import os
import secrets
import string
import sqlite3
from datetime import datetime, timedelta, timezone

import aiohttp
from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import Message

BOT_TOKEN = os.environ["8854500916:AAFx7aAZOd-_2HUha10GtV86L85qfLNXvW4"]
ADMIN_IDS = {int(x.strip()) for x in os.getenv("7218406158", "").split(",") if x.strip()}
TEST_API_URL = os.getenv("TEST_API_URL", "").strip()
HTTP_PROXY = os.getenv("HTTP_PROXY", "").strip() or None
KEY_DAYS = int(os.getenv("KEY_DAYS", "30"))

DB_PATH = os.getenv("DB_PATH", "bot.db")

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
conn.execute("""
CREATE TABLE IF NOT EXISTS access_keys (
    key TEXT PRIMARY KEY,
    created_by INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    used_by INTEGER
)
""")
conn.commit()
conn.execute("""
CREATE TABLE IF NOT EXISTS banned_users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    banned_at TEXT NOT NULL
)
""")
conn.execute("""
CREATE TABLE IF NOT EXISTS sites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    active INTEGER NOT NULL DEFAULT 1
)
""")
conn.commit()

router = Router()

def now():
    return datetime.now(timezone.utc)

def make_key():
    alphabet = string.ascii_uppercase + string.digits
    while True:
        key = f"JAY-{''.join(secrets.choice(alphabet) for _ in range(4))}-{''.join(secrets.choice(alphabet) for _ in range(4))}"
        if not conn.execute("SELECT 1 FROM access_keys WHERE key=?", (key,)).fetchone():
            return key

def styled(title: str, lines: list[str]) -> str:
    return "<b>⚡ 𝙅𝘼𝙔 𝙋𝙍𝙄𝙑𝘼𝙏𝙀 𝘼𝙋𝙄 ⚡</b>\\n" + \
           "━━━━━━━━━━━━━━━━━━━━\\n" + \
           f"<b>{title}</b>\\n" + \
           "━━━━━━━━━━━━━━━━━━━━\\n" + \
           "\\n".join(f"<b>{line}</b>" for line in lines)

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def valid_key(key: str, user_id: int) -> bool:
    row = conn.execute(
        "SELECT expires_at, active, used_by FROM access_keys WHERE key=?",
        (key.strip().upper(),)
    ).fetchone()
    if not row:
        return False
    expires_at, active, used_by = row
    if not active or datetime.fromisoformat(expires_at) <= now():
        return False
    if used_by is not None and used_by != user_id:
        return False
    conn.execute("UPDATE access_keys SET used_by=? WHERE key=?", (user_id, key.strip().upper()))
    conn.commit()
    return True

def is_banned(user_id: int) -> bool:
    return bool(conn.execute("SELECT 1 FROM banned_users WHERE user_id=?", (user_id,)).fetchone())

def has_access(user_id: int) -> bool:

    row = conn.execute(
        "SELECT 1 FROM access_keys WHERE used_by=? AND active=1 AND expires_at>?",
        (user_id, now().isoformat())
    ).fetchone()
    return bool(row) or is_admin(user_id)

@router.message(Command("start"))
async def start(message: Message):
    await message.answer(
        "🔐 *JAY Private API Bot*\n\n"
        "Use `/activate JAY-XXXX-XXXX` to activate an access key.\n"
        "Then use `/test <text>` to send a harmless test payload to the configured authorized API.\n\n"
        "Admin: `/generate`, `/keys`, `/revoke KEY`",
        parse_mode="Markdown"
    )

@router.message(Command("activate"))
async def activate(message: Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) != 2:
        await message.answer("Usage: `/activate JAY-XXXX-XXXX`", parse_mode="Markdown")
        return
    key = parts[1].strip().upper()
    if valid_key(key, message.from_user.id):
        await message.answer("✅ Access activated.")
    else:
        await message.answer("❌ Invalid, expired, revoked, or already assigned key.")


@router.message(Command("key"))
async def key_command(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer(styled("⛔ 𝘼𝘿𝙈𝙄𝙉 𝙊𝙉𝙇𝙔", ["Use this command with an admin account."]), parse_mode="HTML")
        return
    parts = message.text.split()
    if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
        await message.answer("Usage: `/key DAYS QUANTITY`\nExample: `/key 30 5`", parse_mode="Markdown")
        return
    days, quantity = int(parts[1]), int(parts[2])
    if days < 1 or quantity < 1 or quantity > 100:
        await message.answer("❌ DAYS must be >= 1 and QUANTITY must be 1–100.")
        return
    created = now()
    expires = created + timedelta(days=days)
    keys = []
    for _ in range(quantity):
        key = make_key()
        conn.execute(
            "INSERT INTO access_keys(key, created_by, created_at, expires_at) VALUES(?,?,?,?)",
            (key, message.from_user.id, created.isoformat(), expires.isoformat())
        )
        keys.append(key)
    conn.commit()
    await message.answer(
        "🔑 *Generated Keys*\n\n" + "\n".join(f"`{k}`" for k in keys) +
        f"\n\nExpires: `{expires.date()}`", parse_mode="Markdown"
    )

@router.message(Command("ban"))
async def ban_command(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer(styled("⛔ 𝘼𝘿𝙈𝙄𝙉 𝙊𝙉𝙇𝙔", ["Use this command with an admin account."]), parse_mode="HTML")
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) != 2:
        await message.answer("Usage: `/ban USERNAME_OR_USER_ID`", parse_mode="Markdown")
        return
    target = parts[1].strip().lstrip("@")
    user_id = int(target) if target.isdigit() else None
    if user_id is None:
        row = conn.execute(
            "SELECT used_by FROM access_keys WHERE used_by IS NOT NULL AND 1=0"
        ).fetchone()
        await message.answer("⚠️ For reliable banning, provide the numeric Telegram user ID: `/ban 123456789`.")
        return
    conn.execute(
        "INSERT OR REPLACE INTO banned_users(user_id, username, banned_at) VALUES(?,?,?)",
        (user_id, target, now().isoformat())
    )
    conn.execute("UPDATE access_keys SET active=0 WHERE used_by=?", (user_id,))
    conn.commit()
    await message.answer(f"🚫 Banned `{user_id}` and revoked their active keys.", parse_mode="Markdown")

@router.message(Command("site"))
async def site_command(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer(styled("⛔ 𝘼𝘿𝙈𝙄𝙉 𝙊𝙉𝙇𝙔", ["Use this command with an admin account."]), parse_mode="HTML")
        return
    parts = message.text.split()
    if len(parts) == 1:
        rows = conn.execute("SELECT id, name, url, active FROM sites ORDER BY id").fetchall()
        if not rows:
            await message.answer("No sites configured.")
            return
        out = ["*Configured authorized test endpoints:*"]
        for sid, name, url, active in rows:
            out.append(f"`{sid}` {name} — {url} — {'on' if active else 'off'}")
        await message.answer("\n".join(out)[:3900], parse_mode="Markdown")
        return
    if parts[1].lower() == "add" and len(parts) >= 4:
        name = parts[2]
        url = parts[3]
        count = conn.execute("SELECT COUNT(*) FROM sites").fetchone()[0]
        if count >= 300:
            await message.answer("❌ Maximum 300 sites.")
            return
        try:
            conn.execute("INSERT INTO sites(name,url) VALUES(?,?)", (name, url))
            conn.commit()
            await message.answer("✅ Authorized test endpoint added.")
        except sqlite3.IntegrityError:
            await message.answer("❌ That URL already exists.")
        return
    if parts[1].lower() == "del" and len(parts) == 3 and parts[2].isdigit():
        cur = conn.execute("DELETE FROM sites WHERE id=?", (int(parts[2]),))
        conn.commit()
        await message.answer("✅ Deleted." if cur.rowcount else "❌ Site ID not found.")
        return
    await message.answer(
        "Usage:\n`/site`\n`/site add NAME URL`\n`/site del ID`",
        parse_mode="Markdown"
    )

@router.message(Command("gen"))
async def gen_test_ids(message: Message):
    if not has_access(message.from_user.id):
        await message.answer(styled("🔒 𝘼𝘾𝘾𝙀𝙎𝙎 𝘿𝙀𝙉𝙄𝙀𝘿", ["Activate a valid access key first."]), parse_mode="HTML")
        return
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Usage: `/gen QUANTITY`", parse_mode="Markdown")
        return
    quantity = int(parts[1])
    if quantity < 1 or quantity > 20000:
        await message.answer("❌ Quantity must be 1–20000.")
        return
    alphabet = string.ascii_uppercase + string.digits
    values = [
        "TEST-" + "".join(secrets.choice(alphabet) for _ in range(16))
        for _ in range(quantity)
    ]
    # Avoid an oversized Telegram message: send a TXT document.
    import io
    from aiogram.types import BufferedInputFile
    data = ("\n".join(values) + "\n").encode()
    await message.answer_document(
        BufferedInputFile(data, filename=f"test_ids_{quantity}.txt"),
        caption=f"Generated {quantity} random non-payment test IDs."
    )

@router.message(Command("chk"))
async def check_test_file(message: Message):
    if not has_access(message.from_user.id):
        await message.answer(styled("🔒 𝘼𝘾𝘾𝙀𝙎𝙎 𝘿𝙀𝙉𝙄𝙀𝘿", ["Activate a valid access key first."]), parse_mode="HTML")
        return
    if not TEST_API_URL:
        await message.answer("⚠️ TEST_API_URL is not configured.")
        return
    if not message.document:
        await message.answer("Send a `.txt` file with `/chk` as the caption. Maximum 20000 test IDs.")
        return
    if not message.document.file_name.lower().endswith(".txt"):
        await message.answer("❌ Only TXT files are supported.")
        return

    from aiogram.types import BufferedInputFile
    file = await message.bot.download(message.document)
    raw = file.read().decode("utf-8", errors="replace")
    items = [x.strip() for x in raw.splitlines() if x.strip()]
    if len(items) > 20000:
        await message.answer("❌ Maximum 20000 test IDs.")
        return

    results = []
    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for i, item in enumerate(items, 1):
            try:
                async with session.post(
                    TEST_API_URL,
                    json={"test_input": item},
                    proxy=HTTP_PROXY,
                    headers={"User-Agent": "JAY-Private-API-Bot/1.0"}
                ) as response:
                    body = (await response.text()).replace("\n", " ")[:300]
                    results.append(f"{i}. HTTP {response.status} — {body}")
            except Exception as exc:
                results.append(f"{i}. ERROR — {type(exc).__name__}")

    data = ("\n".join(results) + "\n").encode()
    await message.answer_document(
        BufferedInputFile(data, filename="check_results.txt"),
        caption=f"Checked {len(items)} authorized test IDs."
    )

@router.message(Command("generate"))
async def generate(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer(styled("⛔ 𝘼𝘿𝙈𝙄𝙉 𝙊𝙉𝙇𝙔", ["Use this command with an admin account."]), parse_mode="HTML")
        return
    key = make_key()
    created = now()
    expires = created + timedelta(days=KEY_DAYS)
    conn.execute(
        "INSERT INTO access_keys(key, created_by, created_at, expires_at) VALUES(?,?,?,?)",
        (key, message.from_user.id, created.isoformat(), expires.isoformat())
    )
    conn.commit()
    await message.answer(f"`{key}`\nExpires: `{expires.date()}`", parse_mode="Markdown")

@router.message(Command("keys"))
async def keys(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer(styled("⛔ 𝘼𝘿𝙈𝙄𝙉 𝙊𝙉𝙇𝙔", ["Use this command with an admin account."]), parse_mode="HTML")
        return
    rows = conn.execute(
        "SELECT key, expires_at, active, used_by FROM access_keys ORDER BY created_at DESC LIMIT 50"
    ).fetchall()
    if not rows:
        await message.answer("No keys.")
        return
    out = ["*Keys:*"]
    for key, exp, active, used_by in rows:
        status = "active" if active else "revoked"
        owner = str(used_by) if used_by else "unused"
        out.append(f"`{key}` — {status} — {owner} — {exp[:10]}")
    await message.answer("\n".join(out), parse_mode="Markdown")

@router.message(Command("revoke"))
async def revoke(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer(styled("⛔ 𝘼𝘿𝙈𝙄𝙉 𝙊𝙉𝙇𝙔", ["Use this command with an admin account."]), parse_mode="HTML")
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) != 2:
        await message.answer("Usage: `/revoke JAY-XXXX-XXXX`", parse_mode="Markdown")
        return
    key = parts[1].strip().upper()
    cur = conn.execute("UPDATE access_keys SET active=0 WHERE key=?", (key,))
    conn.commit()
    await message.answer("✅ Revoked." if cur.rowcount else "❌ Key not found.")


@router.message(Command("msp"))
async def mass_test(message: Message):
    """Mass-test up to 30 harmless inputs against the configured authorized test endpoint."""
    if not has_access(message.from_user.id):
        await message.answer(styled("🔒 𝘼𝘾𝘾𝙀𝙎𝙎 𝘿𝙀𝙉𝙄𝙀𝘿", ["Activate a valid access key first."]), parse_mode="HTML")
        return
    if not TEST_API_URL:
        await message.answer("⚠️ TEST_API_URL is not configured.")
        return

    raw = message.text.partition(" ")[2].strip()
    items = [x.strip() for x in raw.splitlines() if x.strip()]
    if len(items) == 1 and "," in items[0]:
        items = [x.strip() for x in items[0].split(",") if x.strip()]

    if not items:
        await message.answer("Usage:\n`/msp TEST1\\nTEST2\\n...`", parse_mode="Markdown")
        return
    if len(items) > 30:
        await message.answer("❌ Maximum 30 test inputs per `/msp` request.")
        return

    timeout = aiohttp.ClientTimeout(total=20)
    results = []
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for i, item in enumerate(items, 1):
                try:
                    async with session.post(
                        TEST_API_URL,
                        json={"test_input": item},
                        proxy=HTTP_PROXY,
                        headers={"User-Agent": "JAY-Private-API-Bot/1.0"}
                    ) as response:
                        body = (await response.text()).replace("\n", " ")[:500]
                        results.append(f"{i}. HTTP {response.status} — {body}")
                except Exception as exc:
                    results.append(f"{i}. ERROR — {type(exc).__name__}")

        # Keep the Telegram message within practical limits.
        output = "<b>🧪 𝙈𝘼𝙎𝙎 𝘼𝙋𝙄 𝙏𝙀𝙎𝙏 𝙍𝙀𝙎𝙐𝙇𝙏𝙎</b>\n━━━━━━━━━━━━━━━━━━━━\n" + "\n".join(f"<b>{r}</b>" for r in results)
        await message.answer(output[:3900], parse_mode="Markdown")
    except Exception:
        await message.answer("❌ Mass test failed.")

@router.message(Command("test"))
async def test_endpoint(message: Message):
    if not has_access(message.from_user.id):
        await message.answer(styled("🔒 𝘼𝘾𝘾𝙀𝙎𝙎 𝘿𝙀𝙉𝙄𝙀𝘿", ["Activate a valid access key first."]), parse_mode="HTML")
        return
    if not TEST_API_URL:
        await message.answer("⚠️ TEST_API_URL is not configured.")
        return

    parts = message.text.split(maxsplit=1)
    payload = {"test_input": parts[1] if len(parts) == 2 else "hello"}

    timeout = aiohttp.ClientTimeout(total=20)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                TEST_API_URL,
                json=payload,
                proxy=HTTP_PROXY,
                headers={"User-Agent": "JAY-Private-API-Bot/1.0"}
            ) as response:
                body = await response.text()
                body = body[:3500]
                await message.answer(
                    f"*HTTP {response.status}*\n```\n{body}\n```",
                    parse_mode="HTML"
                )
    except Exception as exc:
        await message.answer(f"❌ Request failed: `{type(exc).__name__}`", parse_mode="Markdown")

async def main():
    bot = Bot(BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
