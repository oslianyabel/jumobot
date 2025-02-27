import asyncio
import json
import logging

import aiohttp
from openai import OpenAI

from chatbot.core import utils
from chatbot.core.config import get_config
from chatbot.core.getToken import get_oauth_token
from chatbot.database import Repository
from chatbot.core.assistant import Assistant
from chatbot.core import notifications

logger = logging.getLogger(__name__)

config = get_config()
OPENAI_API_KEY = config.OPENAI_API_KEY
client = OpenAI(api_key=OPENAI_API_KEY)
PUBLIC_ODOO_URL = config.PUBLIC_ODOO_URL
PUBLIC_CREATE_PATH = config.PUBLIC_CREATE_PATH
PUBLIC_SEARCH_PATH = config.PUBLIC_SEARCH_PATH


async def test_create_lead(name, email, services, user_number) -> str | bool:
    return "Hemos registrado tus datos. De todas formas agenda tu cita aqui: https://outlook.office365.com/owa/calendar/IACorreo@jumotech.com/bookings/"


async def create_lead(name, email, services, user_number) -> str | bool:
    logger.debug("Creando lead...")
    notifications.send_twilio_message(
        body="La consulta se está procesando. Por favor espere unos segundos",
        from_=config.BOT_NUMBER,
        to=user_number,
    )
    partner, status = await utils.create_partner_odoo(name, user_number, email)
    if not partner:
        msg = "Error creating partner"
        logger.error(msg)
        return msg

    db = Repository()
    bot = Assistant(name="JumoBot_get_chat", assistant_id=config.JUMO_ASSISTANT_ID)
    user = await db.get_user(phone=user_number)
    if not user:
        msg = f"{user_number} no está registrado en la base de datos"
        logger.warning(msg)
        return msg
    
    chat = await bot.get_chat(thread_id=user.thread_id)
    if not chat:
        msg = f"{user_number} tiene el chat vacío"
        logger.warning(msg)
        return msg

    resume_html, resume, products = await asyncio.gather(
        utils.resume_chat(chat, html_format=True),
        utils.resume_chat(chat, html_format=False),
        utils.product_extraction(chat, user_number),
    )

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
        utils.notify_lead(partner, resume, email, lead, products)
        return "Hemos registrado tus datos. Puedes agendar una cita con nosotros aqui: https://outlook.office365.com/owa/calendar/IACorreo@jumotech.com/bookings/"
    else:
        logger.error("Error creando el lead")
        return False


async def test_get_partner(user_number, name=False):
    partner = {
        "name": "Osliani",
        "email": "test@gmail.com",
        "phone": "+5352045846",
    }
    return f"Socio existente: {partner}"


async def get_partner(user_number, name=False):
    logger.debug("Getting partner...")
    format_number = utils.format_phone_number(user_number)
    partner = await utils.get_partner_by_phone(format_number)

    if partner:
        msg = f"Socio existente: {partner}"
        logger.debug(msg)
        return msg

    return f"No existe contacto registrado con el teléfono {user_number}. Pedir al usuario crear una cuenta"


async def test_create_partner(name, user_number, email=None):
    partner = {
        "name": "Osliani",
        "email": "test@gmail.com",
        "phone": "+5352045846",
    }
    return f"Contacto existente: {partner}"


async def create_partner(name, user_number, email=None):
    logger.debug("Creating partner...")
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


async def test_presupuestos(user_number):
    return "No se encontraron pedidos asociados al teléfono +5352045846"


async def presupuestos(user_number):
    # View a customer's orders (quotes) in odoo
    logger.debug(f"Getting sale orders (presupuestos) of {user_number}...")
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


async def test_sale_order_by_name(name, user_number) -> str:
    return "El pedido no le pertenece a usted"


async def sale_order_by_name(name, user_number) -> str:
    logger.debug(f"Getting sale order {name}")
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


async def test_clean_chat(user_number) -> str:
    return "Historial Eliminado"


async def clean_chat(user_number) -> str:
    db = Repository()
    await db.reset_thread(phone=user_number)

    return "Historial Eliminado"
