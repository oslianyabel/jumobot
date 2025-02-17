import logging
import re

import uvicorn
from asgi_correlation_id import CorrelationIdMiddleware
from colorama import Fore, init
from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from twilio.twiml.messaging_response import MessagingResponse

from chatbot.core import mongo, notifications, utils
from chatbot.core.JumoAssistant import JumoAssistant

init(autoreset=True)

logger = logging.getLogger(__name__)
app = FastAPI()
app.add_middleware(CorrelationIdMiddleware)

BOT_NUMBER = "34930039876"
WORDS_LIMIT = 1500


@app.exception_handler(HTTPException)
async def http_exception_handle_logging(request, exc):
    logger.error(f"HTTPException: {exc.status_code} {exc.detail}")
    return await http_exception_handler(request, exc)


@app.post("/whatsapp")
async def whatsapp_reply(request: Request):
    form_data = await request.form()
    user_number = re.sub(r"^whatsapp:\+", "", form_data.get("From", ""))
    incoming_msg = form_data["Body"].strip()
    print(Fore.BLUE + "- User", f"{user_number}:", incoming_msg)

    thread_id = await mongo.get_thread(user_number)

    if not thread_id:
        thread_id = await mongo.create_thread(user_number)

        partner = await utils.get_partner_by_phone(user_number)
        if partner:
            print("Usuario encontrado en Odoo")
            incoming_msg += (
                f". Mi nombre es: {partner['name']}. Por favor llámame por ese nombre."
            )
        else:
            print("Usuario sin registrar en Odoo")
            incoming_msg += (
                ". No estoy registrado en Odoo. Por favor, créame un usuario."
            )

    await mongo.update_chat(user_id=user_number, role="User", message=incoming_msg)

    try:
        jumo_bot = JumoAssistant()
        ans, tools_called = await jumo_bot.submit_message(
            incoming_msg, user_number, thread_id
        )
        print(Fore.BLUE + "Herramientas solicitadas:", tools_called)

    except Exception as error:
        print(Fore.RED + f"Error: {error}")
        notifications.send_twilio_message(
            "Ha ocurrido un error. Por favor, realice la consulta más tarde.",
            BOT_NUMBER,
            user_number,
        )
        notifications.send_email(
            "o.abel@jumotech.com",
            f"Error en wa_jumo respondiendo a {user_number} el mensaje: {incoming_msg}",
            str(error),
        )
        return str(MessagingResponse())

    await mongo.update_chat(
        user_id=user_number, role="Assistant", message=ans, tools_called=tools_called
    )

    if len(ans) > WORDS_LIMIT:
        print(Fore.YELLOW + "Respuesta recortada por exceder el límite de Twilio")
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

    return str(MessagingResponse())


if __name__ == "__main__":
    PORT = 3026
    print("Bot Online en el puerto " + Fore.BLUE + f"{PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
