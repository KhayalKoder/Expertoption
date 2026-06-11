import os
import logging
import asyncio
from datetime import datetime
from openai import OpenAI
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ─── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─── Config ────────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
KIMI_API_KEY   = os.getenv("KIMI_API_KEY",   "YOUR_KIMI_API_KEY")
KIMI_BASE_URL  = "https://api.moonshot.cn/v1"

# ─── Kimi client ───────────────────────────────────────────────────────────────
kimi = OpenAI(api_key=KIMI_API_KEY, base_url=KIMI_BASE_URL)

SYSTEM_PROMPT = """Sən Expert Option platforması üçün professional ticarət analitiküdür.
Sənin vəzifən:
- İstifadəçinin verdiyi aktiv (valyuta cütü, kriptovalyuta, səhm) üçün dəqiq CALL/PUT siqnalı vermək
- Texniki analiz əsasında giriş nöqtəsi, müddət (1-5 dəqiqə) və ehtimal faizi göstərmək
- Qısa, aydın və peşəkar Azərbaycan dilində cavab vermək

Cavab formatı HƏMİŞƏ belə olmalıdır:
📊 *AKTİV:* [aktiv adı]
📈/📉 *SİQNAL:* CALL/PUT
⏱ *MÜDDƏT:* X dəqiqə
🎯 *GİRİŞ:* [qiymət/vaxt]
💯 *EHTIMAL:* XX%
📝 *ƏSAS:* [qısa texniki əsaslandırma]
⚠️ *XƏBƏRDARLIQ:* Ticarət risk daşıyır. Yalnız itirməyə hazır olduğunuz məbləği investisiya edin."""

# ─── Yardımçı funksiyalar ──────────────────────────────────────────────────────

def get_kimi_signal(user_message: str) -> str:
    try:
        resp = kimi.chat.completions.create(
            model="moonshot-v1-8k",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_message},
            ],
            temperature=0.3,
        )
        return resp.choices[0].message.content
    except Exception as e:
        logger.error("Kimi API xətası: %s", e)
        return "❌ Kimi API ilə əlaqə qurularkən xəta baş verdi. Bir az sonra yenidən cəhd edin."


def main_keyboard():
    buttons = [
        [
            InlineKeyboardButton("📊 Siqnal Al",    callback_data="signal"),
            InlineKeyboardButton("📈 Aktivlər",     callback_data="assets"),
        ],
        [
            InlineKeyboardButton("⚙️ Parametrlər", callback_data="settings"),
            InlineKeyboardButton("❓ Kömək",        callback_data="help"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def assets_keyboard():
    pairs = [
        ("EUR/USD", "EUR/USD"), ("GBP/USD", "GBP/USD"),
        ("USD/JPY", "USD/JPY"), ("AUD/USD", "AUD/USD"),
        ("BTC/USD", "BTC/USD"), ("ETH/USD", "ETH/USD"),
        ("GOLD",    "GOLD"),    ("OIL",     "OIL"),
    ]
    buttons = [
        [InlineKeyboardButton(name, callback_data=f"asset_{val}") for name, val in row]
        for row in zip(pairs[::2], pairs[1::2])
    ]
    buttons.append([InlineKeyboardButton("🔙 Geri", callback_data="back")])
    return InlineKeyboardMarkup(buttons)


# ─── Handlers ──────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    welcome = (
        f"👋 Salam, *{user.first_name}*!\n\n"
        "🤖 Bu bot *Kimi AI* texnologiyası əsasında\n"
        "*Expert Option* platforması üçün ticarət siqnalları verir.\n\n"
        "📌 İstifadə qaydası:\n"
        "• Aktiv adı yazın (məs: `EUR/USD`)\n"
        "• Və ya aşağıdakı menyudan seçin\n\n"
        "⚠️ _Ticarət risk daşıyır. Bu bot yalnız məlumat məqsədi daşıyır._"
    )
    await update.message.reply_text(
        welcome, parse_mode="Markdown", reply_markup=main_keyboard()
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "📖 *KÖMƏK MƏLUMATı*\n\n"
        "🔹 `/start` — Botu başladın\n"
        "🔹 `/signal <aktiv>` — Siqnal alın\n"
        "  _Nümunə: `/signal EUR/USD`_\n"
        "🔹 `/assets` — Aktivlər siyahısı\n"
        "🔹 `/help` — Bu mesaj\n\n"
        "💬 Yaxud sadəcə aktiv adını yazın:\n"
        "`EUR/USD`, `BTC/USD`, `GOLD` ...\n\n"
        "⚙️ *Powered by Kimi AI (Moonshot)*"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def signal_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.args:
        asset = " ".join(context.args).upper()
        await _send_signal(update, context, asset)
    else:
        await update.message.reply_text(
            "📊 Hansı aktiv üçün siqnal istəyirsiniz?\nNümunə: `/signal EUR/USD`",
            parse_mode="Markdown",
            reply_markup=assets_keyboard(),
        )


async def assets_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "📈 *Aktiv seçin:*",
        parse_mode="Markdown",
        reply_markup=assets_keyboard(),
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip().upper()
    await _send_signal(update, context, text)


async def _send_signal(
    update: Update, context: ContextTypes.DEFAULT_TYPE, asset: str
) -> None:
    thinking = await update.effective_message.reply_text(
        f"⏳ *{asset}* üçün analiz edilir...", parse_mode="Markdown"
    )
    prompt = f"{asset} aktivini analiz et və indi ticarət siqnalı ver. Cari vaxt: {datetime.utcnow().strftime('%H:%M UTC')}"
    signal = await asyncio.to_thread(get_kimi_signal, prompt)
    await thinking.delete()
    back_btn = InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("🔄 Yeni Siqnal", callback_data=f"asset_{asset}"),
            InlineKeyboardButton("🏠 Ana Menyu",   callback_data="back"),
        ]]
    )
    await update.effective_message.reply_text(
        signal, parse_mode="Markdown", reply_markup=back_btn
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "signal":
        await query.edit_message_text(
            "📊 *Aktiv seçin:*", parse_mode="Markdown", reply_markup=assets_keyboard()
        )
    elif data == "assets":
        await query.edit_message_text(
            "📈 *Aktivlər siyahısı:*", parse_mode="Markdown", reply_markup=assets_keyboard()
        )
    elif data == "help":
        await query.edit_message_text(
            "📖 *Kömək*\n\nAktiv adı yazın və ya menyudan seçin.",
            parse_mode="Markdown",
            reply_markup=main_keyboard(),
        )
    elif data == "settings":
        await query.edit_message_text(
            "⚙️ *Parametrlər*\n\n_Hazırda bütün parametrlər standart olaraq qurulub._",
            parse_mode="Markdown",
            reply_markup=main_keyboard(),
        )
    elif data == "back":
        await query.edit_message_text(
            "🏠 *Ana Menyu*\nAktiv seçin və ya siqnal alın:",
            parse_mode="Markdown",
            reply_markup=main_keyboard(),
        )
    elif data.startswith("asset_"):
        asset = data.replace("asset_", "")
        await _send_signal(update, context, asset)


# ─── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start",  start))
    app.add_handler(CommandHandler("help",   help_command))
    app.add_handler(CommandHandler("signal", signal_command))
    app.add_handler(CommandHandler("assets", assets_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Bot işə düşdü...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
