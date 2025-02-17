import asyncio

from chatbot.core import functions
from chatbot.core.assistant import Assistant
from chatbot.core.config import get_config


class JumoAssistant(Assistant):
    def __init__(self):
        self.tools = {
            "clean_chat": functions.clean_chat,
            "create_lead": functions.create_lead,
            "create_partner": functions.create_partner,
            "get_partner": functions.get_partner,
            "presupuestos": functions.presupuestos,
            "sale_order_by_name": functions.sale_order_by_name,
        }
        super().__init__("Jumo_Assistant", get_config().JUMO_ASSISTANT_ID, self.tools)


async def main():
    thread_id = await assistant.create_thread()

    """ ans, status = assistant.submit_message("Hola, listame mis pedidos", "34936069261", thread_id)
	print(ans) """

    ans, status = await assistant.submit_message(
        "Hola, créame una cuenta. Me llamo Osliani Abel", "34936069261", thread_id
    )

    print(ans)


if __name__ == "__main__":
    assistant = JumoAssistant()
    asyncio.run(main())
