import asyncio
import json
from datetime import datetime

from colorama import Fore, init
from openai import AsyncOpenAI
from pydantic import BaseModel

from chatbot.core import notifications
from chatbot.core.config import get_config
from chatbot.core.extractor_prompt import extractor_prompt

init(autoreset=True)


class Completions:
    def __init__(
        self,
        messages,
        model="gpt-4o-mini",
        tools=[],
        functions={},
        tool_choice="auto",
        response_format=False,
    ):
        self.client = AsyncOpenAI(api_key=get_config().OPENAI_API_KEY)
        self.model = model
        self.messages = messages
        self.tools = tools
        self.tool_choice = tool_choice
        self.functions = functions
        self.response_format = response_format

    async def submit_message(self, message, user_number):
        if message:
            self.messages.append(
                {
                    "role": "user",
                    "content": message,
                    "date": datetime.now().strftime("%Y-%m-%d"),
                }
            )
            # message + "(Fecha: {})".format(datetime.now().strftime('%Y-%m-%d'))

        try:
            if self.tools:
                if self.response_format:
                    response = await self.client.beta.chat.completions.parse(
                        model=self.model,
                        messages=self.messages,
                        tools=self.tools,
                        tool_choice=self.tool_choice,
                        response_format=self.response_format,
                    )
                else:
                    response = await self.client.chat.completions.create(
                        model=self.model,
                        messages=self.messages,
                        tools=self.tools,
                        tool_choice=self.tool_choice,
                    )
            else:
                if self.response_format:
                    response = await self.client.beta.chat.completions.parse(
                        model=self.model,
                        messages=self.messages,
                        response_format=self.response_format,
                    )
                else:
                    response = await self.client.chat.completions.create(
                        model=self.model,
                        messages=self.messages,
                    )

        except Exception as exc:
            msg = f"Falló la respuesta del modelo: {exc}"
            print(Fore.RED + msg)
            notifications.send_email("o.abel@jumotech.com", "Completions error", msg)
            return msg, False

        if response.choices[0].message.tool_calls:
            return await self.tool_calls(response, user_number)

        if self.response_format:
            ans = response.choices[0].message.parsed
        else:
            ans = response.choices[0].message.content

        self.messages.append(
            {
                "role": "assistant",
                "content": ans,
                "date": datetime.now().strftime("%Y-%m-%d"),
            }
        )

        return ans, True

    async def tool_calls(self, response, user_number):
        print("Tool calls!")
        self.messages.append(response.choices[0].message)

        for tool_call in response.choices[0].message.tool_calls:
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)
            print(function_name)
            print(function_args)

            function_to_call = self.functions[function_name]

            function_response = await function_to_call(
                **function_args, user_number=user_number
            )
            self.messages.append(
                {
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": function_name,
                    "content": function_response,
                }
            )

        return await self.submit_message(self, False, user_number)


class Product(BaseModel):
    product_name: str
    product_id: int
    price_unit: int
    product_uom: int
    discount: int
    product_uom_qty: int


class ProductList(BaseModel):
    products: list[Product]


async def main():
    messages = [{"role": "system", "content": extractor_prompt}]

    model = "gpt-4o-2024-08-06"

    bot = Completions(messages=messages, model=model, response_format=ProductList)

    msg = """
    User: Hola, que puedes hacer
    Assistant: En JUMO Technologies, puedo ofrecerte una variedad de servicios adaptados a tus necesidades. Aquí tienes un resumen de lo que podemos hacer:

1. *Implementación de Odoo Community Plus*: Un ERP potente sin coste de licencias, ideal para optimizar la gestión de tu empresa. 💼

2. *Fábrica de Empleados Virtuales*: Crea empleados virtuales ilimitados para tareas específicas, como atención al cliente o gestión de inventarios. ¡Un empleado que nunca se enferma! 🤖

3. *Desarrollo y Configuración de Odoo*: Te ayudamos a personalizar Odoo según tu industria y tus necesidades específicas. 🛠️

4. *Formación y Capacitación*: Ofrecemos formación para que tú y tu equipo aprovechen al máximo Odoo. 📚

5. *Módulos de Odoo*: Podemos integrarte diversos módulos, como CRM, contabilidad, ventas, y mucho más, según lo que tu empresa necesite. 🧩

6. *Soporte en la Nube*: Gestión de servidores y de la plataforma Odoo, asegurando que todo funcione sin problemas. ☁️

¿Te gustaría saber más sobre alguno de estos servicios específicos? ¡Estoy aquí para ayudarte! 💖
    """

    ans, ok = await bot.submit_message(msg, "52045846")
    async for p in ans.products:
        print(p.product_name)


if __name__ == "__main__":
    asyncio.run(main())
