import smtplib
import time
from email.message import EmailMessage

from colorama import Fore, init
from twilio.rest import Client

from chatbot.core.config import get_config

init(autoreset=True)


def send_email(EMAIL_TO, subject, message):
    config = get_config()
    if config.ENVIRONMENT != "prod":
        return True
    
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

        print("Correo enviado a", Fore.BLUE + EMAIL_TO)
        return True

    except Exception as exc:
        print(Fore.RED + f"Error enviando correo a {EMAIL_TO}:", exc)
        return False


def send_twilio_message(body, from_, to):
    try:
        config = get_config()
        twilio_client = Client(config.ACCOUNT_SID, config.AUTH_TOKEN)
        twilio_client.messages.create(
            body=body, from_=f"whatsapp:+{from_}", to=f"whatsapp:+{to}"
        )
        print(Fore.BLUE + "- Bot:", body, sep="\n")
        return True

    except Exception as exc:
        msg = f"Error enviando mensaje de WhatsApp mediante Twilio: {str(exc)}"
        print(Fore.RED + msg)
        send_email("o.abel@jumotech.com", "Error enviando mensaje de WhatsApp", msg)
        return False


def send_twilio_message2(body, from_, to):
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
            print(Fore.BLUE + "- Bot:", body, sep="\n")
            return True

        except Exception as exc:
            print(Fore.YELLOW + f"Attempt {attempt} failed:", exc)
            if attempt < retries:
                print(Fore.YELLOW + f"Retrying in {delay * 1000}ms...")
                time.sleep(delay)  # Wait before retrying

            else:
                print(Fore.RED + "All attempts to send the message failed")
                subject = f"Error enviando mensaje de WhatsApp de {from_} a {to}"
                msg = subject + f"\nMensaje: {body}\nError: {exc}"
                send_email("o.abel@jumotech.com", subject, msg)
                return False
