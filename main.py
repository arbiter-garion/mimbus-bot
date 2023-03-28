import asyncio
import logging
import random
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import select

from mimbus import proxy, structures, models
from mimbus.automation import AutomationWorker
from mimbus.client import MimbusClient
from mimbus.config import Config
from mimbus.exceptions import SteamException
from mimbus.middleware import (
    SessionMiddleware,
    UserMiddleware,
    AuthMiddleware,
    ExceptionMiddleware,
    LanguageMiddleware,
    StatusMiddleware,
    AdminOnlyMiddleware,
)
from mimbus.state import AuthState, DungeonState, AdminState
from mimbus.utils import generate_token, prepare_db, session_scope

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, Text
from aiogram.fsm.context import FSMContext
from aiogram.utils.i18n import gettext, I18n
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import (
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    CallbackQuery,
)


client = MimbusClient()

bot = Bot(token=Config.BOT_TOKEN, parse_mode='HTML')
router = Router()

version = '0.0.1'

logger = logging.getLogger('mimbus')

guard_callbacks = {}  # fixme: temp storage required here!


def get_keyboard(user: models.User) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text=gettext('📦 Assemble modules')),
                    KeyboardButton(text=gettext('🏰 Enter EXP Dungeon')),
                ],
                [
                    KeyboardButton(
                        text=gettext('🔁 Auto Assemble {status}').format(status=('✅' if user.auto_assemble else '❌'))
                    ),
                ]
            ]
        )


@router.message(Command('start'))
async def start(message: Message, state: FSMContext, user: models.User):
    if not user.language:
        await language(message, state)
    else:
        await main_menu(message, state, user)


@router.message(Command('language'))
async def language(message: Message, state: FSMContext):
    await state.set_state(AuthState.waiting_for_language)
    await message.answer(
        gettext(
            'Mimbus Bot {version}.\n'
            'This bot is used to manage your Mimbus account. Please, select your language:\n'
        ).format(version=version),
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text='English'),
                    KeyboardButton(text='Русский'),
                ],
            ],
            resize_keyboard=True,
        ),
    )


# noinspection PyShadowingNames
@router.message(AuthState.waiting_for_language, F.text.casefold() == 'english')
async def english_language(message: Message, state: FSMContext, user: models.User, i18n: I18n):
    await state.clear()
    user.language = 'en'
    i18n.use_locale('en')
    await main_menu(message, state, user)


# noinspection PyShadowingNames
@router.message(AuthState.waiting_for_language, F.text.casefold() == 'русский')
async def russian_language(message: Message, state: FSMContext, user: models.User, i18n: I18n):
    await state.clear()
    user.language = 'ru'
    i18n.use_locale('ru')
    await main_menu(message, state, user)


@router.message(AuthState.waiting_for_language)
async def unknown_language(message: Message):
    await message.answer(
        gettext('Unknown language. Please, select your language:\n'),
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text='English'),
                    KeyboardButton(text='Русский'),
                ],
            ],
            resize_keyboard=True,
        ),
    )


@router.message(Command('main'))
async def main_menu(message: Message, state: FSMContext, user: models.User):
    if not user.refresh_token:
        await state.set_state(AuthState.waiting_for_steam_name)
        await message.answer(
            gettext(
                '<b>Please, enter your Steam name:</b>'
            ),
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    await state.clear()
    response = await message.answer(
        gettext('Loading Data...'),
        reply_markup=ReplyKeyboardRemove(),
    )

    data: structures.LoadAllResponse = await client.load_all(uid=user.uid, auth_code=user.auth_token)
    user.public_uid = data.result.profile.public_uid

    await response.delete()
    await message.answer(
        gettext(
            'Welcome, {name}! LVL {level}\n'
            'Your Enkephalin: {stamina}\n'
        ).format(
            name=data.result.profile.public_uid,
            level=data.result.profile.level,
            stamina=data.updated.user_info.stamina,
        ),
        reply_markup=get_keyboard(user),
    )


@router.message(Text(contains='📦'))
async def assemble_modules(message: Message, user: models.User):
    await message.answer(
        gettext(
            'Assembling modules...'
        ),
    )

    await client.purchase_enkephalin_module(uid=user.uid, auth_code=user.auth_token, num=1)
    await message.answer(
        gettext(
            'Modules assembled!'
        ),
    )


@router.message(Text(contains='🏰'))
async def enter_exp_dungeon(message: Message, state: FSMContext):
    await state.set_state(DungeonState.dungeon_id)
    await message.answer(
        gettext(
            'Select dungeon type:'
        ),
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text=gettext('Dungeon 1')),
                    KeyboardButton(text=gettext('Dungeon 2')),
                    KeyboardButton(text=gettext('Dungeon 3')),
                ],
            ]
        ),
    )


@router.message(DungeonState.dungeon_id)
async def handle_dungeon_id(message: Message, state: FSMContext, user: models.User):
    dungeon_id = int(message.text.split(' ')[-1])
    await state.clear()

    await message.answer(
        gettext(
            'Entering dungeon...'
        ),
        reply_markup=ReplyKeyboardRemove(),
    )

    await client.enter_exp_dungeon(uid=user.uid, auth_code=user.auth_token, dungeon_id=dungeon_id)

    await message.answer(
        gettext(
            'Battle in progress, please wait...'
        ),
    )
    await asyncio.sleep(random.uniform(5 * 60, 7 * 60))
    await client.exit_exp_dungeon(uid=user.uid, auth_code=user.auth_token)

    await message.answer(
        gettext(
            'Battle finished!'
        ),
    )

    await main_menu(message, state, user)


@router.message(AuthState.waiting_for_steam_name)
async def steam_name(message: Message, state: FSMContext, user: models.User):
    user.steam_name = message.text
    await state.set_state(AuthState.waiting_for_steam_password)
    await message.answer(
        gettext(
            '<b>Please, enter your Steam password:</b>\n'
            '\n'
            'Common questions:\n'
            'Q: Why do you need my Steam password?\n'
            'A: We need it to get your Mimbus one-time auth token. We do not store your password. '
            'This bot is open-source and you can check it yourself.\n'
            '\n'
            'Q: Can I log out this bot from steam?\n'
            'A: Yes, you can. Just use /logout command. '
            'Alternatively you can use `Log out from every device` button in steam.\n'
            '\n'
            'Q: Can I get banned for using this bot?\n'
            'A: <b>Yes</b>, you can. But we believe that probability of this is very low.'
            'We insure that every connection use separated proxy and we manually '
            'check every Mimbus update for potential problems.\n'

        ),
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(AuthState.waiting_for_steam_password)
async def steam_password(message: Message, state: FSMContext, user: models.User):
    await message.delete()
    await message.answer(gettext('Authenticating...'))

    try:
        resp = await generate_token({'accountName': user.steam_name, 'password': message.text, 'rememberPassword': True})

        if resp.token is None:
            await state.set_state(AuthState.waiting_for_guard_code)
            await message.answer(
                gettext(
                    '<b>Please, enter your Steam guard code:</b>'
                ),
                reply_markup=ReplyKeyboardRemove(),
            )

            guard_callbacks[message.from_user.id] = resp.callback
            return
        else:
            user.refresh_token = resp.refresh_token

    except SteamException as e:
        await message.answer(
            gettext(
                'Unable to get the token. Wrong password? \n'
                'Error: {error}'
            ).format(error=e),
            reply_markup=ReplyKeyboardRemove(),
        )

    await state.clear()
    await auth.auth_with_refresh_token(user)
    await main_menu(message, state, user)


@router.message(AuthState.waiting_for_guard_code)
async def steam_guard_code(message: Message, state: FSMContext, user: models.User):
    callback = guard_callbacks.get(message.from_user.id)
    if callback is None:
        await state.clear()
        await message.answer(
            gettext(
                'How did we get here?'
            ),
            reply_markup=ReplyKeyboardRemove(),
        )

    await message.answer(
        gettext(
            'Authenticating...'
        ),
    )

    resp = await callback(message.text)

    if resp.token is None:
        guard_callbacks[message.from_user.id] = resp.callback
        await message.answer(
            gettext(
                'Wrong Guard code. Please, try again: '
            ),
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    user.refresh_token = resp.refresh_token

    await state.clear()
    await auth.auth_with_refresh_token(user)
    await main_menu(message, state, user)


@router.message(Command('relogin'))
async def reload(message: Message, user: models.User):
    user.auth_token = None
    await message.answer(gettext('Done!'))


@router.message(Command('logout'))
async def logout(message: Message, user: models.User):
    user.refresh_token = None
    user.auth_token = None

    await message.answer(
        gettext(
            'You have been successfully logged out.'
        ),
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(Command('cancel'))
async def cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        gettext(
            'Canceled'
        ),
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(Text(contains='🔁'))
async def auto_assemble(message: Message, user: models.User):
    user.auto_assemble = not user.auto_assemble
    await message.answer(
        gettext(
            'Auto assemble has been {status}'
        ).format(status=(gettext('enabled') if user.auto_assemble else gettext('disabled'))),
        reply_markup=get_keyboard(user),
    )


@router.message(Command('broadcast'))
async def broadcast(message: Message, state: FSMContext, status: str):
    if status not in ('creator', 'administrator'):
        return

    await state.set_state(AdminState.broadcast_message)
    await message.answer(
        'Please, enter your message:'
    )


@router.message(AdminState.broadcast_message)
async def broadcast_message(message: Message, state: FSMContext, session: AsyncSession):
    query = select(models.User)
    users = (await session.execute(query)).scalars().all()

    for user in users:
        await bot.send_message(
            user.id,
            message.text,
        )

    await state.clear()
    await message.answer(
        'Done!'
    )


@router.callback_query(Text(contains='postpone'))
async def postpone(callback: CallbackQuery):
    async with session_scope() as session:
        query = select(models.User).where(models.User.id == callback.from_user.id)
        user = (await session.execute(query)).scalar_one()

        with i18n.context(), i18n.use_locale(user.language):
            user.last_assembled_at = datetime.now()
            user.notification_sent = False

            builder = InlineKeyboardBuilder()
            await callback.message.edit_text(
                gettext(
                    'Waiting for 8 hours...'
                ),
                reply_markup=builder.as_markup(),
            )


async def main():
    dp = Dispatcher()
    dp.include_router(router)

    await proxy.storage.load()
    proxy.storage.start()

    AutomationWorker(bot, auth, i18n).start()

    await prepare_db()
    await dp.start_polling(bot)


if __name__ == '__main__':
    i18n = I18n(path='locales', default_locale='en', domain='messages')
    auth = AuthMiddleware()

    router.message.middleware(SessionMiddleware())
    router.message.middleware(UserMiddleware())
    router.message.middleware(LanguageMiddleware(i18n))
    router.message.middleware(ExceptionMiddleware(bot))
    router.message.middleware(StatusMiddleware(bot))
    router.message.middleware(AdminOnlyMiddleware())
    router.message.middleware(auth)

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s %(levelname)6s - %(name)s - %(message)s',
    )
    asyncio.run(main())
