import logging
import smtplib
import time
from email.message import EmailMessage

from twilio.rest import Client

from chatbot.core.config import get_config

logger = logging.getLogger(__name__)


def send_email(EMAIL_TO, subject, message):
    config = get_config()
    if config.ENVIRONMENT != "prod":
        return True

    logger.debug(f"Enviando correo a {EMAIL_TO}")
    EMAIL = config.EMAIL
    PASSWORD = config.EMAIL_PASSWORD
    HOST = config.EMAIL_HOST

    email = EmailMessage()
    email["from"] = EMAIL
    email["to"] = EMAIL_TO
    email["subject"] = subject
    email.set_content(message)

    try:
        with smtplib.SMTP(HOST, port=587) as smtp:
            smtp.starttls()
            smtp.login(EMAIL, PASSWORD)
            smtp.sendmail(EMAIL, EMAIL_TO, email.as_string())

        logger.info(f"Correo enviado a {EMAIL_TO}")
        return True

    except Exception as exc:
        logger.error(f"Error enviando correo a {EMAIL_TO}: {exc}")
        return False


def send_twilio_message(body, from_, to):
    config = get_config()
    if config.ENVIRONMENT == "test":
        return True
    
    try:
        logger.debug(f"Enviando mensaje de WhatsApp a {to}")
        config = get_config()
        twilio_client = Client(config.ACCOUNT_SID, config.AUTH_TOKEN)
        twilio_client.messages.create(
            body=body, from_=f"whatsapp:+{from_}", to=f"whatsapp:+{to}"
        )
        return True

    except Exception as exc:
        msg = f"Error enviando mensaje de WhatsApp mediante Twilio: {str(exc)}"
        logger.error(msg)
        send_email("o.abel@jumotech.com", "Error enviando mensaje de WhatsApp", msg)
        return False


def send_twilio_message2(body, from_, to):
    config = get_config()
    if config.ENVIRONMENT == "test":
        return True
    
    logger.debug(f"Enviando mensaje de WhatsApp a {to}")
    retries = 3
    delay = 0.5  # 500ms delay
    config = get_config()
    client = Client(config.ACCOUNT_SID, config.AUTH_TOKEN)

    for attempt in range(1, retries + 1):
        try:
            client.messages.create(
                body=body,
                from_=f"whatsapp:+{from_}",
                to=f"whatsapp:+{to}",
            )
            logger.info(f"Bot: {body}")
            return True

        except Exception as exc:
            logger.warning(f"Attempt {attempt} failed: {exc}")
            if attempt < retries:
                logger.warning(f"Retrying in {delay * 1000}ms...")
                time.sleep(delay)  # Wait before retrying

            else:
                logger.error("All attempts to send the message failed")
                subject = f"Error enviando mensaje de WhatsApp de {from_} a {to}"
                msg = subject + f"\nMensaje: {body}\nError: {exc}"
                send_email("o.abel@jumotech.com", subject, msg)
                return False
