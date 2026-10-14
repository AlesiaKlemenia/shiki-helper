"""Базовые команды бота: /start, /help, /menu."""
from __future__ import annotations

import logging
from typing import Any
from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards import get_persistent_main_keyboard
from app.bot.utils import escape_md_v2, escape_md_v2_url
from app.db.models import User

logger = logging.getLogger(__name__)
common_router = Router(name="common_router")


@common_router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession) -> None:
    """Обработчик команды /start."""
    logger.info(
        "[CMD] /start вызван от user_id=%s",
        message.from_user.id if message.from_user else "unknown",
    )
    if not message.from_user:
        return

    user_id = message.from_user.id
    username = message.from_user.username

    user = await session.get(User, user_id)
    if user is None:
        user = User(
            telegram_id=user_id,
            username=username,
            timezone="Europe/Moscow",
        )
        session.add(user)
        await session.commit()
        logger.info("Зарегистрирован новый пользователь %d (@%s)", user_id, username)

    first_name_safe = escape_md_v2(message.from_user.first_name)
    text = (
        f"👋 *Добро пожаловать в Shiki\\-Helper, {first_name_safe}\\!*\n\n"
        "Я помогаю отслеживать выход новых серий аниме на Shikimori и синхронизирую "
        "статусы с вашими Google Таблицами рабочих релизов\\.\n\n"
        "Команды:\n"
        "• */menu* — главное интерактивное меню\n"
        "• */sync* — проверить обновления серий прямо сейчас\n"
        "• */help* — подробная справка по боту"
    )
    await message.answer(
        text,
        reply_markup=get_persistent_main_keyboard(),
        parse_mode="MarkdownV2",
    )


@common_router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Обработчик команды /help."""
    text = (
        "📖 *Справка по командам Shiki\\-Helper:*\n\n"
        "• */start* — запустить бота и обновить профиль\n"
        "• */menu* — главное интерактивное меню управления\n"
        "• */auth* — получить ссылку для привязки Google Таблицы\n"
        "• */sync* — запустить немедленную сверку серий и получить дайджест\n"
        "• */help* — показать эту справку\n\n"
        "_Следите за новыми сериями без ручной рутины\\! 🚀_"
    )
    await message.answer(
        text,
        reply_markup=get_persistent_main_keyboard(),
        parse_mode="MarkdownV2",
    )


@common_router.message(Command("auth"))
async def cmd_auth(message: Message) -> None:
    """Обработчик команды /auth — генерация ссылки Google OAuth."""
    from app.config import settings
    from app.clients.google_sheets import GoogleOAuthHelper

    try:
        helper = GoogleOAuthHelper(
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            encryption_key=settings.encryption_key,
        )
        auth_url = helper.get_authorization_url()
        safe_auth_url = escape_md_v2_url(auth_url)
        text = (
            "🔐 *Авторизация Google Sheets:*\n\n"
            "1\\. Перейдите по ссылке ниже и предоставьте доступ к таблицам Google:\n"
            f"[👉 *Нажмите сюда для авторизации в Google*]({safe_auth_url})\n\n"
            "2\\. Скопируйте полученный код авторизации от Google\\.\n"
            "3\\. Отправьте его боту командой: `/code ВАШ_КОД`\n"
            "4\\. Затем привяжите таблицу командой: `/sheet ССЫЛКА_ИЛИ_ID_ТАБЛИЦЫ`"
        )
        await message.answer(text, parse_mode="MarkdownV2", disable_web_page_preview=True)
    except Exception as exc:
        logger.error("Ошибка при формировании Google OAuth ссылки: %s", exc)
        safe_exc = escape_md_v2(str(exc))
        await message.answer(
            f"⚠️ *Ошибка формирования ссылки авторизации:*\n`{safe_exc}`",
            parse_mode="MarkdownV2",
        )


@common_router.message(Command("menu"))
async def cmd_menu(message: Message) -> None:
    """Обработчик команды /menu — главное меню бота."""
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📋 Мои тайтлы", callback_data="menu_open_titles"),
            ],
            [
                InlineKeyboardButton(text="⚙️ Настройки (Онбординг)", callback_data="menu_open_settings"),
                InlineKeyboardButton(text="🔄 Синхронизация", callback_data="menu_trigger_sync"),
            ],
        ]
    )

    text = (
        "🎛 *Главное меню Shiki\\-Helper*\n\n"
        "Выберите интересующий раздел управления:"
    )
    await message.answer(text, reply_markup=keyboard, parse_mode="MarkdownV2")


@common_router.message(Command("code"))
async def cmd_code(message: Message, session: AsyncSession) -> None:
    """Обработчик команды /code — обмен кода на refresh_token и сохранение в БД."""
    from app.config import settings
    from app.clients.google_sheets import GoogleOAuthHelper
    from app.db.models import GoogleCredentials
    import json

    if not message.from_user:
        return

    text_parts = (message.text or "").strip().split(maxsplit=1)
    if len(text_parts) < 2:
        await message.answer("⚠️ Пожалуйста, укажите код после команды:\n`/code ВАШ_КОД`", parse_mode="MarkdownV2")
        return

    auth_code = text_parts[1].strip()
    user_id = message.from_user.id

    try:
        helper = GoogleOAuthHelper(
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            encryption_key=settings.encryption_key,
        )
        encrypted_token = helper.exchange_code_for_encrypted_token(auth_code)

        # Сохраняем или обновляем в базе (по user_id, так как PK — суррогатный id)
        stmt = select(GoogleCredentials).where(GoogleCredentials.user_id == user_id)
        result = await session.execute(stmt)
        creds = result.scalar_one_or_none()

        if creds is None:
            creds = GoogleCredentials(
                user_id=user_id,
                encrypted_refresh_token=encrypted_token,
                client_id=settings.google_client_id,
                client_secret=settings.google_client_secret,
                scopes=json.dumps(["https://www.googleapis.com/auth/spreadsheets"]),
            )
            session.add(creds)
        else:
            creds.encrypted_refresh_token = encrypted_token
            creds.client_id = settings.google_client_id
            creds.client_secret = settings.google_client_secret

        await session.commit()
        await message.answer(
            "✅ *Google аккаунт успешно подключен\\!*\n\n"
            "Теперь отправьте ссылку на вашу Google Таблицу:\n"
            "`/sheet ВАША_ССЫЛКА_ИЛИ_ID`",
            parse_mode="MarkdownV2",
        )
    except Exception as exc:
        logger.error("Ошибка при обмене OAuth кода для пользователя %d: %s", user_id, exc)
        safe_exc = escape_md_v2(str(exc))
        await message.answer(
            f"❌ *Не удалось авторизовать аккаунт:*\n`{safe_exc}`\n\n"
            "Попробуйте запросить новую ссылку через /auth\\.",
            parse_mode="MarkdownV2",
        )


@common_router.message(Command("sheet"))
async def cmd_sheet(message: Message, session: AsyncSession) -> None:
    """Обработчик команды /sheet — сохранение Spreadsheet ID таблицы."""
    import re
    from app.db.models import GoogleCredentials

    if not message.from_user:
        return

    user_id = message.from_user.id
    text_parts = (message.text or "").strip().split(maxsplit=1)
    if len(text_parts) < 2:
        await message.answer("⚠️ Укажите ссылку на таблицу:\n`/sheet https://docs.google.com/spreadsheets/d/...`", parse_mode="MarkdownV2")
        return

    raw_input = text_parts[1].strip()

    # Извлечение ID таблицы из URL
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", raw_input)
    spreadsheet_id = match.group(1) if match else raw_input

    stmt = select(GoogleCredentials).where(GoogleCredentials.user_id == user_id)
    result = await session.execute(stmt)
    creds = result.scalar_one_or_none()

    if creds is None:
        await message.answer(
            "⚠️ Сначала авторизуйте аккаунт через команду /auth, а затем привяжите таблицу\\.",
            parse_mode="MarkdownV2",
        )
        return

    creds.spreadsheet_id = spreadsheet_id
    await session.commit()

    safe_sheet_id = escape_md_v2(spreadsheet_id)
    await message.answer(
        f"📊 *Таблица успешно привязана\\!*\n"
        f"ID: `{safe_sheet_id}`\n\n"
        "Теперь вы можете проверить синхронизацию командой */sync*\\!",
        parse_mode="MarkdownV2",
    )


@common_router.callback_query(lambda c: c.data == "menu_open_titles")
async def cb_open_titles(query: Any, dialog_manager: Any) -> None:
    """Открытие диалога тайтлов из меню."""
    from app.bot.dialogs.titles.dialog import TitlesSG
    from aiogram_dialog import StartMode

    await query.answer()
    await dialog_manager.start(TitlesSG.list_titles, mode=StartMode.RESET_STACK)


@common_router.callback_query(lambda c: c.data == "menu_open_settings")
async def cb_open_settings(query: Any, dialog_manager: Any) -> None:
    """Открытие диалога настроек из меню."""
    from app.bot.dialogs.settings.dialog import SettingsSG
    from aiogram_dialog import StartMode

    await query.answer()
    await dialog_manager.start(SettingsSG.main, mode=StartMode.RESET_STACK)


@common_router.callback_query(lambda c: c.data == "menu_trigger_sync")
async def cb_trigger_sync(query: Any, session: AsyncSession) -> None:
    """Запуск немедленной синхронизации по кнопке из меню."""
    from app.config import settings
    from app.services.digest import format_digest_markdown
    from app.services.tracker import TrackerService

    await query.answer("Запускаем синхронизацию...")
    user_id = query.from_user.id

    if query.message:
        await query.message.answer("🔍 _Сверяем обновления серий с Shikimori и Google Таблицей\\.\\.\\._", parse_mode="MarkdownV2")

    tracker = TrackerService(
        session=session,
        encryption_key=settings.encryption_key,
    )

    try:
        result = await tracker.check_user_updates_full(user_id=user_id)
        digest_text = format_digest_markdown(result.deltas, result.debts)
        if query.message:
            await query.message.answer(digest_text, parse_mode="MarkdownV2", disable_web_page_preview=True)
    except Exception as exc:
        logger.error("Ошибка при выполнении синхронизации из меню для пользователя %d: %s", user_id, exc)
        if query.message:
            safe_exc = escape_md_v2(str(exc))
            await query.message.answer(
                f"⚠️ *Произошла ошибка при сверке обновлений:*\n`{safe_exc}`",
                parse_mode="MarkdownV2",
            )


# ---------------------------------------------------------------------------
# Постоянная Reply-навигация (Persistent Keyboard Handlers)
# ---------------------------------------------------------------------------


@common_router.message(lambda msg: msg.text == "🏠 Главное меню")
async def nav_main_menu(message: Message) -> None:
    """Обработчик постоянной кнопки '🏠 Главное меню'."""
    await cmd_menu(message)


@common_router.message(lambda msg: msg.text == "📋 Мой список")
async def nav_my_titles(message: Message, dialog_manager: Any) -> None:
    """Обработчик постоянной кнопки '📋 Мой список'."""
    from app.bot.dialogs.titles.dialog import TitlesSG
    from aiogram_dialog import StartMode

    await dialog_manager.start(TitlesSG.list_titles, mode=StartMode.RESET_STACK)


@common_router.message(lambda msg: msg.text == "⚙️ Настройки")
async def nav_settings(message: Message, dialog_manager: Any) -> None:
    """Обработчик постоянной кнопки '⚙️ Настройки'."""
    from app.bot.dialogs.settings.dialog import SettingsSG
    from aiogram_dialog import StartMode

    await dialog_manager.start(SettingsSG.main, mode=StartMode.RESET_STACK)


# ---------------------------------------------------------------------------
# Фоллбэк неизвестного пользовательского ввода
# ---------------------------------------------------------------------------


@common_router.message()
async def fallback_unknown_message(message: Message) -> None:
    """Фоллбэк для неизвестных текстовых сообщений, не перехваченных диалогами."""
    logger.info(
        "[FALLBACK] Неизвестное сообщение от user_id=%s: %r",
        message.from_user.id if message.from_user else "unknown",
        message.text,
    )
    await message.answer(
        "Я не понял это сообщение. Воспользуйтесь кнопками меню ниже или перешлите лог сабов",
        reply_markup=get_persistent_main_keyboard(),
    )

