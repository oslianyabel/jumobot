import json
import os

from dotenv import load_dotenv
from openai import OpenAI

create_lead = {
    "name": "create_lead",
    "description": "Se crea una oportunidad de negocio en Odoo (lead) y se le notifica a los supervisores de JUMO Technologies para que se pongan en contacto directo con el cliente. Condición: detección de clientes interesados en contratar o negociar algún servicio de la empresa. Preguntar siempre al cliente si quiere realizar la acción antes de proceder.",
    "parameters": {
        "type": "object",
        "properties": {
            "email": {
                "type": "string",
                "description": "Correo electrónico del cliente interesado",
            },
            "name": {"type": "string", "description": "Nombre del cliente interesado"},
        },
        "required": ["email", "name"],
    },
}

get_partner = {
    "name": "get_partner",
    "description": "Consulta el usuario en Odoo del cliente. Esta acción verifica que el usuario sea cliente de JUMO Technologies y de ser así retorna su información personal. Usa esta herramienta para conocer al cliente. Utilizar esta herramienta si el cliente hace preguntas como estas: Sabes quien soy? Cómo me llamo?",
}

create_partner = {
    "name": "create_partner",
    "description": "Registra al usuario en Odoo. Cualquier usuario puede hacerlo. (Prohibido pedir número de teléfono)",
    "parameters": {
        "type": "object",
        "properties": {
            "email": {
                "type": "string",
                "description": "Correo electrónico del cliente (Campo Opcional)",
            },
            "name": {"type": "string", "description": "Nombre del cliente"},
        },
        "required": ["name"],
    },
}

presupuestos = {
    "name": "presupuestos",
    "description": "Consulta los pedidos de un cliente en Odoo. Usa esta herramienta si el cliente hace peticiones similares a estas: Muéstrame mi presupuesto, Dime mis operaciones realizadas, Consulta mi historial de compra, Lístame mis pedidos",
}

sale_order_by_name = {
    "name": "sale_order_by_name",
    "description": "Consulta información de una orden de venta o pedido a partir de su nombre. Los campos extraídos son: (id, name, partner_id, date_order, order_line, state, amount_total, user_id, company_id, access_token y link)",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Nombre de la orden de venta o pedido",
            }
        },
        "required": ["name"],
    },
}

clean_chat = {
    "name": "clean_chat",
    "description": "Borra el historial de mensajes de la conversación actual. Limpia el chat e inicia uno nuevo. Siempre preguntar al usuario si esta seguro de realizar la acción antes de ejecutarla.",
}


def show_json(obj):
    print(json.loads(obj.model_dump_json()))


if __name__ == "__main__":
    load_dotenv()

    JUMO_ASSISTANT_ID = os.getenv("JUMO_ASSISTANT_ID")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    client = OpenAI(api_key=OPENAI_API_KEY)

    """ prompt = "Se te enviaran conversaciones entre un cliente y un asistente para que analices los aspectos mas importantes que se hablaron. Responderas con un texto que resuma toda la conversacion y quede bien definida la intencion del cliente. Necesitamos que en el resumen se destaque el servicio que desea el cliente, los precios ofrecidos, nombre del cliente y nombre de la empresa del cliente en caso de haber. Responde con un texto que tenga un máximo de 500 palabras. No utilices saltos de línea."

    assistant = client.beta.assistants.update (
        "asst_VBTmQrozWUdxX2vC4CD0xRW5",
        instructions = prompt,
    ) """

    assistant = client.beta.assistants.update(
        JUMO_ASSISTANT_ID,
        tools=[
            {"type": "function", "function": create_lead},
            {"type": "function", "function": clean_chat},
            {"type": "function", "function": create_partner},
            {"type": "function", "function": get_partner},
            {"type": "function", "function": presupuestos},
            {"type": "function", "function": sale_order_by_name},
        ],
    )

    show_json(assistant)
