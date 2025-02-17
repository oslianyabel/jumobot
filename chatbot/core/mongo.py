from colorama import Fore, init
from motor.motor_asyncio import AsyncIOMotorClient  # Motor para MongoDB asíncrono
from openai import AsyncOpenAI

from chatbot.core import notifications
from chatbot.core.config import get_config

init(autoreset=True)

# MONGO_URI = "mongodb+srv://oslianyabel:atlas801*@cluster0.2wbttfz.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
# MONGO_URI = "mongodb://localhost:27017"
env_config = get_config()
MONGO_URI = env_config.DATABASE_URL

# Conexión asíncrona a MongoDB
client = AsyncIOMotorClient(MONGO_URI)
db = client["wa_jumo"]
threads_collection = db["threads"]

openai_client = AsyncOpenAI(api_key=env_config.OPENAI_API_KEY)


async def create_thread(user_id):
    thread = await openai_client.beta.threads.create()
    await threads_collection.update_one(
        {"user_id": user_id},
        {"$set": {"thread_id": thread.id, "interactions": 1, "messages": []}},
        upsert=True,
    )
    return thread.id


async def update_thread(user_id, thread_id):
    await threads_collection.update_one(
        {"user_id": user_id}, {"$set": {"thread_id": thread_id}}, upsert=True
    )


async def update_chat(user_id, role, message, tools_called="No"):
    try:
        if role == "Assistant":
            new_message = {
                "role": role,
                "message": message,
                "tools_called": tools_called,
            }
        else:
            new_message = {
                "role": role,
                "message": message,
            }

        await threads_collection.update_one(
            {"user_id": user_id}, {"$push": {"messages": new_message}}, upsert=True
        )
        return True

    except Exception as exc:
        msg = f"Error actualizando chat: {exc}"
        print(Fore.RED + msg)
        await notifications.send_email(
            "o.abel@jumotech.com", "Error updating the conversation in wa_jumo", msg
        )
        return False


async def get_chat(user_id):
    print("=" * 50, "Obteniendo Chats...", "=" * 50)

    thread = await threads_collection.find_one({"user_id": user_id})
    if thread:
        chats = thread["messages"]
        chats_str = ""

        for chat in chats:
            chats_str += f"{chat['role']}: {chat['message']} \n"

        print("Chats:", chats_str, sep="\n")
        return chats_str

    return False


async def get_thread(user_id):
    thread = await threads_collection.find_one({"user_id": user_id})
    if thread:
        interactions = int(thread["interactions"])
        await threads_collection.update_one(
            {"user_id": user_id},
            {"$set": {"interactions": interactions + 1}},
            upsert=True,
        )
        return thread["thread_id"]

    return None


async def get_interactions(user_id):
    thread = await threads_collection.find_one({"user_id": user_id})
    if thread:
        interactions = int(thread["interactions"])
        return interactions

    return 0
