import logging

import aiohttp
from aiohttp import BasicAuth

from chatbot.core.config import get_config

logger = logging.getLogger(__name__)


async def get_oauth_token():
    logger.debug("Getting Odoo token...")
    config = get_config()
    client_id = config.PUBLIC_ODOO_CLIENT_ID
    client_secret = config.PUBLIC_ODOO_CLIENT_SECRET
    PUBLIC_ODOO_URL = config.PUBLIC_ODOO_URL
    PUBLIC_TOKEN_PATH = config.PUBLIC_TOKEN_PATH

    token_url = f"{PUBLIC_ODOO_URL}{PUBLIC_TOKEN_PATH}"
    data = {"grant_type": "client_credentials"}
    auth = BasicAuth(client_id, client_secret)

    async with aiohttp.ClientSession() as session:
        async with session.post(token_url, data=data, auth=auth) as response:
            if response.status == 200:
                token = await response.json()
                return token["access_token"]
            else:
                raise Exception(f"Error al obtener el token OAuth: {response.text}")
