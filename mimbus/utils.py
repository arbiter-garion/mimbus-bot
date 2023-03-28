import asyncio
import contextlib
import functools
import json
import struct
import sys
import traceback

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

from mimbus.config import Config
from mimbus.exceptions import SteamException
from mimbus import structures


Base = declarative_base()
engine = create_async_engine(Config.DB_URL, echo=Config.DEBUG)


async def generate_token(credentials: dict) -> structures.SteamTokenResponse:
    reader, writer = await asyncio.open_unix_connection('/tmp/mimbus-token.sock')

    req = json.dumps({'credentials': credentials}).encode()
    writer.write(struct.pack('>I', len(req)) + req)

    length = struct.unpack('>I', await reader.read(4))[0]
    response = json.loads((await reader.read(length)).decode())

    if err := response.get('error'):
        raise SteamException(err)

    if response.get('guard'):

        async def callback(code: str):
            request = json.dumps({'code': code}).encode()
            writer.write(struct.pack('>I', len(request)) + request)

            _length = struct.unpack('>I', await reader.read(4))[0]
            _response = json.loads((await reader.read(_length)).decode())

            if _err := _response.get('error'):
                raise SteamException(_err)

            if _response.get('guard'):
                return None, callback

            return structures.SteamTokenResponse(
                token=_response['token'],
                refresh_token=_response.get('refreshToken'),
                callback=None
            )

        return structures.SteamTokenResponse(
            token=None,
            refresh_token=None,
            callback=callback
        )

    return structures.SteamTokenResponse(
        token=response['token'],
        refresh_token=response.get('refreshToken'),
        callback=None,
    )


def retry(times: int = 6, exceptions: tuple = (Exception,)):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            for _ in range(times - 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions:
                    continue

            return await func(*args, **kwargs)

        return wrapper

    return decorator


@contextlib.asynccontextmanager
async def session_scope(autocommit=True):
    async with AsyncSession(engine) as session:
        try:
            yield session

            if autocommit:
                await session.commit()

        except:
            await session.rollback()
            raise


def generate_session():
    return AsyncSession(engine)


async def prepare_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


def get_traceback_string(exception):
    if hasattr(exception, '__traceback__'):
        tb_strings = traceback.format_tb(exception.__traceback__)
    else:
        tb_strings = traceback.format_exception(*sys.exc_info())
    return ''.join(tb_strings)


def format_exception(e, with_traceback=False):
    if hasattr(e, '__module__'):
        exc_string = u'{}.{}: {}'.format(e.__module__, e.__class__.__name__, e)
    else:
        exc_string = u'{}: {}'.format(e.__class__.__name__, e)

    if with_traceback:
        traceback_string = ':\n' + get_traceback_string(exception=e)
    else:
        traceback_string = ''

    return u'{}{}'.format(exc_string, traceback_string)
