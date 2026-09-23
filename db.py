import sqlite3
import secrets
import time
import os

DB_PATH = os.environ.get("DB_PATH", "shop.db")

START_BALANCE = 100
LINK_TTL = 60       # секунд — ссылка регистрации живёт минуту
MINE_SECONDS = 15 * 60
COOL_SECONDS = 30 * 60
MINE_REWARD = 10

SHOP_ITEMS = [
    {"id": "booster",   "name": "Ускоритель майнинга", "price": 50},
    {"id": "shield",    "name": "Щит от перезарядки",  "price": 80},
    {"id": "skin_gold", "name": "Золотой скин",        "price": 200},
]


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                balance INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL,
                state TEXT NOT NULL DEFAULT 'idle',
                mine_start INTEGER,
                cool_start INTEGER,
                last_counted INTEGER
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                item_id TEXT NOT NULL,
                bought_at INTEGER NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reg_tokens (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                used INTEGER NOT NULL DEFAULT 0
            )
        """)


# ---------- Пользователь / валюта ----------

def get_or_create_user(user_id, username):
    with db() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO users (user_id, username, balance, created_at) VALUES (?, ?, ?, ?)",
                (user_id, username or "", START_BALANCE, int(time.time())),
            )
            return START_BALANCE
        if username and row["username"] != username:
            conn.execute("UPDATE users SET username = ? WHERE user_id = ?", (username, user_id))
        return row["balance"]


def get_balance(user_id):
    with db() as conn:
        row = conn.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return row["balance"] if row else 0


def change_balance(user_id, delta):
    with db() as conn:
        conn.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (delta, user_id))
        row = conn.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return row["balance"]


# ---------- Магазин ----------

def find_item(item_id):
    for item in SHOP_ITEMS:
        if item["id"] == item_id:
            return item
    return None


def record_purchase(user_id, item_id):
    with db() as conn:
        conn.execute(
            "INSERT INTO purchases (user_id, item_id, bought_at) VALUES (?, ?, ?)",
            (user_id, item_id, int(time.time())),
        )


def count_item(user_id, item_id):
    with db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM purchases WHERE user_id = ? AND item_id = ?",
            (user_id, item_id),
        ).fetchone()
        return row["c"]


def get_inventory(user_id):
    return [
        {"id": item["id"], "name": item["name"], "count": count_item(user_id, item["id"])}
        for item in SHOP_ITEMS
        if count_item(user_id, item["id"]) > 0
    ]


def get_username(user_id):
    with db() as conn:
        row = conn.execute("SELECT username, created_at FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if row is None:
            return None, None
        return row["username"], row["created_at"]


# ---------- Ссылка регистрации (бот -> сайт) ----------

def create_reg_token(user_id):
    with db() as conn:
        conn.execute("UPDATE reg_tokens SET used = 1 WHERE user_id = ? AND used = 0", (user_id,))
        token = secrets.token_urlsafe(24)
        expires_at = int(time.time()) + LINK_TTL
        conn.execute(
            "INSERT INTO reg_tokens (token, user_id, expires_at, used) VALUES (?, ?, ?, 0)",
            (token, user_id, expires_at),
        )
        return token, expires_at


def verify_reg_token(token):
    with db() as conn:
        row = conn.execute("SELECT * FROM reg_tokens WHERE token = ?", (token,)).fetchone()
        if row is None or row["used"] or row["expires_at"] < int(time.time()):
            return None
        conn.execute("UPDATE reg_tokens SET used = 1 WHERE token = ?", (token,))
        return row["user_id"]


def peek_reg_token(token):
    """Проверить токен без пометки 'использован' — безопасно для GET
    (в т.ч. для автоматических запросов превью ссылки в мессенджере)."""
    with db() as conn:
        row = conn.execute("SELECT * FROM reg_tokens WHERE token = ?", (token,)).fetchone()
        if row is None or row["used"] or row["expires_at"] < int(time.time()):
            return None
        return row["user_id"]


# ---------- Майнинг (используется сайтом) ----------

def get_mine_state(user_id):
    now = int(time.time())
    with db() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        state = row["state"]
        mine_start = row["mine_start"]
        cool_start = row["cool_start"]
        last_counted = row["last_counted"]
        balance = row["balance"]

        if state == "mining" and mine_start is not None:
            elapsed = now - mine_start
            if elapsed >= MINE_SECONDS:
                if last_counted != mine_start:
                    balance += MINE_REWARD
                    last_counted = mine_start
                state = "cooldown"
                cool_start = mine_start + MINE_SECONDS
                conn.execute(
                    "UPDATE users SET state=?, cool_start=?, balance=?, last_counted=? WHERE user_id=?",
                    (state, cool_start, balance, last_counted, user_id),
                )

        if state == "cooldown" and cool_start is not None:
            elapsed = now - cool_start
            if elapsed >= COOL_SECONDS:
                state = "idle"
                conn.execute("UPDATE users SET state=? WHERE user_id=?", (state, user_id))

        remaining = 0
        if state == "mining":
            remaining = max(0, MINE_SECONDS - (now - mine_start))
        elif state == "cooldown":
            remaining = max(0, COOL_SECONDS - (now - cool_start))

        return {"state": state, "remaining": remaining, "balance": balance}


def start_mining(user_id):
    now = int(time.time())
    with db() as conn:
        row = conn.execute("SELECT state FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if row is None or row["state"] != "idle":
            return False
        conn.execute("UPDATE users SET state='mining', mine_start=? WHERE user_id=?", (now, user_id))
        return True
