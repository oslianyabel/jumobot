import asyncio
import json
import logging
import time

from openai import AsyncOpenAI

from chatbot.core import notifications
from chatbot.core.config import get_config
from chatbot.database import Repository

logger = logging.getLogger(__name__)


class Assistant:
    """
    Class to manage OpenAI client

    Attributes:
                    name (str): The name of the assistant.
                    assistant_id (str): The unique identifier for the assistant.
                    functions (dict): A dictionary of functions associated with the assistant. E.G: {function_name: function} (required parameter of each function: user_id)
    """

    def __init__(self, name, assistant_id, functions={}, api_key=False):
        if api_key:
            self.client = AsyncOpenAI(api_key=api_key)
        else:
            self.client = AsyncOpenAI(api_key=get_config().OPENAI_API_KEY)

        self.name = name
        self.assistant_id = assistant_id
        self.functions = functions
        self.error_msg = (
            "Ha ocurrido un error, por favor realice la consulta más tarde."
        )
        self.db = Repository()

    def add_function(self, function_name, function):
        self.functions[function_name] = function

    async def create_thread(self):
        logger.debug("Creating thread...")
        thread = await self.client.beta.threads.create()
        thread_id = thread.id
        logger.debug(f"thread created: {thread_id}")
        return thread_id

    async def get_response(self, message_object, thread_id):
        logger.debug(f"Getting last message from {thread_id}")

        response = await self.client.beta.threads.messages.list(
            thread_id=thread_id, order="asc", after=message_object.id
        )

        ans = ""
        async for message in response:
            if hasattr(message, "content") and len(message.content) > 0:
                ans += f"{message.content[0].text.value}\n"

        return ans

    async def get_chat(self, thread_id):
        logger.debug(f"Getting chat from {thread_id}")

        response = await self.client.beta.threads.messages.list(
            thread_id=thread_id, order="asc"
        )

        ans = ""
        async for message in response:
            if hasattr(message, "content") and len(message.content) > 0:
                ans += f"{message.content[0].text.value}\n"

        return ans

    async def create_message(self, thread_id, message, role):
        message_object = await self.client.beta.threads.messages.create(
            thread_id=thread_id, role=role, content=message
        )
        return message_object

    async def get_run_status(self, run_id, thread_id):
        run = await self.client.beta.threads.runs.retrieve(
            thread_id=thread_id,
            run_id=run_id,
        )
        logger.debug(f"run status: {run.status}")
        return run.status

    async def submit_message(self, message: str, user_id=None, thread_id=None):
        # return -> tuple[str, list[str]]
        before = time.time()
        clean = False
        if not thread_id:
            thread_id = await self.create_thread()
            clean = True

        message_object = await self.create_message(thread_id, message, "user")

        logger.debug(f"Obteniendo respuesta de {self.name}")
        run = await self.client.beta.threads.runs.create_and_poll(
            thread_id=thread_id,
            assistant_id=self.assistant_id,
        )
        await self.db.set_user_data(phone=user_id, data={"run_id": run.id})

        tools_called = []
        while run.status == "requires_action":
            tools = run.required_action.submit_tool_outputs.tool_calls
            logger.debug(f"{len(tools)} tools need to be called!")
            tool_outputs = []

            tasks = []
            for tool in tools:
                function_name = tool.function.name
                arguments = json.loads(tool.function.arguments)
                logger.info(f"Function name: {function_name}")
                logger.info(f"Function arguments: {arguments}")

                if user_id:
                    tasks.append(self._call_tool(function_name, arguments, user_id))
                else:
                    logger.error(f"User_id empty in tool {function_name}")
                    tools_called.append("NO_USER_ID")
                    tool_outputs.append(
                        {
                            "tool_call_id": tool.id,
                            "output": self.error_msg,
                        }
                    )

            # Ejecutar todas las herramientas en paralelo
            before_tools = time.time()
            logger.debug(f"Ejecutando herramientas externas en {self.name}")
            results = await asyncio.gather(*tasks, return_exceptions=True)
            logger.debug(f"Tools performance: {time.time() - before_tools}")
            for result, tool in zip(results, tools):
                if isinstance(result, Exception):
                    msg = f"Error running the tool {tool.function.name}: {result}"
                    logger.error(msg)
                    notifications.send_email(
                        "o.abel@jumotech.com", "Assistant error", msg
                    )
                    tools_called.append(f"{tool.function.name}_ERROR")
                    tool_outputs.append(
                        {
                            "tool_call_id": tool.id,
                            "output": self.error_msg,
                        }
                    )
                else:
                    tool_outputs.append(
                        {
                            "tool_call_id": tool.id,
                            "output": result,
                        }
                    )
                    tools_called.append(tool.function.name)

            run = await self.client.beta.threads.runs.submit_tool_outputs_and_poll(
                thread_id=thread_id,
                run_id=run.id,
                tool_outputs=tool_outputs,
            )
            logger.debug("tools answers sent to the model")
            # end while

        if run.status == "completed":
            ans = await self.get_response(message_object, thread_id)
            logger.info(f"{self.name}: {ans}")
            logger.info(f"Tools: {tools_called}")
            if clean:
                await self.cleanup_resources(thread_id)

            logger.info(f"Performance de {self.name}: {time.time() - before}")
            return ans, tools_called

        return self.error_msg, False

    async def _call_tool(self, function_name, arguments, user_id):
        try:
            function_to_call = self.functions[function_name]
            tool_ans = await function_to_call(**arguments, user_number=user_id)
            if tool_ans:
                logger.info(f"{function_name}: {tool_ans}")
            else:
                logger.error(f"Error running the tool {function_name}")
                return self.error_msg

        except Exception as exc:
            return exc

        return tool_ans

    async def cleanup_resources(self, thread_id: str) -> None:
        logger.debug(f"Borrando hilo: {thread_id}")
        try:
            await self.client.beta.threads.delete(thread_id)
        except Exception as exc:
            logger.error(exc)


class AssistantTest(Assistant):
    async def get_response(self, message_object, thread_id):
        response = await self.client.beta.threads.messages.list(
            thread_id=thread_id, order="asc", after=message_object.id
        )

        ans = f"{self.name}:\n"
        async for message in response:
            if hasattr(message, "content") and len(message.content) > 0:
                ans += f"{message.content[0].text.value}\n"

        return ans
