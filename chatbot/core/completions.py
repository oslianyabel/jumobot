import asyncio
import json
import logging
import time
from datetime import datetime

from openai import AsyncOpenAI
from pydantic import BaseModel

from chatbot.core import notifications
from chatbot.core.config import get_config
from chatbot.core.extractor_prompt import extractor_prompt

logger = logging.getLogger(__name__)


class Completions:
    def __init__(
        self,
        messages,
        name = "CompletionsBot",
        model="gpt-4o-mini",
        tools=[],
        functions={},
        tool_choice="auto",
        response_format=False,
    ):
        self.client = AsyncOpenAI(api_key=get_config().OPENAI_API_KEY)
        self.name = name
        self.model = model
        self.messages = messages
        self.tools = tools
        self.tool_choice = tool_choice
        self.functions = functions
        self.response_format = response_format

    async def submit_message(self, message, user_number):
        last_time = time.time()

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
            msg = f"Falló la respuesta del modelo en wa_jumo: {exc}"
            logger.error(msg)
            notifications.send_email("o.abel@jumotech.com", "Completions error", msg)
            logger.info(f"Performance de {self.name}: {time.time() - last_time}")
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

        logger.info(f"Performance de {self.name}: {time.time() - last_time}")
        return ans, True

    async def tool_calls(self, response, user_number):
        logger.info("Tool calls!")
        self.messages.append(response.choices[0].message)

        for tool_call in response.choices[0].message.tool_calls:
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)
            logger.info(function_name)
            logger.info(function_args)

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
