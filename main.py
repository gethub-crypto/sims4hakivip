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

# ==================== SETTINGS ====================
BOT_TOKEN = os.getenv("BOT_TOKEN")  # Use environment variable!
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1004390196653"))
PRODUCT_PRICE = 199  # Price in Stars (199 ⭐️)
SUBSCRIPTION_DAYS = 30  # Subscription duration in days

# Railway persistent storage
DATA_DIR = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", ".")
DATA_FILE = os.path.join(DATA_DIR, "users_data.json")

if not BOT_TOKEN:
    print("❌ BOT_TOKEN is not set in environment variables!")
    sys.exit(1)
# =================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ==================== DATABASE FUNCTIONS ====================

def load_users_data():
    """Load user data from JSON file"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading data file: {e}")
            return {}
    return {}

def save_users_data(data):
    """Save user data to JSON file"""
    try:
        os.makedirs(os.path.dirname(DATA_FILE) if os.path.dirname(DATA_FILE) else ".", exist_ok=True)
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving data file: {e}")

def add_subscription(user_id: int, username: str):
    """Add/update user subscription"""
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
    logger.info(f"Subscription added: user_id={user_id}, username={username}, until={expiry_date}")

def is_subscription_active(user_id: int) -> bool:
    """Check if subscription is active"""
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
    """Get remaining subscription days"""
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

# ==================== COMMAND HANDLERS ====================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    
    if is_subscription_active(user_id):
        days_left = get_subscription_days_left(user_id)
        builder = InlineKeyboardBuilder()
        builder.button(text="🔗 Get Channel Link", callback_data="get_channel_link")
        builder.button(text="📊 Subscription Status", callback_data="subscription_status")
        builder.button(text="💎 Renew Subscription", callback_data="send_invoice")
        builder.adjust(1)
        
        await message.answer(
            f"🎉 Your subscription is active!\n"
            f"⏳ Days remaining: {days_left}\n\n"
            f"Choose an action:",
            reply_markup=builder.as_markup()
        )
    else:
        builder = InlineKeyboardBuilder()
        builder.button(
            text=f"💎 Buy Access for {PRODUCT_PRICE} ⭐️", 
            callback_data="send_invoice"
        )
        
        await message.answer(
            f"Hello, {message.from_user.first_name}! 👋\n\n"
            f"🔒 Get access to a private channel with exclusive content!\n\n"
            f"📅 Subscription: {SUBSCRIPTION_DAYS} days\n"
            f"💰 Price: {PRODUCT_PRICE} ⭐️\n"
            f"🔗 One-time invite link\n"
            f"🔄 No auto-renewal\n\n"
            f"Click the button below to pay:",
            reply_markup=builder.as_markup()
        )

@dp.callback_query(F.data == "get_channel_link")
async def get_channel_link(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    if not is_subscription_active(user_id):
        await callback.message.answer(
            "❌ Your subscription has expired or is inactive.\n"
            "Use /start to purchase access."
        )
        await callback.answer()
        return
    
    try:
        invite_link = await bot.create_chat_invite_link(
            chat_id=CHANNEL_ID,
            member_limit=1
        )
        
        await callback.message.answer(
            f"🔗 Your channel invite link:\n"
            f"{invite_link.invite_link}\n\n"
            f"⚠️ This link is single-use! Do not share it with anyone.\n"
            f"If the link doesn't work, use /link to get a new one."
        )
    except Exception as e:
        logger.error(f"Error creating link for user_id={user_id}: {e}")
        await callback.message.answer(
            "❌ Error creating link. Try again later or use /link"
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
            f"📊 Subscription Status:\n\n"
            f"✅ Active\n"
            f"📅 Start: {start_date.strftime('%d.%m.%Y')}\n"
            f"📅 End: {end_date.strftime('%d.%m.%Y')}\n"
            f"⏳ Days remaining: {days_left}\n\n"
            f"Commands:\n"
            f"/link - get channel invite link\n"
            f"/status - view this status"
        )
    else:
        await callback.message.answer(
            "❌ You don't have an active subscription.\n"
            "Use /start to purchase access."
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
    """Send payment invoice"""
    try:
        await bot.send_invoice(
            chat_id=message.chat.id,
            title="Private Channel Access",
            description=f"{SUBSCRIPTION_DAYS}-day subscription. Access to exclusive content.",
            payload="channel_access_payload",
            provider_token="",  # Must be empty for Stars
            currency="XTR",
            prices=[LabeledPrice(label=f"{SUBSCRIPTION_DAYS}-day subscription", amount=PRODUCT_PRICE)],
            start_parameter="channel_access",
            need_name=False,
            need_phone_number=False,
            need_email=False,
            need_shipping_address=False,
            is_flexible=False
        )
        logger.info(f"Invoice sent to user {message.chat.id}")
    except Exception as e:
        logger.error(f"Error sending invoice to user {message.chat.id}: {e}")
        await message.answer(
            "❌ Error creating invoice. Please try again later.\n"
            "If the error persists, contact the administrator."
        )

@dp.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
    """Confirm payment pre-checkout"""
    user_id = pre_checkout_query.from_user.id
    logger.info(f"Pre-checkout query from user {user_id}")
    
    # Additional checks can be added here:
    # - Check if purchase limit exceeded
    # - Check if user is blocked
    # - Check if channel is available
    
    await pre_checkout_query.answer(ok=True)

@dp.message(F.successful_payment)
async def process_successful_payment(message: types.Message):
    """Handle successful payment"""
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.full_name
    
    # Add subscription
    add_subscription(user_id, username)
    
    logger.info(f"Successful payment: user_id={user_id}, amount={message.successful_payment.total_amount}")
    
    await message.answer("✅ Payment successful! Generating your invite link...")
    
    try:
        invite_link = await bot.create_chat_invite_link(
            chat_id=CHANNEL_ID,
            member_limit=1
        )
        
        await message.answer(
            f"🎉 Congratulations! You now have access for {SUBSCRIPTION_DAYS} days!\n\n"
            f"🔗 Your personal invite link:\n{invite_link.invite_link}\n\n"
            f"⚠️ This link is single-use! Do not share it with anyone.\n"
            f"If the link stops working, use /link\n\n"
            f"📊 Check subscription status: /status\n"
            f"🔗 Get a new link: /link"
        )
    except Exception as e:
        logger.error(f"Error creating link after payment user_id={user_id}: {e}")
        await message.answer(
            "❌ Error creating invite link.\n"
            "Don't worry, your subscription is active!\n"
            "Use /link to get your invite link."
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
            f"✅ Your subscription is active\n\n"
            f"📅 Start: {start_date.strftime('%d.%m.%Y')}\n"
            f"📅 End: {end_date.strftime('%d.%m.%Y')}\n"
            f"⏳ Days remaining: {days_left}\n\n"
            f"🔗 Get invite link: /link\n"
            f"💎 Renew: /buy"
        )
    else:
        await message.answer(
            "❌ You don't have an active subscription\n"
            "Use /start to purchase access"
        )

@dp.message(Command("link"))
async def link_command(message: types.Message):
    user_id = message.from_user.id
    
    if not is_subscription_active(user_id):
        await message.answer(
            "❌ You don't have an active subscription.\n"
            "Use /start to purchase access."
        )
        return
    
    try:
        invite_link = await bot.create_chat_invite_link(
            chat_id=CHANNEL_ID,
            member_limit=1
        )
        await message.answer(
            f"🔗 Your channel invite link:\n"
            f"{invite_link.invite_link}\n\n"
            f"⚠️ Single-use link! Do not share with anyone."
        )
    except Exception as e:
        logger.error(f"Error creating link for user_id={user_id}: {e}")
        await message.answer("❌ Error creating link. Try again later.")

# ==================== AUTOMATIC KICK ====================

async def check_expired_subscriptions():
    """Periodically check for expired subscriptions and kick users"""
    logger.info("🔄 Starting expired subscription check (every hour)")
    
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
                logger.info(f"Found {len(expired_users)} users with expired subscriptions")
            
            for user_id in expired_users:
                try:
                    # Notify user
                    try:
                        await bot.send_message(
                            user_id,
                            "⚠️ Your channel subscription has expired.\n\n"
                            "Access to the channel has been revoked.\n"
                            "Use /start to renew."
                        )
                    except Exception as e:
                        logger.error(f"Failed to notify user {user_id}: {e}")
                    
                    # Kick from channel
                    try:
                        await bot.ban_chat_member(
                            chat_id=CHANNEL_ID,
                            user_id=user_id
                        )
                        await bot.unban_chat_member(
                            chat_id=CHANNEL_ID,
                            user_id=user_id
                        )
                        logger.info(f"User {user_id} kicked from channel")
                    except Exception as e:
                        logger.error(f"Error kicking user {user_id} from channel: {e}")
                    
                    # Mark subscription as inactive
                    users[str(user_id)]["active"] = False
                    save_users_data(users)
                    
                except Exception as e:
                    logger.error(f"Error processing user {user_id}: {e}")
            
            # Check every hour
            await asyncio.sleep(3600)
            
        except Exception as e:
            logger.error(f"Error in subscription check loop: {e}")
            await asyncio.sleep(300)  # Wait 5 minutes on error

# ==================== STARTUP ====================

async def main():
    logger.info("=" * 50)
    logger.info("🚀 BOT STARTING")
    logger.info(f"💰 Subscription price: {PRODUCT_PRICE} ⭐️")
    logger.info(f"📅 Duration: {SUBSCRIPTION_DAYS} days")
    logger.info(f"📁 Data file: {DATA_FILE}")
    logger.info(f"📢 Channel ID: {CHANNEL_ID}")
    logger.info(f"⏰ Start time: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
    logger.info("=" * 50)
    
    # Check if bot is channel admin
    try:
        bot_member = await bot.get_chat_member(CHANNEL_ID, (await bot.get_me()).id)
        if bot_member.status in ["administrator", "creator"]:
            logger.info("✅ Bot is a channel administrator")
        else:
            logger.warning("⚠️ Bot is NOT a channel administrator! Link creation may not work.")
    except Exception as e:
        logger.error(f"❌ Error checking channel permissions: {e}")
    
    # Start background subscription check task
    asyncio.create_task(check_expired_subscriptions())
    
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("🤖 Bot is running and ready")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"❌ Critical error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Bot stopped by user")
    except Exception as e:
        logger.error(f"💥 Unexpected error: {e}")
