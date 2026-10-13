# main.py
# Бот-автоповышатель:
#   - Запоминает каналы, куда его добавили.
#   - Как только кто-то заходит в канал —
#     бот сразу даёт ему полные права админа.
#   - /list — список каналов.

import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message, ChatMemberUpdated

from config import BOT_TOKEN, ADMIN_ID, LOG_PATH
import database as db


# ---------- Логирование ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


# ============================================================
#        ЛОВИМ СОБЫТИЯ ПО КАНАЛАМ
# ============================================================

@dp.my_chat_member()
async def on_bot_status(event: ChatMemberUpdated):
    """
    Срабатывает, когда бот меняет свой статус в чате.
    Интересует:
      - Добавление бота в канал (админом) → запомнить канал.
      - Удаление бота из канала → удалить из базы.
    """
    chat = event.chat
    new_status = event.new_chat_member.status
    old_status = event.old_chat_member.status

    # Нас интересуют только каналы
    if chat.type != "channel":
        return

    # Бот СТАЛ админом (или создателем)
    if new_status in ("administrator", "creator") and old_status not in ("administrator", "creator"):
        await db.add_channel(chat.id, chat.title or str(chat.id))
        logger.info(f"✅ Добавлен канал: {chat.title} ({chat.id})")

        try:
            await bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    f"✅ <b>Бот добавлен в канал</b>\n\n"
                    f"📛 <b>{chat.title}</b>\n"
                    f"🆔 <code>{chat.id}</code>\n\n"
                    f"Теперь все новые участники получат <b>права админа</b> автоматически."
                )
            )
        except Exception as e:
            logger.error(f"Не смог уведомить: {e}")

    # Бот УДАЛЁН из канала
    elif new_status in ("left", "kicked") and old_status in ("administrator", "creator", "member"):
        await db.remove_channel(chat.id)
        logger.info(f"❌ Удалён канал: {chat.title} ({chat.id})")

        try:
            await bot.send_message(
                chat_id=ADMIN_ID,
                text=f"❌ <b>Бот удалён из канала</b>\n\n📛 {chat.title}"
            )
        except Exception:
            pass


@dp.chat_member()
async def on_member_join(event: ChatMemberUpdated):
    """
    Когда кто-то заходит в канал — сразу даём ему права админа.
    Срабатывает ТОЛЬКО для каналов, где бот админ.
    """
    chat = event.chat

    # Только каналы
    if chat.type != "channel":
        return

    new_status = event.new_chat_member.status
    old_status = event.old_chat_member.status

    # Зашёл: был left/kicked → стал member
    if not (old_status in ("left", "kicked") and new_status == "member"):
        return

    user = event.new_chat_member.user

    # Игнорируем ботов
    if user.is_bot:
        return

    username = f"@{user.username}" if user.username else "(нет юзернейма)"
    full_name = user.full_name or "(без имени)"

    logger.info(f"🔔 Новый участник в «{chat.title}»: {full_name} ({user.id})")

    # === СРАЗУ ВЫДАЁМ ПРАВА ===
    try:
        await bot.promote_chat_member(
            chat_id=chat.id,
            user_id=user.id,
            can_manage_chat=True,
            can_delete_messages=True,
            can_manage_video_chats=True,
            can_restrict_members=True,
            can_promote_members=True,     # может повышать других
            can_change_info=True,
            can_invite_users=True,
            can_post_messages=True,
            can_edit_messages=True,
            can_pin_messages=True,
            can_manage_topics=True,
        )
        logger.info(f"✅ Права выданы: {full_name} ({user.id})")
        promote_status = "✅ Права выданы"
    except Exception as e:
        logger.error(f"❌ Ошибка выдачи прав {user.id}: {e}")
        promote_status = f"❌ Ошибка: <code>{e}</code>"

    # === УВЕДОМЛЯЕМ АДМИНА ===
    try:
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"🔔 <b>Новый участник</b>\n\n"
                f"📛 Канал: <b>{chat.title}</b>\n"
                f"👤 Имя: <b>{full_name}</b>\n"
                f"🔗 Юзернейм: {username}\n"
                f"🆔 ID: <code>{user.id}</code>\n\n"
                f"{promote_status}"
            )
        )
    except Exception as e:
        logger.error(f"Не смог уведомить админа: {e}")

    # === УВЕДОМЛЯЕМ ЮЗЕРА ===
    try:
        await bot.send_message(
            chat_id=user.id,
            text=(
                "✅ <b>Тебе выданы права администратора</b>\n\n"
                "Теперь ты можешь:\n"
                "• Публиковать посты\n"
                "• Удалять сообщения\n"
                "• Банить пользователей\n"
                "• Менять настройки канала\n"
                "• Добавлять других админов"
            )
        )
    except Exception:
        pass  # юзер мог не писать боту


# ============================================================
#        КОМАНДЫ
# ============================================================

@dp.message(Command("start"))
async def cmd_start(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Бот приватный.")
        return
    await message.answer(
        "👋 <b>Бот-автоповышатель</b>\n\n"
        "• Добавь бота <b>админом</b> в канал — он его запомнит.\n"
        "• Как только кто-то <b>зайдёт</b> в канал — ему сразу дадут <b>права админа</b>.\n"
        "• Тебе приходят уведомления.\n\n"
        "<b>Команды:</b>\n"
        "/list — список каналов\n"
        "/status — статус"
    )


@dp.message(Command("list"))
async def cmd_list(message: Message):
    if not is_admin(message.from_user.id):
        return
    channels = await db.get_channels()
    if not channels:
        await message.answer(
            "📭 Каналов нет.\n"
            "Добавь бота <b>админом</b> в канал — он появится здесь."
        )
        return

    lines = ["📋 <b>Подключённые каналы:</b>\n"]
    for i, (ch_id, name, added) in enumerate(channels, 1):
        lines.append(f"{i}. <b>{name}</b>\n   ID: <code>{ch_id}</code>\n   Добавлен: {added}\n")
    await message.answer("\n".join(lines))


@dp.message(Command("status"))
async def cmd_status(message: Message):
    if not is_admin(message.from_user.id):
        return
    channels = await db.get_channels()
    await message.answer(
        f"📊 <b>Статус</b>\n\n"
        f"Каналов: <b>{len(channels)}</b>\n"
        f"Твой ID: <code>{ADMIN_ID}</code>\n"
        f"Режим: <b>авто-повышение</b> ✅"
    )


# ============================================================
#        ЗАПУСК
# ============================================================

async def main():
    await db.init_db()
    logger.info(f"Бот-автоповышатель запущен. Админ: {ADMIN_ID}")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Остановлен.")