import json

from colorama import Fore, init
from openai import AsyncOpenAI

from chatbot.core import notifications
from chatbot.core.config import get_config

init(autoreset=True)


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

    def add_function(self, function_name, function):
        self.functions[function_name] = function

    async def create_thread(self):
        thread = await self.client.beta.threads.create()
        thread_id = thread.id
        print("thread created: ", Fore.BLUE + thread_id)
        return thread_id

    async def get_response(self, message_object, thread_id):
        response = await self.client.beta.threads.messages.list(
            thread_id=thread_id, order="asc", after=message_object.id
        )

        ans = ""
        async for message in response:
            if hasattr(message, "content") and len(message.content) > 0:
                ans += f"{message.content[0].text.value}\n"

        return ans

    async def submit_message(self, message: str, user_id=False, thread_id=None):
        """Send a message to the model and get its response

        Keyword arguments:
        message -- user message (input)
        user_id -- phone number or telegram id (exclusive uses of tools)
        thread_id -- unique identifier of the conversation

        Return: (model_response:str, status_code:str | False)
        """

        try:
            if not thread_id:
                thread_id = await self.create_thread()

            # Crear el mensaje en el hilo
            message_object = await self.client.beta.threads.messages.create(
                thread_id=thread_id, role="user", content=message
            )

            # Crear y esperar a que el run se complete
            run = await self.client.beta.threads.runs.create_and_poll(
                thread_id=thread_id,
                assistant_id=self.assistant_id,
            )

            tools_called = []

            # Verificar si el run requiere acciones adicionales (como llamar a una función)
            while run.status == "requires_action":
                tools = run.required_action.submit_tool_outputs.tool_calls
                print(Fore.BLUE + f"{len(tools)} tools need to be called!")

                tool_outputs = []

                for tool in tools:
                    function_name = tool.function.name
                    arguments = json.loads(tool.function.arguments)
                    print("Function Name:", Fore.BLUE + f"{function_name}")
                    print("Function Arguments:", Fore.BLUE + f"{arguments}")

                    if user_id:
                        try:
                            function_to_call = self.functions[function_name]
                            tool_ans = await function_to_call(
                                **arguments, user_number=user_id
                            )

                            if tool_ans:
                                print("Tool response:", Fore.BLUE + tool_ans)
                            else:
                                print(
                                    Fore.RED + f"Error running the tool {function_name}"
                                )
                                tools_called.append(f"{function_name}_ERROR")
                                tool_ans = self.error_msg

                        except Exception as exc:
                            msg = f"Error running the tool {function_name}: {exc}"
                            print(Fore.RED + msg)
                            notifications.send_email(
                                "o.abel@jumotech.com", "Assistant error", msg
                            )
                            tools_called.append(f"{function_name}_ERROR")
                            tool_ans = self.error_msg

                    else:
                        print(Fore.RED + "User_id not sent")
                        tools_called.append("NO_USER_ID")
                        tool_ans = self.error_msg

                    tool_outputs.append(
                        {
                            "tool_call_id": tool.id,
                            "output": tool_ans,
                        }
                    )

                    if tool_ans != self.error_msg:
                        tools_called.append(function_name)

                # Enviar las respuestas de las herramientas al modelo
                run = await self.client.beta.threads.runs.submit_tool_outputs_and_poll(
                    thread_id=thread_id,
                    run_id=run.id,
                    tool_outputs=tool_outputs,
                )
                print("Responses from tools sent to the model")

            # Si el run se completó, obtener la respuesta del asistente
            if run.status == "completed":
                return await self.get_response(message_object, thread_id), tools_called

            # Si el run falló, devolver un mensaje de error
            return self.error_msg, False

        except Exception as exc:
            msg = f"Model response failed: {exc}"
            print(Fore.RED + msg)
            notifications.send_email("o.abel@jumotech.com", "Assistant error", msg)
            return self.error_msg, False

    async def cleanup_resources(self, thread_id: str) -> None:
        """Delete a thread"""

        await self.client.beta.threads.delete(thread_id)
