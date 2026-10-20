"""Start a private local app, installing Python dependencies in .venv as needed."""
import argparse
import shutil
import subprocess
import sys
import time
import urllib.request
import venv
import webbrowser
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    environment = root / ".venv"
    python = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    if not python.exists():
        venv.create(environment, with_pip=True)
    subprocess.run([str(python), "-m", "pip", "install", "--disable-pip-version-check",
                    "-r", str(root / "requirements.txt")], check=True)
    if not shutil.which("tesseract"):
        print("Tesseract is missing. Install it for screenshot OCR; text search still works.")
    process = subprocess.Popen(
        [str(python), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
         "--port", str(args.port)], cwd=root,
    )
    try:
        address = f"http://127.0.0.1:{args.port}"
        for _ in range(50):
            if process.poll() is not None:
                raise SystemExit("Server failed to start. Check whether the port is in use.")
            try:
                with urllib.request.urlopen(address + "/api/health", timeout=1) as response:
                    if response.status == 200:
                        if not args.no_browser:
                            webbrowser.open(address)
                        break
            except OSError:
                time.sleep(0.2)
        else:
            raise SystemExit("Server did not become ready.")
        process.wait()
    except KeyboardInterrupt:
        pass
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=10)


if __name__ == "__main__":
    main()
