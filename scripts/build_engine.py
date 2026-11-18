"""Build the local calculation sidecar. Python/NumPy are bundled, not required at runtime."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    target = os.environ.get("TAURI_ENV_TARGET_TRIPLE")
    if not target:
        try:
            details = subprocess.check_output(["rustc", "-vV"], text=True)
            target = next(line.split(": ", 1)[1] for line in details.splitlines() if line.startswith("host:"))
        except (OSError, StopIteration):
            raise SystemExit("Instale Rust e os pré-requisitos Tauri antes de preparar o desktop.")
    out = ROOT / "build" / "engine"
    legacy = ROOT / "backend" / "legacy"
    sep = os.pathsep
    subprocess.run([
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--console",
        "--name", "tubstruct-engine", "--distpath", str(out), "--workpath", str(ROOT / "build" / "pyinstaller"),
        "--specpath", str(ROOT / "build"), "--paths", str(legacy), "--paths", str(ROOT / "backend"),
        "--hidden-import", "tubulao_core", "--hidden-import", "tubulao_sondagem",
        "--hidden-import", "tubulao_solo", "--hidden-import", "tubulao_concreto",
        "--hidden-import", "tubulao_memoria", "--hidden-import", "tubulao_3d", "--hidden-import", "dependencias",
        "--add-data", f"{legacy / 'tubulao_3d.html'}{sep}legacy",
        "--add-data", f"{legacy / 'vendor'}{sep}legacy/vendor",
        "--add-data", f"{legacy / 'exemplos'}{sep}legacy/exemplos",
        str(ROOT / "backend" / "worker.py"),
    ], check=True, cwd=ROOT)
    suffix = ".exe" if os.name == "nt" else ""
    dest = ROOT / "src-tauri" / "binaries" / f"tubstruct-engine-{target}{suffix}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(out / f"tubstruct-engine{suffix}", dest)
    smoke = subprocess.run([str(dest)], input='{"action":"health"}', text=True, capture_output=True, timeout=30)
    if smoke.returncode:
        raise SystemExit(smoke.stderr or smoke.stdout)
    import json
    response = json.loads(smoke.stdout)
    if not response.get("ok"):
        raise SystemExit(smoke.stdout)
    print(f"Motor preparado: {dest.name} ({response['data']['version']})")


if __name__ == "__main__":
    main()
