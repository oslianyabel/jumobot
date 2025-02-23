import asyncio
import logging
import time

from chatbot.core import functions
from chatbot.core.assistant import Assistant
from chatbot.core.config import get_config

logger = logging.getLogger(__name__)


class JumoAssistant(Assistant):
    def __init__(self):
        tools = {
            "clean_chat": functions.clean_chat,
            "create_lead": functions.create_lead,
            "create_partner": functions.create_partner,
            "get_partner": functions.get_partner,
            "presupuestos": functions.presupuestos,
            "sale_order_by_name": functions.sale_order_by_name,
        }
        config = get_config()
        super().__init__(
            name="Jumo_Assistant",
            assistant_id=config.JUMO_ASSISTANT_ID,
            functions=tools,
            api_key=config.OPENAI_API_KEY,
        )


async def main():
    thread_id = await assistant.create_thread()

    """ ans, status = assistant.submit_message("Hola, listame mis pedidos", "34936069261", thread_id)
	print(ans) """

    before = time.time()
    ans, status = await assistant.submit_message("Hola", thread_id)
    print(ans)
    print(time.time() - before)


if __name__ == "__main__":
    assistant = JumoAssistant()
    asyncio.run(main())
