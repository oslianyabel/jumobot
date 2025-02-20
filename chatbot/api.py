import asyncio
import logging
import re
import time

import uvicorn
from asgi_correlation_id import CorrelationIdMiddleware
from colorama import Fore, init
from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from twilio.twiml.messaging_response import MessagingResponse

from chatbot.core import notifications, utils
from chatbot.core.JumoAssistant import JumoAssistant
from chatbot.database import Repository
from chatbot.loggin_conf import configure_loggin, get_config

init(autoreset=True)
configure_loggin()
logger = logging.getLogger(__name__)
app = FastAPI()
app.add_middleware(CorrelationIdMiddleware)


def checktime(last_time):
    performance = time.time() - last_time
    if performance > 25:
        logger.warning(f"Performance: {performance}")
    else:
        logger.debug(f"Performance: {performance}")

    return time.time()


@app.exception_handler(HTTPException)
async def http_exception_handle_logging(request, exc):
    logger.error(f"HTTPException: {exc.status_code} {exc.detail}")
    return await http_exception_handler(request, exc)


@app.post("/whatsapp")
async def whatsapp_reply(request: Request):
    last_time = time.time()
    logger.debug("="*125)

    # recieve request
    form_data = await request.form()
    user_number = re.sub(r"^whatsapp:\+", "", form_data.get("From", ""))
    incoming_msg = form_data["Body"].strip()
    logger.info(f"User {user_number}: {incoming_msg}")

    # load env variables
    config = get_config()
    BOT_NUMBER = config.BOT_NUMBER or "34930039876"
    WORDS_LIMIT = config.WORDS_LIMIT or 1500

    # get or create conversation
    db = Repository()
    user = await db.get_user(phone=user_number)
    if user:
        thread_id = user.thread_id
    else:
        logger.info(f"Primera conversacion de {user_number}")
        partner = await utils.get_partner_by_phone(user_number)
        if partner:
            logger.info(f"{user_number} encontrado en Odoo")
            incoming_msg += (
                f". Me llamo: {partner['name']}. Por favor llámame por mi nombre"
            )
            user = await db.create_user(phone=user_number, name=partner["name"])
        else:
            logger.info(f"{user_number} no encontrado en Odoo")
            incoming_msg += (
                ". No estoy registrado en Odoo. Por favor, créame un usuario"
            )
            user = await db.create_user(phone=user_number)

        thread_id = user["thread_id"]

    # obtener respuesta del LLM
    try:
        jumo_bot = JumoAssistant()
        results = await asyncio.gather(
            db.create_message(phone=user_number, role="User", message=incoming_msg),
            jumo_bot.submit_message(incoming_msg, user_number, thread_id),
        )
        _, bot_ans = results
        ans = bot_ans[0]
        tools_called = bot_ans[1]
        logger.info(f"Herramientas solicitadas: {tools_called}")

    except Exception as exc:
        logger.error(f"Model response failed: {exc}")
        notifications.send_twilio_message(
            "Ha ocurrido un error. Por favor, realice la consulta más tarde",
            BOT_NUMBER,
            user_number,
        )
        notifications.send_email(
            "o.abel@jumotech.com",
            f"Error en wa_jumo respondiendo a {user_number} el mensaje: {incoming_msg}",
            str(exc),
        )
        return str(MessagingResponse())

    await db.create_message(
        phone=user_number, role="Assistant", message=ans, tools_called=tools_called
    )

    # envio de msg por whatsapp
    logger.debug("Enviando mensaje de WhatsApp")
    if len(ans) > WORDS_LIMIT:
        logger.warning("Respuesta fragmentada por exceder el límite de caracteres de Twilio")
        start = 0
        while start < len(ans):
            end = min(start + WORDS_LIMIT, len(ans))
            if end < len(ans) and ans[end] not in ["\n"]:
                while end > start and ans[end] not in ["\n"]:
                    end -= 1
                if end == start:
                    end = start + WORDS_LIMIT
            chunk = ans[start:end].strip()
            notifications.send_twilio_message(chunk, BOT_NUMBER, user_number)
            start = end + 1
    else:
        notifications.send_twilio_message(ans, BOT_NUMBER, user_number)

    last_time = checktime(last_time)
    return str(MessagingResponse())


if __name__ == "__main__":
    PORT = 3026
    print("Bot Online en el puerto " + Fore.BLUE + f"{PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
