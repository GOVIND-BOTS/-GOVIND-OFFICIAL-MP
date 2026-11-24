import asyncio
import os
import secrets
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from io import BytesIO

from cryptography.fernet import Fernet, InvalidToken
from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.sessions import SessionMiddleware
from telethon import TelegramClient
from telethon.errors import FloodWaitError, PhoneCodeExpiredError, PhoneCodeInvalidError, PhoneNumberInvalidError, SessionPasswordNeededError
from telethon.sessions import StringSession

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("DATABASE_PATH", str(ROOT / "data" / "accounts.sqlite3")))
API_ID = int(os.getenv("API_ID", "0") or "0")
API_HASH = os.getenv("API_HASH", "")
APP_SECRET = os.getenv("APP_SECRET", "")
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() == "true"
KEY = os.getenv("SESSION_ENCRYPTION_KEY", "")
if not API_ID or not API_HASH or not APP_SECRET or not KEY:
    raise RuntimeError("Configure API_ID, API_HASH, APP_SECRET and SESSION_ENCRYPTION_KEY.")
try:
    cipher = Fernet(KEY.encode())
except (ValueError, TypeError) as exc:
    raise RuntimeError("SESSION_ENCRYPTION_KEY must be a valid Fernet key.") from exc

pending = {}
clients = {}
locks = {}


def connect_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with connect_db() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS accounts (user_id INTEGER PRIMARY KEY, phone TEXT NOT NULL, session BLOB NOT NULL)")
        conn.commit()


@asynccontextmanager
async def lifespan(_app):
    init_db()
    yield
    for client in list(clients.values()):
        if client.is_connected():
            await client.disconnect()


app = FastAPI(title="GOVIND OFFICIAL MP", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=APP_SECRET, session_cookie="govind_mp_session", max_age=604800, same_site="lax", https_only=COOKIE_SECURE)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


class PhoneBody(BaseModel):
    phone: str = Field(min_length=5, max_length=32)


class CodeBody(BaseModel):
    phone: str
    code: str = Field(min_length=1, max_length=16)


class PasswordBody(BaseModel):
    phone: str
    password: str = Field(min_length=1, max_length=256)


class MessageBody(BaseModel):
    chat_id: int
    message: str = Field(min_length=1, max_length=4096)


class MessageAction(BaseModel):
    chat_id: int
    message_id: int


class EditBody(MessageAction):
    text: str = Field(min_length=1, max_length=4096)


class ForwardBody(BaseModel):
    from_chat_id: int
    message_id: int
    to_chat_id: int


def csrf(request):
    expected = request.session.get("csrf", "")
    supplied = request.headers.get("x-csrf-token", "")
    if not expected or not secrets.compare_digest(expected, supplied):
        raise HTTPException(403, "Invalid request token. Refresh the page.")


def get_pending(phone):
    value = pending.get(phone)
    if not value:
        raise HTTPException(400, "Login request expired. Request a new code.")
    return value


async def complete_login(request, phone, client):
    user = await client.get_me()
    encrypted = cipher.encrypt(client.session.save().encode())
    with connect_db() as conn:
        conn.execute("INSERT INTO accounts(user_id, phone, session) VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET phone=excluded.phone, session=excluded.session", (user.id, phone, encrypted))
        conn.commit()
    pending.pop(phone, None)
    await client.disconnect()
    request.session.clear()
    request.session["user_id"] = user.id
    request.session["csrf"] = secrets.token_urlsafe(32)
    return {"ok": True, "csrf": request.session["csrf"], "user": {"id": user.id, "name": user.first_name or ""}}


async def get_client(request):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(401, "Please sign in first.")
    if user_id in clients and clients[user_id].is_connected():
        return clients[user_id]
    with connect_db() as conn:
        row = conn.execute("SELECT session FROM accounts WHERE user_id=?", (user_id,)).fetchone()
    if not row:
        request.session.clear()
        raise HTTPException(401, "Session not found. Sign in again.")
    try:
        saved = cipher.decrypt(row["session"]).decode()
    except InvalidToken:
        raise HTTPException(500, "Could not decrypt the saved session.")
    lock = locks.setdefault(user_id, asyncio.Lock())
    async with lock:
        client = clients.get(user_id)
        if client is None or not client.is_connected():
            client = TelegramClient(StringSession(saved), API_ID, API_HASH)
            await client.connect()
            if not await client.is_user_authorized():
                await client.disconnect()
                with connect_db() as conn:
                    conn.execute("DELETE FROM accounts WHERE user_id=?", (user_id,))
                    conn.commit()
                request.session.clear()
                raise HTTPException(401, "Telegram session expired. Sign in again.")
            clients[user_id] = client
    return client


@app.get("/")
async def home():
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "GOVIND OFFICIAL MP"}


@app.get("/api/csrf")
async def csrf_token(request: Request):
    if "csrf" not in request.session:
        request.session["csrf"] = secrets.token_urlsafe(32)
    return {"csrf": request.session["csrf"]}


@app.post("/api/auth/send-code")
async def send_code(body: PhoneBody, request: Request):
    csrf(request)
    phone = body.phone.strip()
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    try:
        await client.connect()
        sent = await client.send_code_request(phone)
        pending[phone] = {"client": client, "hash": sent.phone_code_hash}
        return {"ok": True, "message": "Telegram login code sent. Check your Telegram app."}
    except PhoneNumberInvalidError:
        await client.disconnect()
        raise HTTPException(400, "Invalid phone number. Include the country code.")
    except FloodWaitError as exc:
        await client.disconnect()
        raise HTTPException(429, f"Telegram rate limit. Try again in {exc.seconds} seconds.")
    except Exception:
        await client.disconnect()
        raise HTTPException(502, "Telegram could not send a code. Please try again later.")


@app.post("/api/auth/verify-code")
async def verify_code(body: CodeBody, request: Request):
    csrf(request)
    item = get_pending(body.phone)
    try:
        await item["client"].sign_in(body.phone, body.code.strip(), phone_code_hash=item["hash"])
        return await complete_login(request, body.phone, item["client"])
    except SessionPasswordNeededError:
        return {"ok": False, "password_required": True, "message": "Two-step verification password required."}
    except (PhoneCodeInvalidError, PhoneCodeExpiredError):
        raise HTTPException(400, "The login code is invalid or expired.")
    except FloodWaitError as exc:
        raise HTTPException(429, f"Telegram rate limit. Try again in {exc.seconds} seconds.")
    except Exception:
        raise HTTPException(400, "Could not verify this code. Request a new code and try again.")


@app.post("/api/auth/verify-password")
async def verify_password(body: PasswordBody, request: Request):
    csrf(request)
    item = get_pending(body.phone)
    try:
        await item["client"].sign_in(password=body.password)
        return await complete_login(request, body.phone, item["client"])
    except Exception:
        raise HTTPException(400, "Incorrect password or Telegram verification failed.")


@app.get("/api/me")
async def me(request: Request):
    user = await (await get_client(request)).get_me()
    return {"id": user.id, "name": " ".join(filter(None, [user.first_name, user.last_name])), "username": user.username, "phone": user.phone}


@app.get("/api/dialogs")
async def dialogs(request: Request):
    client = await get_client(request)
    result = []
    async for dialog in client.iter_dialogs(limit=80):
        entity = dialog.entity
        result.append({"id": dialog.id, "name": dialog.name or "Unknown", "unread": dialog.unread_count, "message": dialog.message.message if dialog.message and dialog.message.message else "", "date": dialog.date.isoformat() if dialog.date else "", "kind": "channel" if getattr(entity, "broadcast", False) else "group" if getattr(entity, "megagroup", False) or getattr(entity, "title", None) else "private"})
    return {"chats": result}


@app.get("/api/messages/{chat_id}")
async def messages(chat_id: int, request: Request):
    client = await get_client(request)
    result = []
    async for message in client.iter_messages(chat_id, limit=50, reverse=True):
        result.append({"id": message.id, "text": message.message or "", "out": bool(message.out), "date": message.date.isoformat() if message.date else "", "media": bool(message.media)})
    return {"messages": result}


@app.post("/api/messages")
async def send_message(body: MessageBody, request: Request):
    csrf(request)
    sent = await (await get_client(request)).send_message(body.chat_id, body.message)
    return {"ok": True, "id": sent.id}


@app.post("/api/logout")
async def logout(request: Request):
    csrf(request)
    user_id = request.session.get("user_id")
    client = clients.pop(user_id, None)
    if client and client.is_connected():
        await client.disconnect()
    request.session.clear()
    return {"ok": True}


@app.get("/api/contacts")
async def contacts(request: Request):
    client = await get_client(request)
    result = []
    async for user in client.iter_contacts():
        result.append({"id": user.id, "name": " ".join(filter(None, [user.first_name, user.last_name])), "username": user.username, "phone": user.phone})
    return {"contacts": result}


@app.post("/api/messages/edit")
async def edit_message(body: EditBody, request: Request):
    csrf(request)
    client = await get_client(request)
    try:
        await client.edit_message(body.chat_id, body.message_id, body.text)
        return {"ok": True}
    except Exception:
        raise HTTPException(400, "Message could not be edited. You can only edit your own eligible messages.")


@app.post("/api/messages/delete")
async def delete_message(body: MessageAction, request: Request):
    csrf(request)
    client = await get_client(request)
    try:
        await client.delete_messages(body.chat_id, [body.message_id], revoke=True)
        return {"ok": True}
    except Exception:
        raise HTTPException(400, "Message could not be deleted.")


@app.post("/api/messages/forward")
async def forward_message(body: ForwardBody, request: Request):
    csrf(request)
    client = await get_client(request)
    try:
        await client.forward_messages(body.to_chat_id, body.message_id, body.from_chat_id)
        return {"ok": True}
    except Exception:
        raise HTTPException(400, "Message could not be forwarded.")


@app.post("/api/media")
async def send_media(request: Request, chat_id: int, file: UploadFile = File(...)):
    csrf(request)
    if not file.filename:
        raise HTTPException(400, "Choose a file to upload.")
    content = await file.read(20 * 1024 * 1024 + 1)
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(413, "Files must be 20 MB or smaller.")
    if not content:
        raise HTTPException(400, "The selected file is empty.")
    client = await get_client(request)
    try:
        sent = await client.send_file(chat_id, BytesIO(content), file_name=Path(file.filename).name, caption="")
        return {"ok": True, "id": sent.id}
    except Exception:
        raise HTTPException(400, "Telegram could not send this file.")
