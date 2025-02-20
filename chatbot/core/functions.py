import asyncio
import json
import logging

import aiohttp
from openai import OpenAI

from chatbot.core import utils
from chatbot.core.config import get_config
from chatbot.core.getToken import get_oauth_token
from chatbot.database import Repository

logger = logging.getLogger(__name__)

config = get_config()
OPENAI_API_KEY = config.OPENAI_API_KEY
client = OpenAI(api_key=OPENAI_API_KEY)
PUBLIC_ODOO_URL = config.PUBLIC_ODOO_URL
PUBLIC_CREATE_PATH = config.PUBLIC_CREATE_PATH
PUBLIC_SEARCH_PATH = config.PUBLIC_SEARCH_PATH


async def create_lead(name, email, user_number) -> str | bool:
    partner, status = await utils.create_partner_odoo(name, user_number, email)

    if not partner:
        msg = "Error creando el partner"
        logger.error(msg)
        return msg

    db = Repository()
    chat = await db.get_chat(phone=user_number)
    if not chat:
        msg = f"No se encontró el chat del número {user_number}"
        logger.warning(msg)
        return msg

    results = await asyncio.gather(
        utils.resume_chat(chat, html_format=True),
        utils.resume_chat(chat, html_format=False),
        utils.product_extraction(chat, user_number),
    )
    resume_html, resume, products = results
    order_line = utils.create_order_line(products)
    if order_line:
        results = await asyncio.gather(
            utils.create_sale_order(partner["id"], order_line),
            utils.create_lead_odoo(partner, resume_html, email),
        )
        order_id, lead = results
    else:
        lead = await utils.create_lead_odoo(partner, resume_html, email)

    if lead:
        utils.notify_lead(partner, resume, email, lead)
        return "El equipo de ventas se pondrá en contacto contigo próximamente"
    else:
        logger.error("Error creando el lead")
        return False


async def get_partner(user_number, name=False):
    format_number = utils.format_phone_number(user_number)
    partner = await utils.get_partner_by_phone(format_number)

    if partner:
        msg = f"Socio existente: {partner}"
        logger.debug(msg)
        return msg

    return f"No existe contacto registrado con el teléfono {user_number}. Pedir al usuario crear una cuenta"


async def create_partner(name, user_number, email=None):
    data = {"name": name}
    if email:
        data["email"] = email

    db = Repository()
    partner_data, _ = await asyncio.gather(
        utils.create_partner_odoo(name, user_number, email),
        db.set_user_data(phone=user_number, data=data)
    )
    partner = partner_data[0]
    status = partner_data[1] 

    if status == "ALREADY":
        return f"Socio encontrado: {partner}"

    elif status == "CREATE":
        return f"Contacto creado: {partner}"

    logger.error("Error creando el partner")
    return False


async def presupuestos(user_number):
    # View a customer's orders (quotes) in odoo
    token = await get_oauth_token()
    partner = await utils.get_partner_by_phone(user_number, token)

    if not partner:
        return f"No se encontró ningún cliente con el teléfono: {user_number}"

    if not partner["is_company"] and partner["parent_id"]:
        # Si el partner pertenece a una compañía tomar la compañía como referencia
        partner = await utils.get_partner_by_id(partner["parent_id"][0])

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
            if response.status == 200:

                async def process_order(order, partner):
                    order2 = await sale_order_by_name(order["name"])
                    if order2["partner_id"][0] == partner["id"]:
                        return order
                    return None

                orders = await response.json()
                if orders:
                    tasks = [process_order(order, partner) for order in orders]
                    results = await asyncio.gather(*tasks)
                    orders2 = [order for order in results if order is not None]
                    return json.dumps(orders2)
                else:
                    msg = (
                        f"No se encontraron pedidos asociados al teléfono {user_number}"
                    )
                    logger.warning(msg)
                    return msg
            else:
                logger.error(f"Error al obtener los presupuestos: {response.text}")
                return False


async def sale_order_by_name(name, user_number) -> str:
    partner = await utils.get_partner_by_phone(user_number)

    if not partner:
        msg = "El partner no existe"
        logger.warning(msg)
        return msg

    if not partner["is_company"] and partner["parent_id"]:
        logger.info(f"Compañía {partner['parent_id']} tomada como referencia")
        # Si el partner pertenece a una compañía tomar la compañía como referencia
        partner = await utils.get_partner_by_id(partner["parent_id"][0])

    order = await utils.sale_order_by_name(name)

    if not order:
        msg = "El pedido no existe"
        logger.warning(msg)
        return msg

    elif order["partner_id"][0] == partner["id"]:
        return json.dumps(order)

    else:
        logger.warning(f"El pedido le pertenece a {order['partner_id'][1]}")
        return "El pedido no le pertenece a usted"


async def clean_chat(user_number) -> str:
    db = Repository()
    await db.reset_thread(phone=user_number)

    return "Historial Eliminado"


if __name__ == "__main__":
    asyncio.run(presupuestos("34930039876"))
