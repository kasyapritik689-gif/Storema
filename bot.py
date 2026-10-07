import os
import sqlite3
import asyncio

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ==========================================
# CONFIG
# ==========================================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

OWNER_IDS = {
    int(x.strip())
    for x in os.getenv("OWNER_IDS", "").split(",")
    if x.strip()
}

MAX_ITEMS = 250
DB_FILE = "storage.db"


# ==========================================
# DATABASE
# ==========================================

db = sqlite3.connect(
    DB_FILE,
    check_same_thread=False
)

db.execute("""
CREATE TABLE IF NOT EXISTS allowed_users (
    user_id INTEGER PRIMARY KEY
)
""")

db.execute("""
CREATE TABLE IF NOT EXISTS batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

db.execute("""
CREATE TABLE IF NOT EXISTS batch_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER NOT NULL,
    item_type TEXT NOT NULL,
    file_id TEXT,
    text TEXT,
    caption TEXT,
    item_order INTEGER NOT NULL
)
""")

db.commit()


# ==========================================
# PERMISSION
# ==========================================

def is_owner(user_id):
    return user_id in OWNER_IDS


def is_allowed(user_id):

    if is_owner(user_id):
        return True

    row = db.execute(
        """
        SELECT user_id
        FROM allowed_users
        WHERE user_id=?
        """,
        (user_id,)
    ).fetchone()

    return row is not None


# ==========================================
# BATCH HELPERS
# ==========================================

def get_open_batch(user_id):

    return db.execute(
        """
        SELECT id
        FROM batches
        WHERE owner_id=?
        AND status='open'
        ORDER BY id DESC
        LIMIT 1
        """,
        (user_id,)
    ).fetchone()


def get_batch_count(batch_id):

    row = db.execute(
        """
        SELECT COUNT(*)
        FROM batch_items
        WHERE batch_id=?
        """,
        (batch_id,)
    ).fetchone()

    return row[0]


# ==========================================
# KEYBOARDS
# ==========================================

def main_keyboard():

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "➕ Create Batch",
                callback_data="create_batch"
            )
        ]
    ])


def batch_keyboard():

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "✅ Done",
                callback_data="batch_done"
            ),
            InlineKeyboardButton(
                "❌ Cancel",
                callback_data="batch_cancel"
            )
        ]
    ])


# ==========================================
# START
# ==========================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    args = context.args

    # ======================================
    # BATCH LINK
    # ======================================

    if args and args[0].startswith("b"):

        try:
            batch_id = int(args[0][1:])

        except ValueError:

            await update.message.reply_text(
                "❌ Invalid batch link."
            )

            return

        # Kisi bhi user ko completed batch dekhne dena
        batch = db.execute(
            """
            SELECT id
            FROM batches
            WHERE id=?
            AND status='complete'
            """,
            (batch_id,)
        ).fetchone()

        if not batch:

            await update.message.reply_text(
                "❌ Batch nahi mila."
            )

            return

        items = db.execute(
            """
            SELECT
                item_type,
                file_id,
                text,
                caption
            FROM batch_items
            WHERE batch_id=?
            ORDER BY item_order ASC
            """,
            (batch_id,)
        ).fetchall()

        if not items:

            await update.message.reply_text(
                "❌ Is batch mein koi content nahi hai."
            )

            return

        await update.message.reply_text(
            f"📦 Batch mein {len(items)} items hain.\n"
            "⏳ Content bheja ja raha hai..."
        )

        for item_type, file_id, text, caption in items:

            try:

                # PHOTO
                if item_type == "photo":

                    await context.bot.send_photo(
                        chat_id=user_id,
                        photo=file_id,
                        caption=caption or None,
                        protect_content=True
                    )

                # VIDEO
                elif item_type == "video":

                    await context.bot.send_video(
                        chat_id=user_id,
                        video=file_id,
                        caption=caption or None,
                        protect_content=True
                    )

                # DOCUMENT
                elif item_type == "document":

                    await context.bot.send_document(
                        chat_id=user_id,
                        document=file_id,
                        caption=caption or None,
                        protect_content=True
                    )

                # AUDIO
                elif item_type == "audio":

                    await context.bot.send_audio(
                        chat_id=user_id,
                        audio=file_id,
                        caption=caption or None,
                        protect_content=True
                    )

                # VOICE
                elif item_type == "voice":

                    await context.bot.send_voice(
                        chat_id=user_id,
                        voice=file_id,
                        caption=caption or None,
                        protect_content=True
                    )

                # ANIMATION / GIF
                elif item_type == "animation":

                    await context.bot.send_animation(
                        chat_id=user_id,
                        animation=file_id,
                        caption=caption or None,
                        protect_content=True
                    )

                # TEXT
                elif item_type == "text":

                    await context.bot.send_message(
                        chat_id=user_id,
                        text=text,
                        protect_content=True
                    )

                await asyncio.sleep(0.08)

            except Exception as e:

                print(
                    "SEND ERROR:",
                    e
                )

        await context.bot.send_message(
            chat_id=user_id,
            text="✅ Batch complete."
        )

        return

    # ======================================
    # NORMAL START
    # ======================================

    if not is_allowed(user_id):

        await update.message.reply_text(
            "👋 Welcome!\n\n"
            "🔗 Agar aapke paas private batch link hai, "
            "use open karein.\n\n"
            "❌ Aap apna content storage mein add nahi kar sakte."
        )

        return

    await update.message.reply_text(
        "🤖 Private Storage Bot\n\n"
        "📦 Multiple content ko ek Batch mein save karo.\n"
        "🔗 Done ke baad ek hi private link milega.",
        reply_markup=main_keyboard()
    )


# ==========================================
# CREATE BATCH
# ==========================================

async def create_batch(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    # Sirf owner / allowed user
    # batch create kar sakta hai

    if not is_allowed(user_id):

        await query.edit_message_text(
            "❌ Aapko storage use karne ki permission nahi hai."
        )

        return

    existing = get_open_batch(user_id)

    if existing:

        count = get_batch_count(
            existing[0]
        )

        await query.edit_message_text(
            f"⚠️ Aapka Batch already open hai.\n\n"
            f"📦 Items: {count}/{MAX_ITEMS}\n\n"
            "Ab content bhejte raho.\n"
            "Sab complete hone par ✅ Done dabao.",
            reply_markup=batch_keyboard()
        )

        return

    # New batch

    cur = db.execute(
        """
        INSERT INTO batches
        (
            owner_id,
            status
        )
        VALUES
        (
            ?,
            'open'
        )
        """,
        (user_id,)
    )

    db.commit()

    batch_id = cur.lastrowid

    await query.edit_message_text(
        "📦 BATCH CREATED!\n\n"
        "📤 Ab apni saari files/photos/videos/documents/text bhejo.\n\n"
        "✅ Multiple files ek saath select karke bhej sakte ho.\n"
        f"📦 Maximum {MAX_ITEMS} items.\n\n"
        "Sab content bhejne ke baad:\n"
        "👉 ✅ Done dabao",
        reply_markup=batch_keyboard()
    )


# ==========================================
# SAVE CONTENT
# ==========================================

async def save_content(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    message = update.message

    user_id = update.effective_user.id

    # IMPORTANT:
    # Sirf owner / allowed users save kar sakte hain

    if not is_allowed(user_id):

        return

    batch = get_open_batch(user_id)

    if not batch:

        await message.reply_text(
            "📦 Pehle ➕ Create Batch par click karo."
        )

        return

    batch_id = batch[0]

    current_count = get_batch_count(
        batch_id
    )

    if current_count >= MAX_ITEMS:

        await message.reply_text(
            f"❌ Batch limit {MAX_ITEMS} items hai.\n\n"
            "Pehle ✅ Done dabao."
        )

        return

    item_order = current_count + 1

    item_type = None
    file_id = None
    text = None
    caption = None

    # ======================================
    # PHOTO
    # ======================================

    if message.photo:

        item_type = "photo"

        file_id = message.photo[-1].file_id

        caption = message.caption

    # ======================================
    # VIDEO
    # ======================================

    elif message.video:

        item_type = "video"

        file_id = message.video.file_id

        caption = message.caption

    # ======================================
    # DOCUMENT
    # ======================================

    elif message.document:

        item_type = "document"

        file_id = message.document.file_id

        caption = message.caption

    # ======================================
    # AUDIO
    # ======================================

    elif message.audio:

        item_type = "audio"

        file_id = message.audio.file_id

        caption = message.caption

    # ======================================
    # VOICE
    # ======================================

    elif message.voice:

        item_type = "voice"

        file_id = message.voice.file_id

        caption = message.caption

    # ======================================
    # GIF / ANIMATION
    # ======================================

    elif message.animation:

        item_type = "animation"

        file_id = message.animation.file_id

        caption = message.caption

    # ======================================
    # TEXT
    # ======================================

    elif message.text:

        item_type = "text"

        text = message.text

    else:

        await message.reply_text(
            "⚠️ Ye content type abhi supported nahi hai."
        )

        return

    # ======================================
    # SAVE TO DATABASE
    # ======================================

    db.execute(
        """
        INSERT INTO batch_items
        (
            batch_id,
            item_type,
            file_id,
            text,
            caption,
            item_order
        )
        VALUES
        (
            ?,
            ?,
            ?,
            ?,
            ?,
            ?
        )
        """,
        (
            batch_id,
            item_type,
            file_id,
            text,
            caption,
            item_order
        )
    )

    db.commit()

    new_count = current_count + 1

    await message.reply_text(
        f"✅ Saved: {new_count}/{MAX_ITEMS}\n\n"
        "📦 Isi Batch mein save ho gaya.\n"
        "Aur content bhej sakte ho.\n\n"
        "Sab complete hone par ✅ Done dabao.",
        reply_markup=batch_keyboard()
    )


# ==========================================
# DONE
# ==========================================

async def batch_done(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    # Sirf owner / allowed user
    # batch complete kar sakta hai

    if not is_allowed(user_id):

        await query.edit_message_text(
            "❌ Permission denied."
        )

        return

    batch = get_open_batch(user_id)

    if not batch:

        await query.edit_message_text(
            "❌ Koi open Batch nahi hai."
        )

        return

    batch_id = batch[0]

    count = get_batch_count(
        batch_id
    )

    if count == 0:

        await query.edit_message_text(
            "❌ Batch empty hai.\n"
            "Pehle content bhejo."
        )

        return

    # Complete batch

    db.execute(
        """
        UPDATE batches
        SET status='complete'
        WHERE id=?
        """,
        (batch_id,)
    )

    db.commit()

    bot_info = await context.bot.get_me()

    link = (
        f"https://t.me/"
        f"{bot_info.username}"
        f"?start=b{batch_id}"
    )

    await query.edit_message_text(
        "🎉 BATCH READY!\n\n"
        f"📦 Total items: {count}\n\n"
        "🔗 ONE LINK:\n"
        f"{link}\n\n"
        "👀 Is link ko koi bhi open kar sakta hai.\n"
        "📱 Same link har phone par chalega.\n"
        "❌ Har file ka alag link nahi hai."
    )


# ==========================================
# CANCEL
# ==========================================

async def batch_cancel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    if not is_allowed(user_id):

        await query.edit_message_text(
            "❌ Permission denied."
        )

        return

    batch = get_open_batch(user_id)

    if not batch:

        await query.edit_message_text(
            "❌ Koi open Batch nahi hai."
        )

        return

    batch_id = batch[0]

    db.execute(
        """
        DELETE FROM batch_items
        WHERE batch_id=?
        """,
        (batch_id,)
    )

    db.execute(
        """
        DELETE FROM batches
        WHERE id=?
        """,
        (batch_id,)
    )

    db.commit()

    await query.edit_message_text(
        "❌ Batch cancel kar diya gaya."
    )


# ==========================================
# ALLOW USER
# ==========================================

async def allow_user(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_id = update.effective_user.id

    if not is_owner(user_id):

        return

    if not context.args:

        await update.message.reply_text(
            "Use:\n"
            "/allow USER_ID"
        )

        return

    try:

        target_id = int(
            context.args[0]
        )

    except ValueError:

        await update.message.reply_text(
            "❌ Invalid User ID."
        )

        return

    db.execute(
        """
        INSERT OR IGNORE INTO allowed_users
        (user_id)
        VALUES
        (?)
        """,
        (target_id,)
    )

    db.commit()

    await update.message.reply_text(
        f"✅ User {target_id} ko "
        "storage permission mil gayi."
    )


# ==========================================
# DENY USER
# ==========================================

async def deny_user(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_id = update.effective_user.id

    if not is_owner(user_id):

        return

    if not context.args:

        await update.message.reply_text(
            "Use:\n"
            "/deny USER_ID"
        )

        return

    try:

        target_id = int(
            context.args[0]
        )

    except ValueError:

        await update.message.reply_text(
            "❌ Invalid User ID."
        )

        return

    db.execute(
        """
        DELETE FROM allowed_users
        WHERE user_id=?
        """,
        (target_id,)
    )

    db.commit()

    await update.message.reply_text(
        f"❌ User {target_id} ki "
        "storage permission hata di gayi."
    )


# ==========================================
# USERS
# ==========================================

async def users(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_id = update.effective_user.id

    if not is_owner(user_id):

        return

    rows = db.execute(
        """
        SELECT user_id
        FROM allowed_users
        ORDER BY user_id
        """
    ).fetchall()

    if not rows:

        await update.message.reply_text(
            "👥 Abhi koi allowed user nahi hai."
        )

        return

    result = "👥 Allowed Users:\n\n"

    for row in rows:

        result += f"{row[0]}\n"

    await update.message.reply_text(
        result
    )


# ==========================================
# MY ID
# ==========================================

async def myid(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "🆔 Your Telegram ID:\n\n"
        f"{update.effective_user.id}"
    )


# ==========================================
# MAIN
# ==========================================

def main():

    if not BOT_TOKEN:

        print(
            "❌ ERROR: BOT_TOKEN .env mein missing hai."
        )

        return

    app = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .build()
    )

    # Commands

    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    app.add_handler(
        CommandHandler(
            "allow",
            allow_user
        )
    )

    app.add_handler(
        CommandHandler(
            "deny",
            deny_user
        )
    )

    app.add_handler(
        CommandHandler(
            "users",
            users
        )
    )

    app.add_handler(
        CommandHandler(
            "myid",
            myid
        )
    )

    # Create Batch

    app.add_handler(
        CallbackQueryHandler(
            create_batch,
            pattern="^create_batch$"
        )
    )

    # Done

    app.add_handler(
        CallbackQueryHandler(
            batch_done,
            pattern="^batch_done$"
        )
    )

    # Cancel

    app.add_handler(
        CallbackQueryHandler(
            batch_cancel,
            pattern="^batch_cancel$"
        )
    )

    # Content

    app.add_handler(
        MessageHandler(
            filters.ALL & ~filters.COMMAND,
            save_content
        )
    )

    print(
        "🤖 Bot is running..."
    )

    app.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


# ==========================================
# START BOT
# ==========================================

if __name__ == "__main__":
    main()
