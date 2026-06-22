import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import LabeledPrice, PreCheckoutQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ==================== НАСТРОЙКИ (ЗАМЕНИТЕ НА СВОИ) ====================
BOT_TOKEN = "СЮДА_ВСТАВЬТЕ_ТОКЕН_ИЗ_BOTFATHER"
# ID вашего приватного канала (должно начинаться с -100, например: -100123456789)
# Как узнать ID: пересылайте любое сообщение из канала в бот @ShowJsonBot
CHANNEL_ID = -1002150000000  
PRODUCT_PRICE = 50  # Цена в Звёздах (например, 50 ⭐️)
# ======================================================================

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# 1. Обработка команды /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    builder = InlineKeyboardBuilder()
    # Важно: для оплаты Stars кнопка ОБЯЗАТЕЛЬНО должна иметь параметр pay=True
    builder.button(text=f"Купить доступ за {PRODUCT_PRICE} ⭐️", pay=True)
    
    await message.answer(
        text=f"Привет, {message.from_user.first_name}! 👋\n\n"
             f"Для получения доступа в закрытый канал с PDF-материалами, "
             f"нажмите на кнопку оплаты ниже:",
        reply_markup=builder.as_markup()
    )

# 2. Отправка счета на оплату (Invoice)
@dp.message(F.text.contains("Купить доступ") | Command("buy"))
async def send_payment(message: types.Message):
    await bot.send_invoice(
        chat_id=message.chat.id,
        title="Доступ в закрытый канал",
        description="Пожизненный доступ к приватным файлам и гайдам.",
        payload="channel_access_payload", # Любая внутренняя метка для кода
        provider_token="", # Для Telegram Stars оставляем ПУСТЫМ!
        currency="XTR",   # Код валюты Telegram Stars
        prices=[LabeledPrice(label="Доступ", amount=PRODUCT_PRICE)],
        start_parameter="channel-pay"
    )

# 3. Предварительная проверка (ОБЯЗАТЕЛЬНЫЙ шаг в Telegram)
# Бот должен одобрить транзакцию в течение 10 секунд
@dp.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)

# 4. Обработка успешной оплаты и выдача ссылки
@dp.message(F.successful_payment)
async def process_successful_payment(message: types.Message):
    await message.answer("✅ Оплата прошла успешно! Генерирую вашу ссылку для входа...")
    
    try:
        # Создаем уникальную ссылку в канал, которая сработает только для 1 человека
        invite_link = await bot.create_chat_invite_link(
            chat_id=CHANNEL_ID,
            member_limit=1 # Ссылка закроется сразу после входа покупателя
        )
        
        await message.answer(
            text=f"Ваша индивидуальная ссылка для вступления:\n{invite_link.invite_link}\n\n"
                 f"⚠️ Ссылка одноразовая, не пересылайте её никому!"
        )
    except Exception as e:
        logging.error(f"Ошибка при создании ссылки: {e}")
        await message.answer(
            "Произошла ошибка при создании ссылки. Пожалуйста, напишите администратору."
        )

async def main():
    await dp.start_polling(bot)

if name == "main":
    asyncio.run(main())
