import base64
import logging
import typing as tp

from aiogram import BaseMiddleware, Bot
from aiogram.types import Message, ReplyKeyboardRemove, TelegramObject
from aiogram.utils.i18n import gettext, I18nMiddleware
from async_lru import alru_cache
from datetime import datetime
from sqlalchemy.sql import select

from mimbus import models, structures
from mimbus.client import MimbusClient
from mimbus.config import Config
from mimbus.exceptions import SteamException, UserException
from mimbus.state import AuthState
from mimbus.utils import session_scope, generate_token, format_exception

Handler = tp.Callable[[Message, dict[str, tp.Any]], tp.Awaitable[tp.Any]]


class SessionMiddleware(BaseMiddleware):
    async def __call__(self, handler: Handler, event: Message, data: dict[str, tp.Any]):
        async with session_scope() as session:
            data['session'] = session
            return await handler(event, data)


class UserMiddleware(BaseMiddleware):
    logger = logging.getLogger('mimbus.middleware.user')

    async def __call__(self, handler: Handler, event: Message, data: dict[str, tp.Any]):
        if not (session := data.get('session')):
            raise RuntimeError('SessionMiddleware is not enabled')

        query = select(models.User).where(models.User.id == event.from_user.id)
        user = (await session.execute(query)).scalar_one_or_none()

        if not user:
            self.logger.info('New user: %s', event.from_user.username)
            user = models.User(id=event.from_user.id, tg_name=event.from_user.username)
            session.add(user)

        data['user'] = user
        return await handler(event, data)


class AuthMiddleware(BaseMiddleware):
    logger = logging.getLogger('mimbus.middleware.auth')

    def __init__(self):
        self.client = MimbusClient()

    async def auth_with_refresh_token(self, user: models.User) -> bool:
        try:
            resp = await generate_token({'refreshToken': user.refresh_token})
        except SteamException:
            user.refresh_token = None
            user.auth_token = None
            return False

        if resp.token is None:
            user.refresh_token = None
            user.auth_token = None
            return False

        try:
            sign_in: structures.SteamLoginResponse = await self.client.sign_in(resp.token, uid=user.uid)
        except Exception as e:
            self.logger.error('Unable to get the auth token. Error: %s', format_exception(e, with_traceback=True))

            user.refresh_token = None
            user.auth_token = None
            return False

        self.logger.debug('Token granted for user %s', user.tg_name)

        user.auth_token = sign_in.result.user_auth.auth_code
        user.uid = sign_in.result.user_auth.uid
        user.auth_token_created_at = datetime.now()
        return True

    async def __call__(self, handler: Handler, event: Message, data: dict[str, tp.Any]):
        if not (user := data.get('user')):
            raise RuntimeError('UserMiddleware is not enabled')

        if (
            user.refresh_token and
            (
                not user.auth_token or
                (datetime.now() - user.auth_token_created_at).total_seconds() > Config.AUTH_TOKEN_TTL
            )
        ):
            if not await self.auth_with_refresh_token(user):
                await event.answer(
                    gettext(
                        'Your refresh token is expired. Please, re-authenticate.'
                    ),
                    reply_markup=ReplyKeyboardRemove(),
                )

                await data['state'].set_state(AuthState.waiting_for_steam_name)
                await event.answer(
                    gettext(
                        '<b>Please, enter your Steam name:</b>'
                    ),
                    reply_markup=ReplyKeyboardRemove(),
                )

                return

        return await handler(event, data)


class ExceptionMiddleware(BaseMiddleware):
    logger = logging.getLogger('mimbus.middleware.exception')

    def __init__(self, bot: Bot):
        self.bot = bot

    async def send_to_escalation_chat(self, event: Message, data: dict[str, tp.Any], e: Exception):
        await self.bot.send_message(
            Config.ESCALATION_CHAT_ID,
            f'User: {data["user"].id}\n'
            f'Message: {event.text}\n\n'
            f'Unhandled exception: {format_exception(e, with_traceback=True)}',
        )

    async def __call__(self, handler: Handler, event: Message, data: dict[str, tp.Any]):
        try:
            return await handler(event, data)
        except UserException as e:
            self.logger.info('User exception: %s', format_exception(e, with_traceback=True))
            await event.answer(str(e.MESSAGE))
        except Exception as e:
            self.logger.error('Unhandled exception: %s', format_exception(e, with_traceback=True))
            if Config.ESCALATION_CHAT_ID is not None:
                await self.send_to_escalation_chat(event, data, e)

            await event.answer(gettext('An error occurred. Please, try again later.'))


class LanguageMiddleware(I18nMiddleware):
    async def get_locale(self, event: TelegramObject, data: dict[str, tp.Any]) -> str:
        user = data.get('user')
        if user and user.language:
            return user.language

        return 'en'


class StatusMiddleware(BaseMiddleware):
    main_group_id = -2 * 773 * 7193 * 90073
    main_group_link = base64.b64decode('aHR0cHM6Ly90Lm1lL2xjYl9ndWlkZXNfcnU=').decode()

    def __init__(self, bot: Bot):
        self.bot = bot

    @alru_cache(ttl=60 * 60)
    async def get_status(self, user_id: int) -> str:
        res = await self.bot.get_chat_member(self.main_group_id, user_id)
        return res.status

    async def __call__(self, handler: Handler, event: Message, data: dict[str, tp.Any]):
        status = await self.get_status(event.from_user.id)
        if status == 'left':
            self.get_status.cache_invalidate(event.from_user.id)
            await event.answer(
                gettext(
                    'Please, subscribe to our group to continue.\n'
                    '{link}'
                ).format(link=self.main_group_link),
                reply_markup=ReplyKeyboardRemove(),
            )
            return

        data['status'] = status

        return await handler(event, data)


class AdminOnlyMiddleware(BaseMiddleware):
    async def __call__(self, handler: Handler, event: Message, data: dict[str, tp.Any]):
        if Config.ADMIN_ONLY and data.get('status') not in ('creator', 'administrator'):
            await event.answer(gettext(
                'Bot is temporarily closed for maintenance. '
                'Please, try again later.'
            ))
            return

        return await handler(event, data)
