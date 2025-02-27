import logging
import re
import time

from asgi_correlation_id import CorrelationIdMiddleware
from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from twilio.twiml.messaging_response import MessagingResponse

from chatbot.core import notifications, utils
from chatbot.core.JumoAssistant import JumoAssistant
from chatbot.database import Repository
from chatbot.loggin_conf import configure_loggin, get_config

configure_loggin()
logger = logging.getLogger(__name__)
app = FastAPI()
app.add_middleware(CorrelationIdMiddleware)


def checktime(last_time):
    performance = time.time() - last_time
    if performance > 25:
        logger.warning(f"Performance de la API: {performance}")
    else:
        logger.debug(f"Performance de la API: {performance}")

    return time.time()


@app.exception_handler(HTTPException)
async def http_exception_handle_logging(request, exc):
    logger.error(f"HTTPException: {exc.status_code} {exc.detail}")
    return await http_exception_handler(request, exc)


@app.post("/whatsapp")
async def whatsapp_reply(request: Request):
    last_time = time.time()
    logger.debug("=" * 125)

    # recieve request
    form_data = await request.form()
    user_number = re.sub(r"^whatsapp:\+", "", form_data.get("From", ""))
    incoming_msg = form_data["Body"].strip()
    logger.info(f"User {user_number}: {incoming_msg}")

    # load env variables & initialize objects
    config = get_config()
    BOT_NUMBER = config.BOT_NUMBER or "34930039876"
    WORDS_LIMIT = config.WORDS_LIMIT or 1500
    bot = JumoAssistant()
    db = Repository()

    # retrieve chat
    user = await db.get_user(phone=user_number)
    if user:
        thread_id = user.thread_id
        if user.run_id and user.interactions > 0:  # avoid blockages
            run_status = bot.get_run_status(run_id=user.run_id, thread_id=thread_id)
            if run_status == "requires_action":
                msg = "Se está procesando su consulta anterior. Vuelva a enviar su mensaje. Si persiste el bloqueo escriba 'reset'"
                if incoming_msg == "reset":
                    msg = "El chat ha sido reiniciado"
                    db.reset_thread(phone=user_number)

                notifications.send_twilio_message(
                    body=msg,
                    from_=BOT_NUMBER,
                    to=user_number,
                )
                return str(MessagingResponse())

        if user.interactions == 0 and user.name:  # after reset thread
            logger.debug("Agregando nombre de usuario al contexto del hilo")
            msg = f"(Este es un mensaje del sistema) El usuario se llama {user.name}. Llámalo por su nombre"
            await bot.create_message(thread_id=thread_id, message=msg, role="user")
    else:
        logger.info(f"Primera conversacion de {user_number}")
        partner = await utils.get_partner_by_phone(user_number)
        if partner:
            logger.info(f"{user_number} encontrado en Odoo")
            user = await db.create_user(phone=user_number, name=partner["name"])
            msg = f"(Este es un mensaje del sistema) El usuario se llama {partner['name']}. Llámalo por su nombre"
        else:
            logger.info(f"{user_number} no encontrado en Odoo")
            user = await db.create_user(phone=user_number)
            msg = "(Este es un mensaje del sistema) Pidele el nombre al usuario para que le crees una cuenta"

        thread_id = user["thread_id"]
        await bot.create_message(thread_id=thread_id, message=msg, role="user")

    # generate IA response
    try:
        ans, tools_called = (
            await bot.submit_message(incoming_msg, user_number, thread_id),
        )
        logger.info(f"Tools: {tools_called}")

        logger.debug("Enviando respuesta de la IA por WhatsApp")
        if len(ans) > WORDS_LIMIT:
            logger.warning(
                "Respuesta fragmentada por exceder el límite de caracteres de Twilio"
            )
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

    except Exception as exc:
        logger.error(f"Model response failed: {exc}")
        await db.reset_thread(user_number)  # por posibles trabas en el hilo

        notifications.send_twilio_message(
            "Ha ocurrido un error. Por favor, consulte más tarde",
            BOT_NUMBER,
            user_number,
        )
        notifications.send_email(
            "o.abel@jumotech.com",
            f"Error en wa_jumo respondiendo a {user_number} el mensaje: {incoming_msg}",
            str(exc),
        )

    finally:
        last_time = checktime(last_time)
        return str(MessagingResponse())


@app.post("/bibolis")
async def bibolis_reply(request: Request):
    pass
