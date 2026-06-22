import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import LabeledPrice, PreCheckoutQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ==================== НАСТРОЙКИ ====================
BOT_TOKEN = "8884956672:AAHY-4_NBDeYNxZ4C9G9T3HRHNYu6afBqUQ"
CHANNEL_ID = -1002150000000  
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
    builder = InlineKeyboardBuilder()
    builder.button(text=f"Купить доступ за {PRODUCT_PRICE} ⭐️", pay=True)
    
    await message.answer(
        text=f"Привет, {message.from_user.first_name}! 👋\n\n"
             f"Для получения доступа в закрытый канал с PDF-материалами, "
             f"нажмите на кнопку оплаты ниже:",
        reply_markup=builder.as_markup()
    )

@dp.message(Command("buy"))
async def send_payment_command(message: types.Message):
    await send_invoice(message)

async def send_invoice(message: types.Message):
    await bot.send_invoice(
        chat_id=message.chat.id,
        title="Доступ в закрытый канал",
        description="Пожизненный доступ к приватным файлам и гайдам.",
        payload="channel_access_payload",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="Доступ", amount=PRODUCT_PRICE)],
        start_parameter="channel-pay"
    )

@dp.callback_query(F.data == "buy_access")
async def send_payment_callback(callback: types.CallbackQuery):
    await send_invoice(callback.message)
    await callback.answer()

@dp.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)

@dp.message(F.successful_payment)
async def process_successful_payment(message: types.Message):
    await message.answer("✅ Оплата прошла успешно! Генерирую вашу ссылку для входа...")
    
    try:
        invite_link = await bot.create_chat_invite_link(
            chat_id=CHANNEL_ID,
            member_limit=1
        )
        
        await message.answer(
            text=f"🎉 Ваша индивидуальная ссылка для вступления:\n"
                 f"{invite_link.invite_link}\n\n"
                 f"⚠️ Ссылка одноразовая, не пересылайте её никому!"
        )
    except Exception as e:
        logger.error(f"Ошибка при создании ссылки: {e}")
        await message.answer(
            "❌ Произошла ошибка при создании ссылки. "
            "Пожалуйста, обратитесь к администратору: @your_username"
        )

async def main():
    logger.info("Запуск бота...")
    try:
        # Пропускаем все накопившиеся сообщения
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Ошибка при запуске: {e}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")
