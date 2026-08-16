import os
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("8679448910:AAHFZhp92ADLqIwkmy8caYudne-3GZHURx8")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is required.")

stats = {
    "total": 0,
    "approved": 0,
    "declined": 0,
    "unknown": 0,
    "errors": 0,
    "start_time": datetime.now(),
}


def menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🧪 Test", callback_data="test"),
            InlineKeyboardButton("📈 Stats", callback_data="stats"),
        ],
        [
            InlineKeyboardButton("❓ Help", callback_data="help"),
            InlineKeyboardButton("🔄 Reset", callback_data="reset"),
        ],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✨ *Safe Test Bot* ✨\n\n"
        "This bot provides a local/mock test checker only.\n"
        "It does not contact payment processors and does not process real card data.\n\n"
        "Use /test to run a mock test or choose a button below.",
        parse_mode="Markdown",
        reply_markup=menu(),
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❓ *Help*\n\n"
        "/start — Open the main menu\n"
        "/help — Show this help\n"
        "/test — Run a safe mock test\n"
        "/stats — Show statistics\n"
        "/reset — Reset statistics\n\n"
        "The mock checker accepts a test label such as `test-ok`, "
        "`test-fail`, or any other text. Do not send real payment-card numbers or CVVs.",
        parse_mode="Markdown",
        reply_markup=menu(),
    )


def mock_check(value: str) -> str:
    """Deterministic local mock. No network/payment-provider calls."""
    value = value.strip().lower()
    if value == "test-ok":
        return "APPROVED (MOCK)"
    if value == "test-fail":
        return "DECLINED (MOCK)"
    return "UNKNOWN (MOCK)"


async def run_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = " ".join(context.args).strip() if context.args else "test-ok"
    result = mock_check(value)

    stats["total"] += 1
    if result.startswith("APPROVED"):
        stats["approved"] += 1
    elif result.startswith("DECLINED"):
        stats["declined"] += 1
    else:
        stats["unknown"] += 1

    await update.message.reply_text(
        f"🧪 *Mock Test*\n\n"
        f"Input: `{value}`\n"
        f"Result: *{result}*\n\n"
        "No external payment service was contacted.",
        parse_mode="Markdown",
        reply_markup=menu(),
    )


async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uptime = datetime.now() - stats["start_time"]
    total = stats["total"]
    rate = (stats["approved"] / total * 100) if total else 0

    text = (
        "📊 *Statistics*\n\n"
        f"🕐 Uptime: `{uptime.seconds // 3600}h {(uptime.seconds % 3600) // 60}m`\n"
        f"📌 Total tests: `{total}`\n"
        f"✅ Mock approved: `{stats['approved']}`\n"
        f"❌ Mock declined: `{stats['declined']}`\n"
        f"⚠️ Mock unknown: `{stats['unknown']}`\n"
        f"📈 Mock approval rate: `{rate:.1f}%`\n"
    )
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, parse_mode="Markdown", reply_markup=menu()
        )
    else:
        await update.message.reply_text(
            text, parse_mode="Markdown", reply_markup=menu()
        )


async def reset_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats.update({
        "total": 0,
        "approved": 0,
        "declined": 0,
        "unknown": 0,
        "errors": 0,
        "start_time": datetime.now(),
    })

    if update.callback_query:
        await update.callback_query.edit_message_text(
            "🔄 *Statistics reset.*", parse_mode="Markdown", reply_markup=menu()
        )
    else:
        await update.message.reply_text(
            "🔄 *Statistics reset.*", parse_mode="Markdown", reply_markup=menu()
        )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "test":
        await query.edit_message_text(
            "🧪 *Mock test*\n\n"
            "Run `/test test-ok` for a mock approval, or `/test test-fail` "
            "for a mock decline.\n\n"
            "Never send real card numbers or CVVs.",
            parse_mode="Markdown",
            reply_markup=menu(),
        )
    elif query.data == "stats":
        await show_stats(update, context)
    elif query.data == "help":
        await query.edit_message_text(
            "❓ *Help*\n\n"
            "/start — Main menu\n"
            "/help — Help\n"
            "/test — Safe mock test\n"
            "/stats — Statistics\n"
            "/reset — Reset statistics\n\n"
            "This version is offline/mock-only and does not contact Stripe or other payment services.",
            parse_mode="Markdown",
            reply_markup=menu(),
        )
    elif query.data == "reset":
        await reset_stats(update, context)


async def reject_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❔ Unknown input. Use /help to see available commands.",
        reply_markup=menu(),
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.exception("Unhandled error", exc_info=context.error)


def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("test", run_test))
    application.add_handler(CommandHandler("stats", show_stats))
    application.add_handler(CommandHandler("reset", reset_stats))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reject_unknown))
    application.add_error_handler(error_handler)

    print("🤖 Safe mock Telegram bot started.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
