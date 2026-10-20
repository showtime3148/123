"""SQLite-backed server access or stateless access for a one-day Vercel app."""
import hashlib
import hmac
import os
import secrets
import sqlite3
import time
import threading
from contextlib import closing
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

SESSION_SECONDS = 12 * 60 * 60
COOKIE = "gce_session"


class AccessControl:
    def __init__(self, environ=None):
        env = os.environ if environ is None else environ
        self.serverless = env.get("VERCEL") == "1" or env.get("GCE_HOSTING") == "vercel"
        self.public = self.serverless or env.get("GCE_PUBLIC") == "1"
        self.password = env.get("GCE_ACCESS_PASSWORD", "")
        self.secret = env.get("GCE_SESSION_SECRET", "")
        if self.serverless and not self.secret and env.get("GCE_OPENAI_API_KEY"):
            self.secret = hmac.new(env["GCE_OPENAI_API_KEY"].encode(),
                                   b"gce-session-signing-v1", hashlib.sha256).hexdigest()
        self.key_mode = env.get("GCE_KEY_MODE", "shared" if self.serverless else "individual")
        self.model = env.get("GCE_MODEL", "gpt-4.1-mini")
        self.daily_limit = int(env.get("GCE_DAILY_WEB_LIMIT", "100"))
        self.hosts = ["localhost", "127.0.0.1", "testserver"]
        self.hosts += [host.strip() for host in env.get("GCE_ALLOWED_HOSTS", "").split(",") if host.strip()]
        if env.get("RENDER_EXTERNAL_HOSTNAME"):
            self.hosts.append(env["RENDER_EXTERNAL_HOSTNAME"])
        for name in ("VERCEL_URL", "VERCEL_PROJECT_PRODUCTION_URL", "VERCEL_BRANCH_URL"):
            if env.get(name):
                self.hosts.append(env[name])
        self.close_at = None
        if env.get("GCE_CLOSE_AT"):
            closing_time = datetime.fromisoformat(env["GCE_CLOSE_AT"].replace("Z", "+00:00"))
            if closing_time.tzinfo is None:
                raise RuntimeError("GCE_CLOSE_AT must include a timezone, for example +09:00.")
            self.close_at = closing_time.timestamp()
        if self.key_mode not in {"individual", "shared"} or self.daily_limit < 1:
            raise RuntimeError("Invalid GCE_KEY_MODE or GCE_DAILY_WEB_LIMIT.")
        if self.public and (len(self.password) < 12 or len(self.secret) < 32):
            raise RuntimeError("Public hosting requires GCE_ACCESS_PASSWORD (12+ characters) and GCE_SESSION_SECRET (32+ characters).")
        if self.key_mode == "shared" and not self.password:
            raise RuntimeError("Shared API access requires a login password.")
        if self.password and len(self.secret) < 32:
            raise RuntimeError("Password login requires GCE_SESSION_SECRET (32+ characters).")
        if self.public and not self.serverless and not env.get("GCE_STATE_DIR"):
            raise RuntimeError("Public hosting requires a persistent GCE_STATE_DIR.")
        if self.public and self.key_mode == "shared" and not env.get("GCE_OPENAI_API_KEY"):
            raise RuntimeError("Set GCE_OPENAI_API_KEY securely in the hosting environment.")
        self.database = None
        self._rates = {}
        self._rates_lock = threading.Lock()
        if self.password and not self.serverless:
            state = Path(env.get("GCE_STATE_DIR", "/tmp/gce-study-state"))
            state.mkdir(parents=True, exist_ok=True)
            self.database = state / "access.sqlite3"
            with closing(self.connect()) as db:
                db.executescript("""
                    PRAGMA journal_mode=WAL;
                    CREATE TABLE IF NOT EXISTS sessions (
                        digest TEXT PRIMARY KEY, expires INTEGER NOT NULL, version TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS rate_limits (
                        bucket TEXT NOT NULL, minute INTEGER NOT NULL, count INTEGER NOT NULL,
                        PRIMARY KEY (bucket, minute)
                    );
                    CREATE TABLE IF NOT EXISTS web_usage (
                        day TEXT PRIMARY KEY, attempts INTEGER NOT NULL
                    );
                """)

    def connect(self):
        return sqlite3.connect(self.database, timeout=10, isolation_level=None)

    def digest(self, value):
        return hmac.new(self.secret.encode(), value.encode(), hashlib.sha256).hexdigest()

    def password_matches(self, candidate):
        return hmac.compare_digest(self.password.encode(), candidate.encode())

    def create_session(self):
        if self.serverless:
            expires = int(time.time()) + SESSION_SECONDS
            if self.close_at is not None:
                expires = min(expires, int(self.close_at))
            payload = f"{expires}.{secrets.token_hex(16)}"
            return payload + "." + self.digest("session:" + payload + ":" + self.digest(self.password))
        token = secrets.token_urlsafe(32)
        now = int(time.time())
        with closing(self.connect()) as db:
            db.execute("DELETE FROM sessions WHERE expires < ?", (now,))
            db.execute("INSERT INTO sessions VALUES (?, ?, ?)",
                       (self.digest(token), now + SESSION_SECONDS, self.digest(self.password)))
        return token

    def authenticated(self, token):
        if self.is_closed():
            return False
        if not self.password:
            return True
        if not token or len(token) > 200:
            return False
        if self.serverless:
            try:
                expiry, nonce, signature = token.split(".")
                payload = expiry + "." + nonce
                expected = self.digest("session:" + payload + ":" + self.digest(self.password))
                return int(expiry) > time.time() and hmac.compare_digest(signature, expected)
            except (ValueError, TypeError):
                return False
        with closing(self.connect()) as db:
            row = db.execute("SELECT expires, version FROM sessions WHERE digest = ?",
                             (self.digest(token),)).fetchone()
        return bool(row and row[0] > time.time() and hmac.compare_digest(row[1], self.digest(self.password)))

    def logout(self, token):
        if self.database:
            with closing(self.connect()) as db:
                db.execute("DELETE FROM sessions WHERE digest = ?", (self.digest(token),))

    def allow_rate(self, bucket, limit):
        if self.serverless:
            # Best-effort only: each serverless instance has its own short-lived counters.
            minute = int(time.time()) // 60
            with self._rates_lock:
                self._rates = {key: value for key, value in self._rates.items() if key[1] == minute}
                key = (self.digest(bucket), minute)
                self._rates[key] = self._rates.get(key, 0) + 1
                return self._rates[key] <= limit
        if not self.database:
            return True
        minute = int(time.time()) // 60
        with closing(self.connect()) as db:
            db.execute("DELETE FROM rate_limits WHERE minute < ?", (minute - 2,))
            count = db.execute(
                "INSERT INTO rate_limits VALUES (?, ?, 1) "
                "ON CONFLICT(bucket, minute) DO UPDATE SET count=count+1 RETURNING count",
                (self.digest(bucket), minute),
            ).fetchone()[0]
        return count <= limit

    @staticmethod
    def day():
        return datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat()

    def usage(self):
        if not self.database:
            return None
        with closing(self.connect()) as db:
            row = db.execute("SELECT attempts FROM web_usage WHERE day=?", (self.day(),)).fetchone()
        return {"used": row[0] if row else 0, "limit": self.daily_limit, "timezone": "Asia/Seoul"}

    def is_closed(self):
        return self.close_at is not None and time.time() >= self.close_at

    def reserve_web_request(self):
        if self.serverless:
            return not self.is_closed()
        # Reserve before making a paid call. Failed calls also count, conservatively.
        with closing(self.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT OR IGNORE INTO web_usage VALUES (?, 0)", (self.day(),))
            row = db.execute(
                "UPDATE web_usage SET attempts=attempts+1 WHERE day=? AND attempts < ? RETURNING attempts",
                (self.day(), self.daily_limit),
            ).fetchone()
            db.execute("COMMIT")
        return bool(row)
