import json

import aiohttp
from colorama import Fore, init
from openai import OpenAI
from pydantic import BaseModel

from chatbot.core.assistant import Assistant
from chatbot.core.completions import Completions
from chatbot.core.config import get_config
from chatbot.core.extractor_prompt import extractor_prompt
from chatbot.core.getToken import get_oauth_token
from chatbot.core import notifications

init(autoreset=True)

env_config = get_config()
OPENAI_API_KEY = env_config.OPENAI_API_KEY
client = OpenAI(api_key=OPENAI_API_KEY)

PUBLIC_ODOO_URL = env_config.PUBLIC_ODOO_URL
PUBLIC_CREATE_PATH = env_config.PUBLIC_CREATE_PATH
PUBLIC_SEARCH_PATH = env_config.PUBLIC_SEARCH_PATH
SEARCH_URL = f"{PUBLIC_ODOO_URL}{PUBLIC_SEARCH_PATH}"
CREATE_URL = f"{PUBLIC_ODOO_URL}{PUBLIC_CREATE_PATH}"


class Product(BaseModel):
    product_name: str
    product_id: int
    price_unit: int
    product_uom: int
    discount: int
    product_uom_qty: int


class ProductList(BaseModel):
    products: list[Product]


async def resume_chat(chat, html_format=True):
    """Summarizes a user's conversation

    Keyword arguments:
    user_number -- User Number

    Return: Chat Summary
    """

    print("Obteniendo resumen...")

    if html_format:
        ASSISTANT_ID = get_config().RESUME_ASSISTANT_ID
    else:
        ASSISTANT_ID = get_config().TEXT_RESUME_ASSISTANT_ID

    resumidor = Assistant("resumidor", ASSISTANT_ID)
    resume, status = await resumidor.submit_message(chat)
    print(Fore.BLUE + "Chat resumido:", resume, sep="\n")

    return resume


def product_extraction(history, user_number):
    print("Extrayendo productos de la conversación con IA...")

    messages = [{"role": "system", "content": extractor_prompt}]
    model = "gpt-4o-2024-08-06"
    extractor = Completions(model=model, messages=messages, response_format=ProductList)

    products, ok = extractor.submit_message(message=history, user_number=user_number)

    if ok:
        print(Fore.BLUE + "Productos extraídos:", products, sep="\n")
        return products.products

    else:
        print(Fore.RED + "Error extrayendo productos.")
        return []


def notify_lead(partner, resume, client_email, lead):
    subject = "He creado una nueva oportunidad en Odoo desde WhatsApp!"
    message = f"ID del lead: {lead[0][0]}\n"
    message = f"Nombre del lead: {lead[0][1]}\n"
    message += f"Nombre del cliente: {partner['name']}\n"
    message += f"Número de teléfono del cliente: {partner['phone']}\n"
    message += f"Correo Electrónico del cliente: {client_email}\n"
    message += f"Resumen de la conversación: \n{resume}\n"

    if get_config().ENVIRONMENT != "dev":
        notifications.send_email("jmojeda@jumotech.com", subject, message)
        notifications.send_email("richard.p@jumotech.com", subject, message)

    return notifications.send_email("o.abel@jumotech.com", subject, message)


async def create_lead_odoo(partner, resume, email):
    print("Creando lead en Odoo...")

    try:
        data = {
            "model": "crm.lead",
            "method": "create",
            "args": json.dumps(
                [
                    {
                        "stage_id": 1,
                        "type": "opportunity",
                        "name": f"WhatsApp - {partner['name']}",
                        "email_from": email,
                        "phone": partner["phone"],
                        "description": resume,
                        "partner_id": partner["id"],
                    }
                ]
            ),
        }

    except Exception as error:
        msg = f"Error al consultar los campos del partner: {partner} ({type(partner)})\n{str(error)}"
        print(Fore.RED + msg)
        notifications.send_email(
            "o.abel@jumotech.com", "Error al consultar los campos de un partner en wa_jumo", msg
        )
        return False

    headers = {"Authorization": f"Bearer {get_oauth_token()}"}

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{CREATE_URL}", headers=headers, data=data
        ) as response:
            if response.status == 200:
                lead_info = response.json()
                print("Lead creado: ", Fore.BLUE + f"{lead_info}")
                return lead_info

            return False


def create_order_line(products):
    print("Creando líneas de pedido...")

    order_line = []
    supported_products = [622]
    try:
        for p in products:
            if p.product_id not in supported_products:
                print(
                    Fore.YELLOW + "producto no admitido:",
                    f"{p.product_name} id: {p.product_id}",
                )
                continue

            order_line.append(
                {
                    "name": p.product_name,
                    "product_id": p.product_id,
                    "price_unit": p.price_unit,
                    "product_uom": p.product_uom,
                    "product_uom_qty": p.product_uom_qty,
                    "discount": p.discount,
                    "price_total": p.product_uom_qty * p.price_unit,
                }
            )

        print("Líneas de pedido creadas:", Fore.BLUE + f"{order_line}", sep="\n")
        return order_line

    except Exception as error:
        msg = f"Error creando líneas de pedido: {str(error)}"
        print(Fore.RED + msg)
        notifications.send_email("o.abel@jumotech.com", "Error creando líneas de pedido en wa_jumo", msg)
        return False


async def create_partner_odoo(name, phone, email=None):
    try:
        phone = format_phone_number(phone)
        partner = get_partner_by_phone(phone)

        if partner:
            print("Socio ya existente:", Fore.BLUE + f"{partner}")
            return partner, "ALREADY"

        print("Creando Partner...")

        args = [
            {
                "name": name,
                "phone": phone,
            }
        ]

        if email:
            args[0]["email"] = email

        odoo_form_data = {
            "model": "res.partner",
            "method": "create",
            "args": args,
            "kwargs": {},
        }

        headers = {"Authorization": f"Bearer {get_oauth_token()}"}

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{CREATE_URL}", json=odoo_form_data, headers=headers
            ) as response:
                if not response.ok:
                    print(Fore.RED + f"Error al crear partner: {response.text}")
                    return False, "ERROR"

        partner = get_partner_by_phone(phone)

        if not partner:
            print(Fore.RED + "Error al asignar el número de teléfono al socio.")
            return False, "ERROR"

        print("Partner creado:", Fore.BLUE + f"{partner}")
        return partner, "CREATE"

    except Exception as exc:
        msg = f"Error creando partner: {str(exc)}"
        print(Fore.RED + msg)
        notifications.send_email("o.abel@jumotech.com", "Error creando partner en wa_jumo", msg)
        return False


async def get_partner(phone=False, email=False, id=False):
    headers = {
        "Authorization": f"Bearer {get_oauth_token()}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "res.partner",
        "fields": [
            "name",
            "email",
            "is_company",
            "company_id",
            "parent_id",
            "phone",
            "id",
        ],
        "limit": 1,
    }

    if phone:
        payload["domain"] = [["phone", "ilike", phone]]

    elif email:
        payload["domain"] = [["email", "=", email]]

    elif id:
        payload["domain"] = [["id", "=", id]]

    async with aiohttp.ClientSession() as session:
        async with session.post(SEARCH_URL, json=payload, headers=headers) as response:
            if response.status == 200:
                partners = response.json()

                if partners:
                    return partners[0]
                else:
                    print(
                        Fore.RED
                        + f"No se encontró ningún partner con el teléfono {phone}"
                    )
                    return None

            else:
                print(Fore.RED + f"Error al obtener el partner: {response.text}")
                return False


async def get_partner_by_id(id):
    return await get_partner(id=id)


async def get_partner_by_phone(phone):
    return await get_partner(phone=phone)


async def get_partner_by_email(email):
    return await get_partner(email=email)


async def create_sale_order(partner_id, order_line):
    print("Creando pedido...")

    headers = {
        "Authorization": f"Bearer {get_oauth_token()}",
        "Content-Type": "application/json",
    }

    order_line_commands = [(0, 0, line) for line in order_line]

    data = {
        "model": "sale.order",
        "method": "create",
        "args": [
            {
                "partner_id": partner_id,
                "order_line": order_line_commands,
                "company_id": 1,
            }
        ],
        "kwargs": {},
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(CREATE_URL, json=data, headers=headers) as response:
            if response.status == 200:
                order_id = response.json()
                print("Pedido creado con ID:", Fore.BLUE + f"{order_id}")
                return order_id

            else:
                print(Fore.RED + f"Error creando pedido: {response.text}")
                return False


async def search_product_by_id(product_id):
    headers = {
        "Authorization": f"Bearer {get_oauth_token()}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "product.product",
        "domain": [["id", "=", product_id]],
        "fields": ["id", "name", "uom_id", "list_price", "taxes_id"],
        "limit": 1,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(SEARCH_URL, json=payload, headers=headers) as response:
            if response.status == 200:
                product_data = response.json()
                if product_data:
                    product = product_data[0]
                    return product.get("taxes_id")
                else:
                    return None

            else:
                msg = f"Error buscando el producto: {response.text}"
                notifications.send_email("o.abel@jumotech.com", "Error buscando producto por id en wa_jumo", msg)
                raise Exception(msg)


def format_phone_number(phone_number: str) -> str:
    print(f"Formateando número de teléfono: {phone_number}")
    # Elimina los espacios y los caracteres no numéricos
    phone_number = "".join(filter(str.isdigit, phone_number))

    # Se aplica el formato
    formatted_phone_number = f"+{phone_number[:2]} {phone_number[2:5]} {phone_number[5:7]} {phone_number[7:9]} {phone_number[9:]}"
    print(f"Formateado a: {formatted_phone_number}")

    return formatted_phone_number


async def presupuestos(phone):
    partner = get_partner_by_phone(phone)

    if not partner:
        return False

    if not partner["is_company"] and partner["parent_id"]:
        # Si el partner pertenece a una compañía tomar la compañía como referencia
        partner = get_partner_by_id(partner["parent_id"][0])

    headers = {
        "Authorization": f"Bearer {get_oauth_token()}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "sale.order",
        "domain": [["partner_id", "=", partner["id"]]],
        "fields": ["id", "name", "date_order", "state", "partner_id"],
        "order": "state",
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(SEARCH_URL, json=payload, headers=headers) as response:
            if response.status == 200:
                orders = response.json()
                if orders:
                    orders2 = []
                    for order in orders:
                        order2 = await sale_order_by_name(order["name"])
                        if order2["partner_id"][0] == partner["id"]:
                            orders2.append(order)
                    return json.dumps(orders2)
                else:
                    print(
                        Fore.YELLOW
                        + f"No se encontraron pedidos asociados al teléfono {phone}"
                    )
                    return f"No se encontraron pedidos asociados al teléfono {phone}"
            else:
                print(Fore.RED + f"Error al obtener los presupuestos: {response.text}")
                return f"Error al obtener los presupuestos: {response.text}"


async def sale_order_by_name(name):
    headers = {
        "Authorization": f"Bearer {get_oauth_token()}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "sale.order",
        "domain": [["name", "ilike", name]],
        "fields": [
            "id",
            "name",
            "partner_id",
            "date_order",
            "order_line",
            "state",
            "amount_total",
            "user_id",
            "company_id",
            "access_token",
        ],
        "limit": 1,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(SEARCH_URL, json=payload, headers=headers) as response:
            if response.status == 200:
                sale_orders = response.json()

                if sale_orders:
                    link = (
                        PUBLIC_ODOO_URL
                        + "/my/orders/"
                        + str(sale_orders[0]["id"])
                        + "?access_token="
                        + str(sale_orders[0]["access_token"])
                    )
                    sale_orders[0]["link"] = link
                    return sale_orders[0]

                else:
                    print(Fore.YELLOW + f"No se encontró el pedido {name}")
                    return None

            else:
                print(Fore.RED + f"Error consultando el pedido: {response.text}")
                return False
