import json

import aiohttp
from colorama import Fore, init
from openai import OpenAI

from chatbot.core import utils
from chatbot.core.config import get_config
from chatbot.core.getToken import get_oauth_token
from chatbot.database import Repository

init(autoreset=True)

config = get_config()
OPENAI_API_KEY = config.OPENAI_API_KEY
client = OpenAI(api_key=OPENAI_API_KEY)
PUBLIC_ODOO_URL = config.PUBLIC_ODOO_URL
PUBLIC_CREATE_PATH = config.PUBLIC_CREATE_PATH
PUBLIC_SEARCH_PATH = config.PUBLIC_SEARCH_PATH


async def create_lead(name, email, user_number):
    """Create a lead in Odoo.

    Keyword arguments:
    name -- Partner Name
    email -- Partner Email
    user_number -- Partner Number

    Return: Success or failure message
    """

    partner, status = await utils.create_partner_odoo(name, user_number, email)

    if not partner:
        msg = "Error creando el partner"
        print(Fore.RED + msg)
        return msg

    db = Repository()
    chat = await db.get_chat(phone=user_number)

    if not chat:
        msg = f"No se encontró el chat del número: {user_number}"
        print(Fore.YELLOW + msg)
        return msg

    resume_html = await utils.resume_chat(chat, html_format=True)
    products = utils.product_extraction(chat, user_number)
    order_line = utils.create_order_line(products)

    if order_line:
        order_id = await utils.create_sale_order(partner["id"], order_line)  # noqa: F841

    lead = await utils.create_lead_odoo(partner, resume_html, email)

    if lead:
        resume = await utils.resume_chat(chat, html_format=False)
        utils.notify_lead(partner, resume, email, lead)
        return "El equipo de ventas se pondrá en contacto contigo próximamente"

    else:
        print(Fore.RED + "Error creando el lead")
        return False


async def get_partner(user_number, name=False):
    format_number = utils.format_phone_number(user_number)
    partner = await utils.get_partner_by_phone(format_number)

    if partner:
        msg = f"Socio existente: {partner}"
        return msg

    return f"No existe contacto registrado con el teléfono {user_number}. Pedir al usuario crear una cuenta"


async def create_partner(name, user_number, email=None):
    """Create a partner in odoo.

    Keyword arguments:
    name -- Partner Name
    user_number --  Partner Number
    email -- Partner Email

    Return: Confirmation Message
    """

    partner, status = await utils.create_partner_odoo(name, user_number, email)

    if status == "ALREADY":
        return f"Contacto ya existente: {partner}"

    elif status == "CREATE":
        return f"Contacto creado: {partner}"

    print(Fore.RED + "Error creando el partner")
    return False


async def presupuestos(user_number):
    """View a customer's orders (quotes) in odoo

    Keyword arguments:
    user_number -- user number

    Return: order list: str
    """

    partner = await utils.get_partner_by_phone(user_number)

    if not partner:
        return f"No se encontró ningún cliente con el teléfono: {user_number}"

    if not partner["is_company"] and partner["parent_id"]:
        # Si el partner pertenece a una compañía tomar la compañía como referencia
        partner = await utils.get_partner_by_id(partner["parent_id"][0])

    token = get_oauth_token()
    url = f"{PUBLIC_ODOO_URL}{PUBLIC_SEARCH_PATH}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "sale.order",
        "domain": [["partner_id", "=", partner["id"]]],
        "fields": ["id", "name", "date_order", "state", "partner_id"],
        "order": "state",
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as response:
            if response.status_code == 200:
                orders = response.json()
                if orders:
                    orders2 = []
                    for order in orders:
                        order2 = await sale_order_by_name(order["name"])
                        if order2["partner_id"][0] == partner["id"]:
                            orders2.append(order)
                    return json.dumps(orders2)

                else:
                    msg = (
                        f"No se encontraron pedidos asociados al teléfono {user_number}"
                    )
                    print(Fore.YELLOW + msg)
                    return msg
            else:
                print(Fore.RED + f"Error al obtener los presupuestos: {response.text}")
                return False


async def sale_order_by_name(name, user_number):
    """View order information based on its name

    Keyword arguments:
    name -- Order Name
    user_number -- User Number

    Return: Order (str)
    """

    partner = await utils.get_partner_by_phone(user_number)

    if not partner:
        msg = "El partner no existe"
        print(Fore.YELLOW + msg)
        return msg

    if not partner["is_company"] and partner["parent_id"]:
        print(f"Compañía {partner['parent_id']} tomada como referencia")
        # Si el partner pertenece a una compañía tomar la compañía como referencia
        partner = await utils.get_partner_by_id(partner["parent_id"][0])

    order = await utils.sale_order_by_name(name)

    if not order:
        msg = "El pedido no existe"
        print(Fore.YELLOW + msg)
        return msg

    elif order["partner_id"][0] == partner["id"]:
        return json.dumps(order)

    else:
        print(
            Fore.YELLOW + "El pedido le pertenece a",
            Fore.LIGHTYELLOW_EX + f"{order['partner_id'][1]}",
        )
        return "El pedido no le pertenece a usted"


async def clean_chat(user_number):
    """Delete conversation history

    Keyword arguments:
    user_number -- User Number

    Return: Delete Notify (str)
    """

    db = Repository()
    await db.reset_thread(phone=user_number)

    return "Historial Eliminado"


if __name__ == "__main__":
    """ name = "Osliani"
    email = "test@gmail.com"
    user_number = "52045846"
    
    lead = create_lead(name, email, user_number)
    print(lead) """

    print(sale_order_by_name("S00187", "34936069261"))
