import json
import logging

import aiohttp
from colorama import init
from openai import OpenAI
from pydantic import BaseModel

from chatbot.core import notifications
from chatbot.core.assistant import Assistant
from chatbot.core.completions import Completions
from chatbot.core.config import get_config
from chatbot.core.extractor_prompt import extractor_prompt
from chatbot.core.getToken import get_oauth_token

logger = logging.getLogger(__name__)
init(autoreset=True)

config = get_config()
OPENAI_API_KEY = config.OPENAI_API_KEY
client = OpenAI(api_key=OPENAI_API_KEY)

PUBLIC_ODOO_URL = config.PUBLIC_ODOO_URL
PUBLIC_CREATE_PATH = config.PUBLIC_CREATE_PATH
PUBLIC_SEARCH_PATH = config.PUBLIC_SEARCH_PATH
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


async def resume_chat(chat: str, html_format: bool=True) -> str:
    logger.debug("Obteniendo resumen...")
    if html_format:
        ASSISTANT_ID = get_config().RESUME_ASSISTANT_ID
    else:
        ASSISTANT_ID = get_config().TEXT_RESUME_ASSISTANT_ID

    resumidor = Assistant("Resumidor", ASSISTANT_ID)
    resume, tools_called = await resumidor.submit_message(chat)
    logger.debug(f"Chat resumido: {resume}")

    return resume


async def product_extraction(history, user_number) -> list[Product]:
    logger.debug("Extrayendo productos de la conversación con IA...")

    messages = [{"role": "system", "content": extractor_prompt}]
    # model = "gpt-4o-2024-08-06"
    extractor = Completions(
        name="Product extractor", messages=messages, response_format=ProductList
    )
    products, ok = await extractor.submit_message(
        message=history, user_number=user_number
    )
    if ok:
        logger.debug(f"Productos extraídos: {products}")
        return products.products
    else:
        logger.error("Error extrayendo productos")
        return []


def notify_lead(partner, resume, client_email, lead, products):
    subject = "He creado un presupuesto en el Odoo de Jumo desde WhatsApp!"
    message = "="*50
    message += f"\nNombre del cliente: {partner['name']}\n"
    message += f"Teléfono del cliente: {partner['phone']}\n"
    message += f"Email del cliente: {client_email}\n"
    message += f"ID del lead: {lead[0][0]}\n"
    message += f"Nombre del lead: {lead[0][1]}\n"
    message += f"Productos solicitados: {products}\n"
    message += f"Resumen de la conversación: \n{resume}"

    logger.debug(f"Notificacion del lead: {message}")

    if get_config().ENVIRONMENT != "dev":
        notifications.send_email("jmojeda@jumotech.com", subject, message)
        notifications.send_email("richard.p@jumotech.com", subject, message)

    return notifications.send_email("o.abel@jumotech.com", subject, message)


async def create_lead_odoo(partner, resume, email):
    logger.debug("Creating Odoo lead...")
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
        logger.error(msg)
        notifications.send_email(
            "o.abel@jumotech.com",
            "Error al consultar los campos de un partner en wa_jumo",
            msg,
        )
        return False

    token = await get_oauth_token()
    headers = {"Authorization": f"Bearer {token}"}

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{CREATE_URL}", headers=headers, data=data
        ) as response:
            if response.status == 200:
                lead_info = await response.json()
                logger.debug(f"Lead creado: {lead_info}")
                return lead_info

            return False


def create_order_line(products):
    logger.debug("Creating order lines...")

    order_line = []
    supported_products = [622]
    try:
        for p in products:
            if p.product_id not in supported_products:
                logger.warning(
                    f"producto no admitido: {p.product_name} id: {p.product_id}"
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

        logger.debug(f"order lines created: {order_line}")
        return order_line

    except Exception as error:
        msg = f"Error creating order lines: {str(error)}"
        logger.error(msg)
        notifications.send_email(
            "o.abel@jumotech.com", "Error creando líneas de pedido en wa_jumo", msg
        )
        return False


async def create_partner_odoo(name, phone, email=None):
    try:
        phone = format_phone_number(phone)
        partner = await get_partner_by_phone(phone)

        if partner:
            logger.debug(f"Partner found: {partner}")
            return partner, "ALREADY"

        logger.debug("Creating Partner...")

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

        token = await get_oauth_token()
        headers = {"Authorization": f"Bearer {token}"}

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{CREATE_URL}", json=odoo_form_data, headers=headers
            ) as response:
                if not response.ok:
                    logger.error(f"Error al crear partner: {response.text}")
                    return False, "ERROR"

        partner = await get_partner_by_phone(phone)

        if not partner:
            logger.error("Error al asignar el número de teléfono al socio")
            return False, "ERROR"

        logger.debug(f"Partner created: {partner}")
        return partner, "CREATE"

    except Exception as exc:
        msg = f"Error creating partner: {str(exc)}"
        logger.error(msg)
        notifications.send_email(
            "o.abel@jumotech.com", "Error creando partner en wa_jumo", msg
        )
        return False


async def get_partner(phone=False, email=False, id=False, token=False):
    if not token:
        token = await get_oauth_token()

    headers = {
        "Authorization": f"Bearer {token}",
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
                partners = await response.json()
                if partners:
                    return partners[0]
                else:
                    logger.warning(
                        f"No se encontró ningún partner con el teléfono {phone}"
                    )
                    return None

            else:
                logger.error(f"Error al obtener el partner: {response.text}")
                return False


async def get_partner_by_id(id, token=False):
    return await get_partner(id=id, token=token)


async def get_partner_by_phone(phone, token=False):
    return await get_partner(phone=phone, token=token)


async def get_partner_by_email(email, token=False):
    return await get_partner(email=email, token=token)


async def create_sale_order(partner_id, order_line):
    logger.debug("Creando pedido...")
    token = get_oauth_token()
    headers = {
        "Authorization": f"Bearer {token}",
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
                order_id = await response.json()
                logger.debug(f"Pedido creado con ID: {order_id}")
                return order_id

            else:
                logger.error(f"Error creando pedido: {response.text}")
                return False


async def search_product_by_id(product_id):
    token = await get_oauth_token()
    headers = {
        "Authorization": f"Bearer {token}",
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
                product_data = await response.json()
                if product_data:
                    product = product_data[0]
                    return product.get("taxes_id")
                else:
                    return None

            else:
                msg = f"Error searching the product: {response.text}"
                notifications.send_email(
                    "o.abel@jumotech.com",
                    "Error buscando producto por id en wa_jumo",
                    msg,
                )
                raise Exception(msg)


def format_phone_number(phone_number: str) -> str:
    logger.debug(f"Formateando teléfono {phone_number}")
    # Elimina los espacios y los caracteres no numéricos
    phone_number = "".join(filter(str.isdigit, phone_number))

    # Se aplica el formato
    formatted_phone_number = f"+{phone_number[:2]} {phone_number[2:5]} {phone_number[5:7]} {phone_number[7:9]} {phone_number[9:]}"
    logger.debug(f"Formateado a: {formatted_phone_number}")

    return formatted_phone_number


async def sale_order_by_name(name):
    token = await get_oauth_token()
    headers = {
        "Authorization": f"Bearer {token}",
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
                sale_orders = await response.json()

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
                    logger.warning(f"No se encontró el pedido {name}")
                    return None

            else:
                logger.error(f"Error consultando el pedido: {response.text}")
                return False
