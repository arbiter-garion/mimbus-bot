import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy.sql import select

from aiogram.utils.i18n import gettext, I18n
from aiogram import Bot
from aiogram.utils.keyboard import InlineKeyboardBuilder

from mimbus import models
from mimbus.client import MimbusClient
from mimbus.middleware import AuthMiddleware
from mimbus.utils import session_scope, format_exception
from mimbus.config import Config


class AutomationWorker:
    logger = logging.getLogger('mimbus.automation')

    def __init__(self, bot: Bot, auth: AuthMiddleware, i18n: I18n):
        self.bot = bot
        self.client = MimbusClient()
        self.auth = auth
        self.i18n = i18n

    async def process_user(self, user: models.User):
        self.logger.debug('Processing user %s', user.id)
        user.last_assembled_at = datetime.now()
        user.notification_sent = False

        if (datetime.now() - user.auth_token_created_at).total_seconds() > Config.AUTH_TOKEN_TTL:
            if not await self.auth.auth_with_refresh_token(user):
                await self.bot.send_message(
                    user.id,
                    gettext(
                        'Canceling auto-assembly.\n'
                        'Your refresh token is expired. Please, re-authenticate.'
                    ),
                )
                return

        data = await self.client.load_all(uid=user.uid, auth_code=user.auth_token)
        stamina = data.updated.user_info.stamina

        modules_count = stamina // 20
        if modules_count > 0:
            await self.client.purchase_enkephalin_module(uid=user.uid, auth_code=user.auth_token, num=modules_count)

        await self.bot.send_message(
            user.id,
            gettext(
                '{num} modules have been assembled. '
            ).format(num=modules_count)
        )

    async def run_once(self):
        async with session_scope() as session:
            query = select(models.User).where(
                models.User.auto_assemble.is_(True),
                models.User.last_assembled_at < datetime.now() - timedelta(hours=7, minutes=45),
                models.User.last_assembled_at > datetime.now() - timedelta(hours=8),
                models.User.notification_sent.is_(False),
            )

            users_to_notify = (await session.execute(query)).scalars().all()
            for user in users_to_notify:
                with self.i18n.context(), self.i18n.use_locale(user.language):
                    self.logger.debug('Sending notification to user %s', user.id)

                    builder = InlineKeyboardBuilder()
                    builder.button(
                        text=gettext('Skip for 8 hours'), callback_data='postpone'
                    )

                    await self.bot.send_message(
                        user.id,
                        gettext(
                            'The modules will be assembled in 15 minutes. '
                            'Please, do not log into the game until the process is finished.'
                        ),
                        reply_markup=builder.as_markup(),
                    )
                    user.notification_sent = True

            query = select(models.User).where(
                models.User.auto_assemble.is_(True),
                models.User.last_assembled_at < datetime.now() - timedelta(hours=8),
            )
            users_to_process = (await session.execute(query)).scalars().all()
            for user in users_to_process:
                with self.i18n.context(), self.i18n.use_locale(user.language):
                    try:
                        await self.process_user(user)
                    except Exception as e:
                        self.logger.error('Unable to process user %s. Error: %s', user.id, format_exception(e, with_traceback=True))

                        await self.bot.send_message(
                            user.id,
                            gettext(
                                'Failed to assemble modules. Contact admin.'
                            ),
                        )

    async def loop(self):
        while True:
            await self.run_once()
            await asyncio.sleep(60)

    def start(self):
        self.logger.debug('Starting automation worker')
        asyncio.create_task(self.loop())
