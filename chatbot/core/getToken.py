import asyncio

import aiohttp
from aiohttp import BasicAuth


async def get_oauth_token():
    from chatbot.core.config import get_config

    env_config = get_config()
    client_id = env_config.PUBLIC_ODOO_CLIENT_ID
    client_secret = env_config.PUBLIC_ODOO_CLIENT_SECRET
    PUBLIC_ODOO_URL = env_config.PUBLIC_ODOO_URL
    PUBLIC_TOKEN_PATH = env_config.PUBLIC_TOKEN_PATH

    token_url = f"{PUBLIC_ODOO_URL}{PUBLIC_TOKEN_PATH}"
    data = {"grant_type": "client_credentials"}
    auth = BasicAuth(client_id, client_secret)

    async with aiohttp.ClientSession() as session:
        async with session.post(token_url, data=data, auth=auth) as response:
            if response.status == 200:
                return await response.json()
            else:
                raise Exception(f"Error al obtener el token OAuth: {response.text}")


if __name__ == "__main__":
    import os
    import sys

    sys.path.insert(
        0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    )

    async def main():
        try:
            token = await get_oauth_token()
            print("Token obtenido:", token)

        except Exception as e:
            print("Error", str(e))

    asyncio.run(main())
