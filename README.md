# GOVIND OFFICIAL MP

An independent Telegram-compatible web client project built with FastAPI, Telethon and a responsive browser interface.

> This project is not affiliated with, endorsed by, or an official product of Telegram. Telegram is a trademark of its respective owner.

## Current foundation

- Phone-number login using Telegram MTProto authentication.
- Login-code verification and two-step verification password support.
- Encrypted storage of authorized Telethon StringSessions.
- Responsive chat list and conversation view.
- Read recent messages and send text messages.
- SQLite persistence for encrypted account sessions.
- Docker and Render deployment foundation.

This is an early development build, not a complete Telegram Web replacement. Media transfer, voice/video calls, stickers, contacts, group/channel administration, message editing/forwarding/deletion, live updates, multi-device controls and account registration are not implemented yet.

## Requirements

- Python 3.12+
- Telegram API credentials from https://my.telegram.org
- Persistent storage for the SQLite database in production.

## Run locally

1. Clone the repository and install dependencies: pip install -r requirements.txt
2. Copy .env.example to .env.
3. Set API_ID and API_HASH from my.telegram.org.
4. Generate APP_SECRET with Python secrets.token_urlsafe(48).
5. Generate SESSION_ENCRYPTION_KEY with Fernet.generate_key() from the cryptography package.
6. Export the variables and run: uvicorn app:app --host 0.0.0.0 --port 8000
7. Open http://localhost:8000.

## Deploy

The repository includes a Dockerfile and render.yaml. Configure API_ID, API_HASH, APP_SECRET, SESSION_ENCRYPTION_KEY, COOKIE_SECURE=true and DATABASE_PATH=/app/data/govind_official_mp.sqlite3. Mount persistent storage at /app/data.

## Security and platform notes

- Authentication is performed against Telegram MTProto servers. This site does not create Telegram accounts; use official Telegram apps for registration when required.
- Never share login codes or two-step passwords with administrators.
- Use HTTPS in production. Keep APP_SECRET and SESSION_ENCRYPTION_KEY private. Losing the encryption key makes stored sessions unrecoverable.
- Before public launch, add rate limiting, persistent multi-worker login challenges, hardened session controls, privacy tools and independent security testing.
- Follow Telegram API terms and applicable privacy laws.
