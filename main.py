import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import LabeledPrice, PreCheckoutQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ==================== НАСТРОЙКИ ====================
BOT_TOKEN = "8884956672:AAHY-4_NBDeYNxZ4C9G9T3HRHNYu6afBqUQ"
CHANNEL_ID = -1004390196653  
PRODUCT_PRICE = 50
# =================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    # Создаем обычную кнопку, которая вызовет команду /buy
    builder = InlineKeyboardBuilder()
    builder.button(
        text=f"💎 Купить доступ за {PRODUCT_PRICE} ⭐️", 
        callback_data="send_invoice"  # Обычный callback, не pay=True!
    )
    
    await message.answer(
        text=f"Привет, {message.from_user.first_name}! 👋\n\n"
             f"Для получения доступа в закрытый канал с PDF-материалами, "
             f"нажмите на кнопку ниже:",
        reply_markup=builder.as_markup()
    )

# Обработчик нажатия на кнопку
@dp.callback_query(F.data == "send_invoice")
async def process_callback(callback: types.CallbackQuery):
    await send_invoice(callback.message)
    await callback.answer()

# Команда /buy для прямой оплаты
@dp.message(Command("buy"))
async def buy_command(message: types.Message):
    await send_invoice(message)

# Общая функция отправки счета
async def send_invoice(message: types.Message):
    await bot.send_invoice(
        chat_id=message.chat.id,
        title="Доступ в закрытый канал",
        description="Пожизненный доступ к приватным файлам и гайдам.",
        payload="channel_access_payload",
        provider_token="",  # Для Stars обязательно пусто
        currency="XTR",
        prices=[LabeledPrice(label="Доступ в канал", amount=PRODUCT_PRICE)],
        start_parameter="channel_access"
    )

@dp.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)

@dp.message(F.successful_payment)
async def process_successful_payment(message: types.Message):
    await message.answer("✅ Оплата прошла успешно! Генерирую вашу ссылку...")
    
    try:
        invite_link = await bot.create_chat_invite_link(
            chat_id=CHANNEL_ID,
            member_limit=1
        )
        
        await message.answer(
            text=f"🎉 Вот ваша персональная ссылка:\n"
                 f"{invite_link.invite_link}\n\n"
                 f"⚠️ Ссылка одноразовая! Не передавайте её третьим лицам."
        )
    except Exception as e:
        logger.error(f"Ошибка создания ссылки: {e}")
        await message.answer(
            "❌ Ошибка при создании ссылки. Администратор уже уведомлён."
        )

async def main():
    logger.info("Запуск бота...")
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
        logger.info("Бот остановлен")
