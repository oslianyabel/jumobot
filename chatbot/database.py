import asyncio
import logging

import databases
import sqlalchemy
from databases.backends.common.records import Record
from openai import AsyncOpenAI
from sqlalchemy import ARRAY, DateTime, ForeignKey, Integer, String, func

from chatbot.core.config import get_config

logger = logging.getLogger(__name__)


class Repository:
    def __init__(self):
        config = get_config()

        self.openai_client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)

        self.metadata = sqlalchemy.MetaData()

        self.users_table = sqlalchemy.Table(
            "users",
            self.metadata,
            sqlalchemy.Column("phone", String, primary_key=True),
            sqlalchemy.Column("interactions", Integer, default=0),
            sqlalchemy.Column("thread_id", String, nullable=False),
            sqlalchemy.Column("name", String, nullable=True),
            sqlalchemy.Column("email", String, nullable=True),
            sqlalchemy.Column("permissions", String, default="user"),
        )

        self.message_table = sqlalchemy.Table(
            "messages",
            self.metadata,
            sqlalchemy.Column("id", Integer, primary_key=True, autoincrement=True),
            sqlalchemy.Column("user_phone", ForeignKey("users.phone"), nullable=False),
            sqlalchemy.Column("role", String, nullable=False),
            sqlalchemy.Column("message", String, nullable=False),
            sqlalchemy.Column("tools_called", ARRAY(String), nullable=True),
            sqlalchemy.Column("created_at", DateTime, default=func.now()),
        )

        self.engine = sqlalchemy.create_engine(config.DATABASE_URL)

        self.metadata.create_all(self.engine)

        self.database = databases.Database(
            config.DATABASE_URL, force_rollback=config.DB_FORCE_ROLL_BACK
        )

    async def get_user(self, phone: str) -> Record | None:
        logger.debug(f"Consultando usuario asociado al telefono {phone}")
        await self.database.connect()
        query = self.users_table.select().where(self.users_table.c.phone == phone)
        logger.debug(query)
        user = await self.database.fetch_one(query)
        await self.database.disconnect()
        return user

    async def create_user(
        self,
        phone: str,
        name: str | None = None,
        email: str | None = None,
        permissions: str = "user",
    ) -> dict | None:
        logger.debug(f"Creando usuario {phone}")
        await self.database.connect()
        thread = await self.openai_client.beta.threads.create()
        data = {
            "phone": phone,
            "thread_id": thread.id,
            "interactions": 0,
            "name": name,
            "email": email,
            "permissions": permissions,
        }
        query = self.users_table.insert().values(data)
        logger.debug(query)
        try:
            await self.database.execute(query)
        except Exception as exc:  # Llave duplicada
            logger.error(exc)
            data = None
        finally:
            await self.database.disconnect()
            return data

    async def set_user_data(self, phone: str, data: dict) -> bool:
        logger.debug(f"Actualizando datos de {phone}")
        await self.database.connect()
        query = (
            self.users_table.update()
            .where(self.users_table.c.phone == phone)
            .values(**data)
        )
        logger.debug(query)
        ans = True
        try:
            await self.database.execute(query)
        except Exception as exc:
            logger.error(exc)
            ans = False
        finally:
            await self.database.disconnect()
            return ans

    async def reset_thread(self, phone: str) -> str:
        logger.debug(f"Reseteando hilo de {phone}")
        await self.database.connect()
        thread = await self.openai_client.beta.threads.create()
        query = (
            self.users_table.update()
            .where(self.users_table.c.phone == phone)
            .values(thread_id=thread.id, interactions=0)
        )
        logger.debug(query)
        query2 = self.message_table.delete().where(
            self.message_table.c.user_phone == phone
        )
        logger.debug(query2)
        await asyncio.gather(
            self.database.execute(query),
            self.database.execute(query2),
        )
        await self.database.disconnect()
        return thread.id

    async def create_message(
        self, phone: str, role: str, message: str, tools_called: list[str] = []
    ) -> bool:
        logger.debug(f"Agregando mensaje de {role} en el chat de {phone}")
        await self.database.connect()
        data = {
            "user_phone": phone,
            "role": role,
            "message": message,
        }
        if role.lower() == "assistant":
            data["tools_called"] = tools_called

        query = self.message_table.insert().values(data)
        logger.debug(query)
        query2 = (
            self.users_table.update()
            .where(self.users_table.c.phone == phone)
            .values(interactions=self.users_table.c.interactions + 1)
        )
        logger.debug(query2)
        ans: bool = True
        try:
            await asyncio.gather(
                self.database.execute(query), self.database.execute(query2)
            )
        except Exception as exc:  # usuario no existe
            logger.error(exc)
            ans = False
        finally:
            await self.database.disconnect()
            return ans

    async def get_chat(self, phone: str) -> str:
        logger.debug(f"Consultando chat de {phone}")
        await self.database.connect()
        query = (
            self.message_table.select()
            .where(self.message_table.c.user_phone == phone)
            .order_by(self.message_table.c.created_at.asc())
        )
        logger.debug(query)
        data = await self.database.fetch_all(query)
        await self.database.disconnect()
        ans = ""
        for msg in data:
            ans += f"- {msg.role}: {msg.message}\n"

        return ans


if __name__ == "__main__":

    async def main():
        db = Repository()
        # get_chat
        data = await db.get_chat(phone="+5352045846")
        print(data)

        """ # create_message
        data = await db.create_message(
            phone="+5352045846", role="User", message="Hola4"
        )
        print(data) """

        """ # reset_thread
        data = await db.reset_thread(phone="+5352045846")
        print(data) """

        """ # get_user
        data = await db.get_user(phone="+5352045846")
        if data:
            print(data.interactions)
        else:
            print(data) """

        """ # create_user
        data = await db.create_user(phone="+5352045846")
        print(data) """

    asyncio.run(main())
