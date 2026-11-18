"""Start the local API and Vite together. Ctrl+C shuts down both children."""
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

root = Path(__file__).resolve().parent.parent
children = []
try:
    children.append(subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.server:app", "--host", "127.0.0.1", "--port", "8765"], cwd=root))
    children.append(subprocess.Popen(["npm.cmd" if os.name == "nt" else "npm", "run", "dev"], cwd=root))
    while all(p.poll() is None for p in children):
        time.sleep(.3)
except KeyboardInterrupt:
    pass
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
