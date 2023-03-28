import aiohttp
import aiohttp.client_exceptions

import asyncio
import base64
import random
import functools
import logging

from mimbus import structures, proxy, exceptions, utils


def with_proxy(func):
    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        uid = kwargs.get('uid') or 1  # fixme
        proxy_host = proxy.storage.get(uid)

        self.logger.debug('Using proxy: %s for uid %s', proxy_host or 'no proxy', uid)

        try:
            return await func(self, *args, **kwargs, proxy_host=proxy_host)
        except (
                asyncio.TimeoutError,
                aiohttp.client_exceptions.ServerDisconnectedError,
                aiohttp.client_exceptions.ClientConnectorError
        ):
            proxy.storage.remove(uid)
            self.logger.debug('Proxy %s is not working for uid %s', proxy_host, uid)
            raise exceptions.RetryException('Failed to connect to the server.')

    return wrapper


class MimbusClient:
    BASE_URL = base64.b64decode('aHR0cHM6Ly93d3cubGltYnVzY29tcGFueWFwaS0yLmNvbQ==').decode('utf-8')  # Mimbus url

    HEADERS = {
        'Content-Type': 'application/json',
        'User-Agent': 'UnityPlayer/2021.3.0f1 (UnityWebRequest/1.0, libcurl/7.80.0-DEV)',
        'Accept': '*/*',
        'Accept-Encoding': 'deflate, gzip',
        'X-Unity-Version': '2021.3.0f1',
    }

    VERSION = '1.3.0'
    DATA_VERSION = 26

    logger = logging.getLogger('mimbus.client')

    @staticmethod
    def check_for_status(data: dict) -> None:
        if data.get('state') != 'ok':
            raise exceptions.APIException(f'Failed to load data. Status code: {data.get("state")}')

    @utils.retry(exceptions=(exceptions.RetryException,))
    @with_proxy
    async def sign_in(self, steam_token: str, proxy_host: str | None = None, uid: int | None = None) -> structures.SteamLoginResponse:
        _ = uid
        timeout = aiohttp.ClientTimeout(total=10)

        async with aiohttp.ClientSession(headers=self.HEADERS, timeout=timeout) as session:
            async with session.post(
                f'{self.BASE_URL}/login/SignInAsSteam',
                json={
                    'userAuth': {
                        'uid': 0,
                        'dbid': 0,
                        'authCode': '',
                        'version': self.VERSION,
                        'synchronousDataVersion': self.DATA_VERSION
                    },
                    'parameters': {
                        'steamToken': steam_token,
                        'version': self.VERSION,
                        'deviceModel': 'Desktop'
                    },
                },
                proxy=proxy_host,
            ) as response:
                data = await response.json()
                self.check_for_status(data)
                return structures.SteamLoginResponse.parse_obj(data)

    @utils.retry(exceptions=(exceptions.RetryException,))
    @with_proxy
    async def load_all(self, uid: int, auth_code: str, proxy_host: str | None = None) -> structures.LoadAllResponse:
        timeout = aiohttp.ClientTimeout(total=10)

        async with aiohttp.ClientSession(headers=self.HEADERS, timeout=timeout) as session:
            async with session.post(
                f'{self.BASE_URL}/api/LoadUserDataAll',
                json={
                    'userAuth': {
                        'uid': uid,
                        'dbid': 0,
                        'authCode': auth_code,
                        'version': self.VERSION,
                        'synchronousDataVersion': self.DATA_VERSION
                    },
                    'parameters': {},
                },
                proxy=proxy_host,
            ) as response:
                data = await response.json()
                self.check_for_status(data)
                return structures.LoadAllResponse.parse_obj(data)

    @utils.retry(exceptions=(exceptions.RetryException,))
    @with_proxy
    async def purchase_enkephalin_module(self, uid: int, auth_code: str, num: int, proxy_host: str | None = None) -> structures.MimbusBaseResponse:
        timeout = aiohttp.ClientTimeout(total=10)

        async with aiohttp.ClientSession(headers=self.HEADERS, timeout=timeout) as session:
            async with session.post(
                f'{self.BASE_URL}/api/PurchaseEnkephalinModule',
                json={
                    'userAuth': {
                        'uid': uid,
                        'dbid': 0,
                        'authCode': auth_code,
                        'version': self.VERSION,
                        'synchronousDataVersion': self.DATA_VERSION
                    },
                    'parameters': {
                        'num': num
                    },
                },
                proxy=proxy_host,
            ) as response:
                data = await response.json()
                self.check_for_status(data)
                return structures.MimbusBaseResponse.parse_obj(data)

    @utils.retry(exceptions=(exceptions.RetryException,))
    @with_proxy
    async def enter_exp_dungeon(self, uid: int, dungeon_id: int, auth_code: str, proxy_host: str | None = None) -> structures.MimbusBaseResponse:
        timeout = aiohttp.ClientTimeout(total=10)

        async with aiohttp.ClientSession(headers=self.HEADERS, timeout=timeout) as session:
            async with session.post(
                f'{self.BASE_URL}/api/EnterExpDungeon',
                json={
                    'userAuth': {
                        'uid': uid,
                        'dbid': 0,
                        'authCode': auth_code,
                        'version': self.VERSION,
                        'synchronousDataVersion': self.DATA_VERSION
                    },
                    'parameters': {
                        'dungeonid': dungeon_id
                    },
                },
                proxy=proxy_host,
            ) as response:
                data = await response.json()
                self.check_for_status(data)
                return structures.MimbusBaseResponse.parse_obj(data)

    @utils.retry(exceptions=(exceptions.RetryException,))
    @with_proxy
    async def exit_exp_dungeon(self, uid: int, auth_code: str, proxy_host: str | None = None) -> structures.MimbusBaseResponse:
        timeout = aiohttp.ClientTimeout(total=10)

        async with aiohttp.ClientSession(headers=self.HEADERS, timeout=timeout) as session:
            async with session.post(
                f'{self.BASE_URL}/api/ExitExpDungeon',
                json={
                    'userAuth': {
                        'uid': uid,
                        'dbid': 0,
                        'authCode': auth_code,
                        'version': self.VERSION,
                        'synchronousDataVersion': self.DATA_VERSION
                    },
                    'parameters': {
                        'formationId': 0,
                        'isWin': 1,
                        'supportCharacterId': -1,
                        'supportParticipate': False,
                        'battlePassParameters': {
                            'enemyKillCount': 10,
                            'abnormalityKillCount': 0,
                            'isUsedDailyChar': True,
                            'isUsedSeasonEgo': False,
                            'isUsedSeasonAnnouncer': False
                        },
                    },
                },
                proxy=proxy_host,
            ) as response:
                data = await response.json()
                self.check_for_status(data)
                return structures.MimbusBaseResponse.parse_obj(data)

    @utils.retry(exceptions=(exceptions.RetryException,))
    @with_proxy
    async def unseal_mails(self, uid: int, mail_id: int, auth_code: str, proxy_host: str | None = None) -> structures.MimbusBaseResponse:
        timeout = aiohttp.ClientTimeout(total=10)

        async with aiohttp.ClientSession(headers=self.HEADERS, timeout=timeout) as session:
            async with session.post(
                f'{self.BASE_URL}/api/UnsealMails',
                json={
                    'userAuth': {
                        'uid': uid,
                        'dbid': 0,
                        'authCode': auth_code,
                        'version': self.VERSION,
                        'synchronousDataVersion': self.DATA_VERSION
                    },
                    'parameters': {
                        'mailIds': [mail_id],
                    },
                },
                proxy=proxy_host,
            ) as response:
                data = await response.json()
                self.check_for_status(data)
                return structures.MimbusBaseResponse.parse_obj(data)
