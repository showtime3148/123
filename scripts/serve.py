"""One process behind Render's HTTPS reverse proxy."""
import os
import sys

port = str(int(os.environ.get("PORT", "10000")))
os.execv(sys.executable, [
    sys.executable, "-m", "uvicorn", "app.main:app",
    "--host", "0.0.0.0", "--port", port,
    "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*",
    "--limit-concurrency", "24", "--timeout-keep-alive", "5",
])
