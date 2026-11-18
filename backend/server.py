"""Loopback-only web development server; the desktop uses IPC instead of HTTP."""
import asyncio
import json
import sys
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="TubStruct local", version="0.1.0")
slots = asyncio.Semaphore(2)
WORKER = Path(__file__).with_name("worker.py")


@app.post("/api/request")
async def engine_request(request: Request):
    origin = request.headers.get("origin", "")
    if origin and origin not in ("http://127.0.0.1:1420", "http://localhost:1420", "http://127.0.0.1:4173", "http://localhost:4173"):
        return JSONResponse({"ok": False, "error": "Origem não permitida."}, status_code=403)
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 2_000_000:
            return JSONResponse({"ok": False, "error": "Arquivo maior que 2 MB."}, status_code=413)
    async with slots:
        proc = await asyncio.create_subprocess_exec(sys.executable, str(WORKER), stdin=asyncio.subprocess.PIPE,
                                                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(bytes(body)), timeout=300)
            if proc.returncode:
                sys.stderr.write(stderr.decode("utf-8", errors="replace"))
                raise ValueError("O motor encerrou sem concluir. Confira a instalação do Python e do NumPy.")
            return JSONResponse(json.loads(stdout))
        except (asyncio.TimeoutError, asyncio.CancelledError):
            if proc.returncode is None:
                proc.kill()
            await proc.communicate()
            return JSONResponse({"ok": False, "error": "Tempo limite de 5 minutos. Reduza a varredura."}, status_code=504)
        except (ValueError, json.JSONDecodeError) as exc:
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)
