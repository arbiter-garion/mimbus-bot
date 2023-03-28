import aiohttp
import asyncio
import bisect
import contextlib
import json
import logging
import mmh3

from mimbus.config import Config


def int_to_bytes(x: int) -> bytes:
    return x.to_bytes((x.bit_length() + 7) // 8, 'big')


class ProxyStorage:
    logger = logging.getLogger('mimbus.proxy')

    def __init__(self):
        self.proxies: dict[int, str | None] = {}
        self.indexes: list[int] = []

    async def load(self):
        proxies = {}
        indexes = []

        if Config.USE_PRIVATE_PROXY:
            with open('endpoints.json', 'r') as f:
                resp = json.load(f)
        else:
            async with aiohttp.ClientSession() as session:
                async with session.get('https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/json/proxies.json') as response:
                    resp = json.loads(await response.text())['http']

        for proxy in resp:
            host = f'http://{proxy}'
            h = mmh3.hash(host)
            proxies[h] = host
            indexes.append(h)

        indexes.sort()

        self.proxies = proxies
        self.indexes = indexes
        self.logger.debug('Loaded %s proxies', len(proxies))

    async def loop(self):
        if self.proxies:
            await asyncio.sleep(60 * 60)

        while True:
            with contextlib.suppress(Exception):
                await self.load()

            await asyncio.sleep(60 * 60)

    def start(self):
        self.logger.debug('Starting proxy storage')
        asyncio.create_task(self.loop())

    def remove(self, uid: int):
        result = self.proxies[self.indexes[self.get_index(uid)]]
        if result is None:
            return self.remove(mmh3.hash(int_to_bytes(abs(uid))))

        self.proxies[self.indexes[self.get_index(uid)]] = None

    def get_index(self, uid: int) -> int:
        if not self.proxies:
            return 0

        index = bisect.bisect_left(self.indexes, mmh3.hash(int_to_bytes(abs(uid))))
        if index == len(self.indexes):
            index = 0
        return index

    def get(self, uid: int) -> str:
        index = self.get_index(uid)

        result = self.proxies[self.indexes[index]]
        if result is None:
            return self.get(mmh3.hash(int_to_bytes(abs(uid))))
        return result


storage = ProxyStorage()
