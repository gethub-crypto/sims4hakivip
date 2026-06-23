import asyncio
import logging
import sys
import os
import json
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import LabeledPrice, PreCheckoutQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ==================== НАСТРОЙКИ ====================
BOT_TOKEN = "ВАШ_ТОКЕН_СЮДА"
CHANNEL_ID = -1002150000000  # Ваш ID канала
PRODUCT_PRICE = 199  # Цена в Stars (199 ⭐️)
SUBSCRIPTION_DAYS = 30  # На сколько дней доступ

# Для Railway: постоянное хранилище
DATA_DIR = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", ".")
DATA_FILE = os.path.join(DATA_DIR, "users_data.json")
# =================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ==================== РАБОТА С БАЗОЙ ДАННЫХ ====================

def load_users_data():
    """Загрузка данных пользователей из JSON файла"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка чтения файла данных: {e}")
            return {}
    return {}

def save_users_data(data):
    """Сохранение данных пользователей в JSON файл"""
    try:
        os.makedirs(os.path.dirname(DATA_FILE) if os.path.dirname(DATA_FILE) else ".", exist_ok=True)
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения файла данных: {e}")

def add_subscription(user_id: int, username: str):
    """Добавление/обновление подписки пользователя"""
    users = load_users_data()
    user_id_str = str(user_id)
    
    expiry_date = (datetime.now() + timedelta(days=SUBSCRIPTION_DAYS)).isoformat()
    
    users[user_id_str] = {
        "username": username,
        "subscription_start": datetime.now().isoformat(),
        "subscription_end": expiry_date,
        "active": True
    }
    
    save_users_data(users)
    logger.info(f"Подписка добавлена: user_id={user_id}, username={username}, до={expiry_date}")

def is_subscription_active(user_id: int) -> bool:
    """Проверка активности подписки"""
    users = load_users_data()
    user_id_str = str(user_id)
    
    if user_id_str not in users:
        return False
    
    user_data = users[user_id_str]
    if not user_data.get("active", False):
        return False
    
    expiry_date = datetime.fromisoformat(user_data["subscription_end"])
    return datetime.now() < expiry_date

def get_subscription_days_left(user_id: int) -> int:
    """Получение оставшихся дней подписки"""
    users = load_users_data()
    user_id_str = str(user_id)
    
    if user_id_str not in users:
        return 0
    
    user_data = users[user_id_str]
    if not user_data.get("active", False):
        return 0
    
    expiry_date = datetime.fromisoformat(user_data["subscription_end"])
    days_left = (expiry_date - datetime.now()).days
    return max(0, days_left)

# ==================== ОБРАБОТЧИКИ КОМАНД ====================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    
    if is_subscription_active(user_id):
        days_left = get_subscription_days_left(user_id)
        builder = InlineKeyboardBuilder()
        builder.button(text="🔗 Получить ссылку на канал", callback_data="get_channel_link")
        builder.button(text="📊 Статус подписки", callback_data="subscription_status")
        builder.button(text="💎 Продлить подписку", callback_data="send_invoice")
        builder.adjust(1)
        
        await message.answer(
            f"🎉 Ваша подписка активна!\n"
            f"⏳ Осталось дней: {days_left}\n\n"
            f"Выберите действие:",
            reply_markup=builder.as_markup()
        )
    else:
        builder = InlineKeyboardBuilder()
        builder.button(
            text=f"💎 Купить доступ за {PRODUCT_PRICE} ⭐️", 
            callback_data="send_invoice"
        )
        
        await message.answer(
            f"Привет, {message.from_user.first_name}! 👋\n\n"
            f"🔒 Получите доступ в закрытый канал с эксклюзивными материалами!\n\n"
            f"📅 Подписка на {SUBSCRIPTION_DAYS} дней\n"
            f"💰 Стоимость: {PRODUCT_PRICE} ⭐️\n"
            f"🔗 Одноразовая ссылка для входа\n"
            f"🔄 Автопродление не предусмотрено\n\n"
            f"Нажмите на кнопку ниже для оплаты:",
            reply_markup=builder.as_markup()
        )

@dp.callback_query(F.data == "get_channel_link")
async def get_channel_link(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    if not is_subscription_active(user_id):
        await callback.message.answer(
            "❌ Ваша подписка истекла или неактивна.\n"
            "Используйте /start для покупки доступа."
        )
        await callback.answer()
        return
    
    try:
        invite_link = await bot.create_chat_invite_link(
            chat_id=CHANNEL_ID,
            member_limit=1
        )
        
        await callback.message.answer(
            f"🔗 Ваша ссылка для входа в канал:\n"
            f"{invite_link.invite_link}\n\n"
            f"⚠️ Ссылка одноразовая! Не передавайте её никому.\n"
            f"Если ссылка не работает, используйте /link для получения новой."
        )
    except Exception as e:
        logger.error(f"Ошибка создания ссылки для user_id={user_id}: {e}")
        await callback.message.answer(
            "❌ Ошибка создания ссылки. Попробуйте позже или используйте /link"
        )
    
    await callback.answer()

@dp.callback_query(F.data == "subscription_status")
async def subscription_status(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    if is_subscription_active(user_id):
        days_left = get_subscription_days_left(user_id)
        users = load_users_data()
        user_data = users[str(user_id)]
        start_date = datetime.fromisoformat(user_data["subscription_start"])
        end_date = datetime.fromisoformat(user_data["subscription_end"])
        
        await callback.message.answer(
            f"📊 Статус подписки:\n\n"
            f"✅ Активна\n"
            f"📅 Начало: {start_date.strftime('%d.%m.%Y')}\n"
            f"📅 Окончание: {end_date.strftime('%d.%m.%Y')}\n"
            f"⏳ Осталось дней: {days_left}\n\n"
            f"Команды:\n"
            f"/link - получить ссылку на канал\n"
            f"/status - этот статус"
        )
    else:
        await callback.message.answer(
            "❌ У вас нет активной подписки.\n"
            "Используйте /start для покупки доступа."
        )
    
    await callback.answer()

@dp.callback_query(F.data == "send_invoice")
async def process_callback(callback: types.CallbackQuery):
    await send_invoice(callback.message)
    await callback.answer()

@dp.message(Command("buy"))
async def buy_command(message: types.Message):
    await send_invoice(message)

async def send_invoice(message: types.Message):
    """Отправка счета на оплату"""
    try:
        await bot.send_invoice(
            chat_id=message.chat.id,
            title="Доступ в закрытый канал",
            description=f"Подписка на {SUBSCRIPTION_DAYS} дней. Доступ к эксклюзивным материалам.",
            payload="channel_access_payload",
            provider_token="",  # Для Stars обязательно пусто
            currency="XTR",
            prices=[LabeledPrice(label=f"Подписка на {SUBSCRIPTION_DAYS} дней", amount=PRODUCT_PRICE)],
            start_parameter="channel_access",
            need_name=False,
            need_phone_number=False,
            need_email=False,
            need_shipping_address=False,
            is_flexible=False
        )
        logger.info(f"Счет отправлен пользователю {message.chat.id}")
    except Exception as e:
        logger.error(f"Ошибка отправки счета пользователю {message.chat.id}: {e}")
        await message.answer(
            "❌ Ошибка при создании счета. Попробуйте позже.\n"
            "Если ошибка повторяется, обратитесь к администратору."
        )

@dp.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
    """Подтверждение платежа"""
    user_id = pre_checkout_query.from_user.id
    logger.info(f"Pre-checkout запрос от пользователя {user_id}")
    
    # Здесь можно добавить проверки:
    # - Не превышен ли лимит покупок
    # - Не заблокирован ли пользователь
    # - Доступен ли канал
    
    await pre_checkout_query.answer(ok=True)

@dp.message(F.successful_payment)
async def process_successful_payment(message: types.Message):
    """Обработка успешной оплаты"""
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.full_name
    
    # Добавляем подписку
    add_subscription(user_id, username)
    
    logger.info(f"Успешная оплата: user_id={user_id}, сумма={message.successful_payment.total_amount}")
    
    await message.answer("✅ Оплата прошла успешно! Генерирую вашу ссылку...")
    
    try:
        invite_link = await bot.create_chat_invite_link(
            chat_id=CHANNEL_ID,
            member_limit=1
        )
        
        await message.answer(
            f"🎉 Поздравляем! Вы получили доступ на {SUBSCRIPTION_DAYS} дней!\n\n"
            f"🔗 Ваша персональная ссылка:\n{invite_link.invite_link}\n\n"
            f"⚠️ Ссылка одноразовая! Не передавайте её третьим лицам.\n"
            f"Если ссылка перестала работать, используйте /link\n\n"
            f"📊 Проверить статус подписки: /status\n"
            f"🔗 Получить новую ссылку: /link"
        )
    except Exception as e:
        logger.error(f"Ошибка создания ссылки после оплаты user_id={user_id}: {e}")
        await message.answer(
            "❌ Ошибка при создании ссылки.\n"
            "Не волнуйтесь, подписка активирована!\n"
            "Используйте /link чтобы получить ссылку."
        )

@dp.message(Command("status"))
async def status_command(message: types.Message):
    user_id = message.from_user.id
    
    if is_subscription_active(user_id):
        days_left = get_subscription_days_left(user_id)
        users = load_users_data()
        user_data = users[str(user_id)]
        start_date = datetime.fromisoformat(user_data["subscription_start"])
        end_date = datetime.fromisoformat(user_data["subscription_end"])
        
        await message.answer(
            f"✅ Ваша подписка активна\n\n"
            f"📅 Начало: {start_date.strftime('%d.%m.%Y')}\n"
            f"📅 Окончание: {end_date.strftime('%d.%m.%Y')}\n"
            f"⏳ Осталось дней: {days_left}\n\n"
            f"🔗 Получить ссылку: /link\n"
            f"💎 Продлить: /buy"
        )
    else:
        await message.answer(
            "❌ У вас нет активной подписки\n"
            "Используйте /start для покупки доступа"
        )

@dp.message(Command("link"))
async def link_command(message: types.Message):
    user_id = message.from_user.id
    
    if not is_subscription_active(user_id):
        await message.answer(
            "❌ У вас нет активной подписки.\n"
            "Используйте /start для покупки доступа."
        )
        return
    
    try:
        invite_link = await bot.create_chat_invite_link(
            chat_id=CHANNEL_ID,
            member_limit=1
        )
        await message.answer(
            f"🔗 Ваша ссылка для входа в канал:\n"
            f"{invite_link.invite_link}\n\n"
            f"⚠️ Ссылка одноразовая! Не передавайте её никому."
        )
    except Exception as e:
        logger.error(f"Ошибка создания ссылки для user_id={user_id}: {e}")
        await message.answer("❌ Ошибка создания ссылки. Попробуйте позже.")

# ==================== АВТОМАТИЧЕСКОЕ ОТКЛЮЧЕНИЕ ====================

async def check_expired_subscriptions():
    """Периодическая проверка истекших подписок и исключение из канала"""
    logger.info("🔄 Запущена проверка истекших подписок (каждый час)")
    
    while True:
        try:
            users = load_users_data()
            now = datetime.now()
            expired_users = []
            
            for user_id, user_data in users.items():
                if user_data.get("active", False):
                    expiry_date = datetime.fromisoformat(user_data["subscription_end"])
                    if now > expiry_date:
                        expired_users.append(int(user_id))
            
            if expired_users:
                logger.info(f"Найдено пользователей с истекшей подпиской: {len(expired_users)}")
            
            for user_id in expired_users:
                try:
                    # Уведомляем пользователя
                    try:
                        await bot.send_message(
                            user_id,
                            "⚠️ Ваша подписка на канал истекла.\n\n"
                            "Доступ к каналу прекращен.\n"
                            "Используйте /start для продления."
                        )
                    except Exception as e:
                        logger.error(f"Не удалось отправить уведомление пользователю {user_id}: {e}")
                    
                    # Исключаем из канала
                    try:
                        await bot.ban_chat_member(
                            chat_id=CHANNEL_ID,
                            user_id=user_id
                        )
                        await bot.unban_chat_member(
                            chat_id=CHANNEL_ID,
                            user_id=user_id
                        )
                        logger.info(f"Пользователь {user_id} исключен из канала")
                    except Exception as e:
                        logger.error(f"Ошибка исключения пользователя {user_id} из канала: {e}")
                    
                    # Отмечаем подписку как неактивную
                    users[str(user_id)]["active"] = False
                    save_users_data(users)
                    
                except Exception as e:
                    logger.error(f"Ошибка обработки пользователя {user_id}: {e}")
            
            # Проверяем раз в час
            await asyncio.sleep(3600)
            
        except Exception as e:
            logger.error(f"Ошибка в цикле проверки подписок: {e}")
            await asyncio.sleep(300)  # При ошибке ждем 5 минут

# ==================== ЗАПУСК ====================

async def main():
    logger.info("=" * 50)
    logger.info("🚀 ЗАПУСК БОТА")
    logger.info(f"💰 Цена подписки: {PRODUCT_PRICE} ⭐️")
    logger.info(f"📅 Длительность: {SUBSCRIPTION_DAYS} дней")
    logger.info(f"📁 Файл данных: {DATA_FILE}")
    logger.info(f"📢 Канал ID: {CHANNEL_ID}")
    logger.info(f"⏰ Время запуска: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
    logger.info("=" * 50)
    
    # Проверяем, что бот является администратором канала
    try:
        bot_member = await bot.get_chat_member(CHANNEL_ID, (await bot.get_me()).id)
        if bot_member.status in ["administrator", "creator"]:
            logger.info("✅ Бот является администратором канала")
        else:
            logger.warning("⚠️ Бот не является администратором канала! Создание ссылок может не работать.")
    except Exception as e:
        logger.error(f"❌ Ошибка проверки прав в канале: {e}")
    
    # Запускаем фоновую задачу проверки подписок
    asyncio.create_task(check_expired_subscriptions())
    
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("🤖 Бот запущен и готов к работе")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"💥 Неожиданная ошибка: {e}")
