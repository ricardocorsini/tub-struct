"""Prepare the local Python environment or start the API and Vite."""
import importlib.util
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener

ROOT = Path(__file__).resolve().parent.parent


def setup():
    venv = ROOT / ".venv"
    python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.is_file():
        subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
    subprocess.run(
        [str(python), "-m", "pip", "install", "-r", "backend/requirements.txt"],
        cwd=ROOT,
        check=True,
    )
    print("Motor preparado. Execute npm run dev.")


def wait_for_api(api):
    http = build_opener(ProxyHandler({}))
    deadline = time.monotonic() + 15
    while api.poll() is None and time.monotonic() < deadline:
        try:
            with http.open("http://127.0.0.1:8765/docs", timeout=0.5):
                return
        except (URLError, TimeoutError):
            time.sleep(0.1)
    raise SystemExit(
        "A API local não iniciou na porta 8765. Confira a mensagem acima."
    )


def start():
    missing = [
        name
        for name in ("numpy", "uvicorn", "fastapi")
        if importlib.util.find_spec(name) is None
    ]
    if missing:
        raise SystemExit(
            f"Dependências Python ausentes: {', '.join(missing)}. "
            "Execute npm run setup:engine e tente novamente."
        )
    vite = ROOT / "node_modules" / "vite" / "bin" / "vite.js"
    if not vite.is_file():
        raise SystemExit("Vite indisponível. Execute npm ci e tente novamente.")

    children = []
    try:
        api = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "backend.server:app",
                "--host", "127.0.0.1",
                "--port", "8765",
            ],
            cwd=ROOT,
        )
        children.append(api)
        wait_for_api(api)
        children.append(
            subprocess.Popen(["node", str(vite), *sys.argv[1:]], cwd=ROOT)
        )
        while True:
            for child in children:
                code = child.poll()
                if code is not None:
                    return code if code >= 0 else 128 - code
            time.sleep(0.2)
    except KeyboardInterrupt:
        return 130
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
        for child in children:
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


def stop(_signal, _frame):
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    raise KeyboardInterrupt


if __name__ == "__main__":
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    if sys.argv[1:] == ["--setup"]:
        try:
            setup()
        except KeyboardInterrupt:
            sys.exit(130)
        except subprocess.CalledProcessError:
            raise SystemExit(
                "Falha ao preparar o motor. Confira a mensagem do Python acima."
            ) from None
    else:
        sys.exit(start())
