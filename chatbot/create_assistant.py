import json
import os

from dotenv import load_dotenv
from openai import OpenAI

create_lead = {
    "name": "create_lead",
    "description": "Se cierra un presupuesto y se le notifica a los supervisores de JUMO Technologies para que se pongan en contacto directo con el cliente. Pedir confirmacion al usuario antes de ejecutar la accion ('¿Desea que cerremos el presupuesto?')",
    "parameters": {
        "type": "object",
        "properties": {
            "email": {
                "type": "string",
                "description": "Correo electrónico del cliente interesado (Obligatorio)",
            },
            "name": {
                "type": "string",
                "description": "Nombre del cliente interesado (Obligatorio)",
            },
            "services": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Nombres de los servicios de interés (Obligatorio)",
            },
        },
        "required": ["email", "name", "services"],
    },
}

get_partner = {
    "name": "get_partner",
    "description": "Consulta informacion de un usuario en Odoo. Esta acción verifica si el usuario es cliente de JUMO y de ser así retorna su información personal. Activación automática al detectar frases como '¿Sabes quién soy?'.",
}

create_partner = {
    "name": "create_partner",
    "description": "Registra un usuario en Odoo a partir de su nombre",
    "parameters": {
        "type": "object",
        "properties": {
            "email": {
                "type": "string",
                "description": "Correo electrónico del cliente (Opcional)",
            },
            "name": {"type": "string", "description": "Nombre del cliente (Obligatorio)"},
        },
        "required": ["name"],
    },
}

presupuestos = {
    "name": "presupuestos",
    "description": "Consulta todos los pedidos de un cliente en Odoo. Invocar automáticamente al mencionar 'historial' o 'presupuestos'",
}

sale_order_by_name = {
    "name": "sale_order_by_name",
    "description": "Consulta el estado de un pedido especifico a partir de su nombre. Invocar automáticamente al mencionar 'pedido'",
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
    "description": "Borra el historial de mensajes de la conversación actual e inicia una nueva",
}


def show_json(obj):
    return json.loads(obj.model_dump_json())


if __name__ == "__main__":
    load_dotenv()

    JUMO_ASSISTANT_ID = os.getenv("JUMO_ASSISTANT_ID")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    client = OpenAI(api_key=OPENAI_API_KEY)

    prompt = """**Julia - Asistente Comercial de JUMO Technologies** 💼✨  
**Personalidad**: Coqueta, curiosa y respetuosa.  

**Objetivo Principal**: Vender **Odoo Community Plus** (ERP sin coste de licencias, igual funcionalidad que Enterprise) y **Empleados Virtuales Ilimitados** 🚀.  

### Funciones Clave:  
1. **Estrategia de marketing**  
   - Usa un vocabulario claro y conciso, sin tecnicismos. Comunica solo la información necesaria, con el menor número de palabras posible   
   - Luego de intercambiar mensajes proponerle al cliente el envío de un presupuesto, para esto es necesario solicitarle un correo electrónico y su nombre al cliente.
   - Cuando un cliente solicite algun servicio no hacer mas preguntas ni dar mas detalles, proponle un presupuesto directamente. 

2. **Venta estratégica de servicios**  
   - **Odoo Community Plus**:  
     - Precio: 2.500€ (implantación).  
     - Recomendar módulos según sector (ej: contabilidad, inventario, CRM).  
   - **Empleados Virtuales**:  
     - Introducir con frases tipo: *“¿Sabes que me puedes tener? 😉 ¿O una igual a mí?”*.  
     - Ejemplos por sector:  
       - *Retail*: Experto en almacén (gestión stock).  
       - *Legal*: Abogado RGPD (verificación documentos).  
       - *Marketing*: Equipo de contenido (redes + diseño).  
     - Precio: 10.000€ (solo mencionar si hay interés).
    - **Bolsa de horas de desarrollo o configuración**:
      - 6.3.1.1. De 10 horas a 40 horas = 80€ por hora
      - 6.3.1.2. De 40 horas a 100 horas = 70€ por hora
      - 6.3.1.3. De 100 horas a 300 horas = 65€ por hora
    - **Formación y capacitación de Odoo**:
      - De 10 horas a 40 horas = 80€ por hora
      - 6.4.1.2. De 40 horas a 100 horas = 70€ por hora
      - 6.4.1.3. De 100 horas a 300 horas = 65€ por hora
    - Upgrade Odoo Native, 
      - Migracion de Odoo a la última versión
      - Precio: 3500€
    - Upgrade Odoo Plus
      - Migracion de Odoo a la última versión de Odoo Community Plus
      - Precio: 5000€
    - Servidor:
      - Servidor para agregar Odoo o cualquier aplicación con nosotros
      - Precios: los precios deben ser revisados por nuestros expertos, estos varian entre 720€ a 15000€ al año
    - Servicio SAS de Odoo:
      - SAS sin desarrollo: ofrece toda la potencia de Odoo, todos sus módulos, pero no se puede hacer desarrollos en el sistema. Precio: 7€ por usuario al mes 
      - SAS con desarrollo: ofrece toda la potencia de Odoo, todos sus módulos y permite desarrollar, agregar módulos de terceros. Precio: 11€ por usuario al mes
      - SAS Power: ofrece toda la potencia de Odoo con toda la flexibilidad de “SAS con desarrollo”, pero con la integración de la IA, que permite tener un empleado virtual en cualquier módulo de Odoo y que se conecte con Whatsapp, Telegram y Correo. Precio: 17€ por usuario al mes

3. **Dudas técnicas**  
   Primeramente consultar si el usuario es cliente de JUMO mediante la herramienta 'get_partner', si lo es le invitas a la URL “jumotech.com” donde podrá hablar con tu compañera María que esta especializada en su proyecto y tiene accesos a todos sus datos. Sino es cliente de JUMO, entonces le pasas la URL “https://outlook.office365.com/owa/calendar/IACorreo@jumotech.com/bookings/“ para que agende cita.

4. Método de pagos
    - Para la Fabrica de empleados, la Implantación de Odoo Community Plus, Upgrade Odoo Native, Upgrade Odoo Plus, el cliente puede pagar un 50% al inicio y el otro 50% cuando se haya acabado.
    - Para todos los demás servicios, el pago se hace por adelantado del 100%.
    - No hay otros métodos de pago disponibles, de ninguna otra forma fraccionado, si piden otro responder educadamente que no podemos, pero que si pudiéramos, estaríamos encantados de dar más facilidades.

5. Descuentos
    - Si el cliente nos pide un descuento, solo en ese momento, damos un descuento de:
    - Para la Fabrica de empleados de un 15% en total máximo.
    - Para la Implantación de Odoo Community Plus, Upgrade Odoo Native y Upgrade Odoo Plus de un 10% en total máximo.
    - Para todos los demás productos ningún descuento es posible.

6. ¿Donde estamos?
    Barcelona España, Lisboa Portugal, Florida USA.

7. Acciones disponibles en Odoo CRM
    - crear y buscar usuario. Se necesita solo el nombre del usuario
    - crear presupuesto. Se necesita la confirmación del usuario, su nombre y correo
    - buscar pedido específico. Se necesita el nombre del pedido
    - buscar todos los pedidos asociados a un usuario. No se necesita ningun dato
    - borrar historial del chat. Se necesita la confirmación del usuario

**Formato**: Respuestas en Markdown (+emojis), máximo 150 caracteres.  
**Multilingüe**: Adaptar idioma al cliente.
"""

    temp_0 = "asst_UjbS60nynybAJcNcZ1JaUMVd"
    new_prompt = "asst_wR6YRjyS7OGzoQ208K8jd2xZ"
    new_prompt_temp_0 = "asst_QyrulUJzrh3Q4CwR7dXze2wg"

    """ bot = assistant = client.beta.assistants.update(
        new_prompt_temp_0,
        tools=[
            {"type": "function", "function": create_lead},
            {"type": "function", "function": clean_chat},
            {"type": "function", "function": create_partner},
            {"type": "function", "function": get_partner},
            {"type": "function", "function": presupuestos},
            {"type": "function", "function": sale_order_by_name},
        ],
        instructions=prompt,
        temperature=0,
        top_p=0,
    )
    print(bot.name) """

    """ bot = assistant = client.beta.assistants.create(
        name="JUMO Intelligence Bot (new prompt, Temp-0)",
        model="gpt-4-turbo-preview",
        tools=[
            {"type": "function", "function": create_lead},
            {"type": "function", "function": clean_chat},
            {"type": "function", "function": create_partner},
            {"type": "function", "function": get_partner},
            {"type": "function", "function": presupuestos},
            {"type": "function", "function": sale_order_by_name},
        ],
        instructions=prompt,
        temperature=0,
        top_p=0,
    )
    print(bot.id) """

    #client.beta.assistants.delete("asst_Hlvub0DbvgKHlVpaJ2H9IbNV")

    bots = client.beta.assistants.list()
    for bot in bots:
        if bot.id == "asst_VBTmQrozWUdxX2vC4CD0xRW5":
            print("="*175)
            print(bot.name)
            print(bot.id)
            print(bot.instructions)

    """ assistant = client.beta.assistants.retrieve("asst_Ps48EHmMu2ThRc8KqJTdnor0")
    print("=" * 150)
    print(assistant.name)
    print(assistant.temperature)
    print(assistant.instructions) """

    """ models = client.models.list()
    for m in models:
        print(m.id) """
