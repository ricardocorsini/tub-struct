"""Verify the bundled worker, including HTML/3D resources, without Python subprocess fallback."""
import json
import os
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parent.parent
suffix = ".exe" if os.name == "nt" else ""
binary = root / "build" / "engine" / f"tubstruct-engine{suffix}"


def call(request):
    result = subprocess.run([str(binary)], input=json.dumps(request), text=True, encoding="utf-8", capture_output=True, timeout=60)
    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response["ok"], response
    return response["data"]


parameters = call({"action": "example", "name": "poste"})
result = call({"action": "calculate", "parameters": parameters})
assert result["result"]["ok"]
assert len(result["result"]["verificacoes"]) == 46
assert "TubStruct" in result["report"]
html = call({"action": "export3d", "parameters": parameters})
assert 'id="three-src"' in html, "Missing offline Three.js bundle"
assert "/*__DADOS__*/null" not in html
print("Frozen engine: health, example, calculation, report and offline 3D passed.")
