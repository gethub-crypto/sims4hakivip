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
PRODUCT_PRICE = 50  # Цена в Stars
SUBSCRIPTION_DAYS = 30  # На сколько дней доступ
TEST_MODE = True  # False когда всё готово

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
        # Создаем директорию если её нет
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
    logger.info(f"Подписка добавлена: user_id={user_id}, до={expiry_date}")

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

# ==================== ОСНОВНЫЕ ОБРАБОТЧИКИ ====================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    
    # Проверяем статус подписки
    if is_subscription_active(user_id):
        days_left = get_subscription_days_left(user_id)
        builder = InlineKeyboardBuilder()
        builder.button(text="🔗 Получить ссылку на канал", callback_data="get_channel_link")
        builder.button(text="📊 Статус подписки", callback_data="subscription_status")
        builder.adjust(1)  # Кнопки в столбик
        
        await message.answer(
            f"🎉 Ваша подписка активна!\n"
            f"⏳ Осталось дней: {days_left}\n\n"
            f"Выберите действие:",
            reply_markup=builder.as_markup()
        )
    else:
        builder = InlineKeyboardBuilder()
        price = 1 if TEST_MODE else PRODUCT_PRICE
        builder.button(
            text=f"💎 Купить доступ за {price} ⭐️", 
            callback_data="send_invoice"
        )
        
        await message.answer(
            f"Привет, {message.from_user.first_name}! 👋\n\n"
            f"🔒 Получите доступ в закрытый канал с материалами!\n"
            f"📅 Подписка на {SUBSCRIPTION_DAYS} дней\n"
            f"💰 Стоимость: {price} ⭐️\n\n"
            f"Нажмите на кнопку ниже для оплаты:",
            reply_markup=builder.as_markup()
        )

@dp.callback_query(F.data == "get_channel_link")
async def get_channel_link(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    if not is_subscription_active(user_id):
        await callback.message.answer("❌ Ваша подписка истекла или неактивна.")
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
            f"⚠️ Ссылка одноразовая! Не передавайте её никому."
        )
    except Exception as e:
        logger.error(f"Ошибка создания ссылки: {e}")
        await callback.message.answer("❌ Ошибка создания ссылки. Попробуйте позже или используйте /link")
    
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
            f"⏳ Осталось дней: {days_left}"
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
    price = 1 if TEST_MODE else PRODUCT_PRICE
    test_text = "🧪 ТЕСТОВЫЙ ПЛАТЕЖ\n" if TEST_MODE else ""
    
    try:
        await bot.send_invoice(
            chat_id=message.chat.id,
            title="Доступ в закрытый канал",
            description=f"{test_text}Подписка на {SUBSCRIPTION_DAYS} дней",
            payload="test_payload" if TEST_MODE else "channel_access_payload",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(label=f"Подписка на {SUBSCRIPTION_DAYS} дней", amount=price)],
            start_parameter="channel_access"
        )
    except Exception as e:
        logger.error(f"Ошибка отправки счета: {e}")
        await message.answer("❌ Ошибка при создании счета. Попробуйте позже.")

@dp.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
    # Здесь можно добавить дополнительные проверки
    logger.info(f"Pre-checkout запрос от пользователя {pre_checkout_query.from_user.id}")
    await pre_checkout_query.answer(ok=True)

@dp.message(F.successful_payment)
async def process_successful_payment(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.full_name
    
    # Добавляем подписку
    add_subscription(user_id, username)
    
    await message.answer("✅ Оплата прошла успешно! Генерирую вашу ссылку...")
    
    try:
        invite_link = await bot.create_chat_invite_link(
            chat_id=CHANNEL_ID,
            member_limit=1
        )
        
        await message.answer(
            f"🎉 Поздравляем! Вы получили доступ на {SUBSCRIPTION_DAYS} дней!\n\n"
            f"🔗 Ваша персональная ссылка:\n{invite_link.invite_link}\n\n"
            f"⚠️ Ссылка одноразовая! Не передавайте её третьим лицам.\n\n"
            f"📊 Проверить статус подписки: /status\n"
            f"🔗 Получить новую ссылку: /link"
        )
    except Exception as e:
        logger.error(f"Ошибка создания ссылки: {e}")
        await message.answer(
            "❌ Ошибка при создании ссылки.\n"
            "Используйте /link чтобы получить ссылку позже.\n"
            "Статус подписки: /status"
        )

@dp.message(Command("status"))
async def status_command(message: types.Message):
    user_id = message.from_user.id
    
    if is_subscription_active(user_id):
        days_left = get_subscription_days_left(user_id)
        users = load_users_data()
        user_data = users[str(user_id)]
        end_date = datetime.fromisoformat(user_data["subscription_end"])
        
        await message.answer(
            f"✅ Ваша подписка активна\n"
            f"⏳ Осталось дней: {days_left}\n"
            f"📅 Действует до: {end_date.strftime('%d.%m.%Y')}\n\n"
            f"🔗 Получить ссылку: /link"
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
        await message.answer("❌ Ваша подписка неактивна. Используйте /start для покупки.")
        return
    
    try:
        invite_link = await bot.create_chat_invite_link(
            chat_id=CHANNEL_ID,
            member_limit=1
        )
        await message.answer(
            f"🔗 Ваша ссылка для входа в канал:\n"
            f"{invite_link.invite_link}\n\n"
            f"⚠️ Ссылка одноразовая!"
        )
    except Exception as e:
        logger.error(f"Ошибка создания ссылки: {e}")
        await message.answer("❌ Ошибка создания ссылки. Попробуйте позже.")

# ==================== АВТОМАТИЧЕСКОЕ ОТКЛЮЧЕНИЕ ====================

async def check_expired_subscriptions():
    """Периодическая проверка истекших подписок"""
    logger.info("Запущена проверка истекших подписок")
    
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
            
            for user_id in expired_users:
                try:
                    # Уведомляем пользователя
                    await bot.send_message(
                        user_id,
                        "⚠️ Ваша подписка истекла.\n"
                        "Доступ к каналу прекращен.\n"
                        "Используйте /start для продления."
                    )
                    
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
                    except Exception as e:
                        logger.error(f"Ошибка исключения пользователя {user_id}: {e}")
                    
                    # Отмечаем подписку как неактивную
                    users[str(user_id)]["active"] = False
                    save_users_data(users)
                    
                    logger.info(f"Пользователь {user_id} отключен (истекла подписка)")
                    
                except Exception as e:
                    logger.error(f"Ошибка обработки пользователя {user_id}: {e}")
            
            # Проверяем раз в час
            await asyncio.sleep(3600)
            
        except Exception as e:
            logger.error(f"Ошибка в цикле проверки подписок: {e}")
            await asyncio.sleep(300)

# ==================== ТЕСТОВЫЕ КОМАНДЫ ====================

if TEST_MODE:
    @dp.message(Command("test_payment"))
    async def test_payment(message: types.Message):
        """Имитация успешной оплаты для тестов"""
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.full_name
        
        add_subscription(user_id, username)
        
        try:
            invite_link = await bot.create_chat_invite_link(
                chat_id=CHANNEL_ID,
                member_limit=1
            )
            
            await message.answer(
                f"🧪 ТЕСТОВАЯ ОПЛАТА УСПЕШНА!\n\n"
                f"✅ Подписка активирована на {SUBSCRIPTION_DAYS} дней\n"
                f"🔗 Ссылка: {invite_link.invite_link}\n\n"
                f"Команды:\n"
                f"/status - проверить статус\n"
                f"/test_expiry - тест истечения подписки"
            )
        except Exception as e:
            logger.error(f"Ошибка тестовой оплаты: {e}")
            await message.answer(f"❌ Ошибка: {e}")

    @dp.message(Command("test_expiry"))
    async def test_expiry(message: types.Message):
        """Тест истечения подписки"""
        user_id = str(message.from_user.id)
        users = load_users_data()
        
        if user_id in users:
            # Устанавливаем "истечение" 10 секунд назад
            users[user_id]["subscription_end"] = (datetime.now() - timedelta(seconds=10)).isoformat()
            save_users_data(users)
            await message.answer(
                "🧪 Подписка помечена как истекшая 10 секунд назад\n"
                "В течение часа бот должен вас исключить из канала\n"
                "Для быстрой проверки перезапустите бота"
            )
        else:
            await message.answer("❌ У вас нет подписки. Используйте /test_payment")

# ==================== ЗАПУСК ====================

async def main():
    logger.info("=" * 40)
    logger.info("Запуск бота...")
    logger.info(f"Режим: {'ТЕСТОВЫЙ' if TEST_MODE else 'ПРОДАКШЕН'}")
    logger.info(f"Файл данных: {DATA_FILE}")
    logger.info(f"Канал ID: {CHANNEL_ID}")
    logger.info("=" * 40)
    
    # Запускаем фоновую задачу проверки подписок
    asyncio.create_task(check_expired_subscriptions())
    
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")
