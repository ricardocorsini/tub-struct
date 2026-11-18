import { spawn, spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../", import.meta.url));
const windows = process.platform === "win32";
const local = join(
  root,
  ".venv",
  windows ? "Scripts/python.exe" : "bin/python",
);
const override = process.env.TUBSTRUCT_PYTHON;
const configured = existsSync(local) ? local : override;
const candidates = configured
  ? [[configured]]
  : windows
    ? [["python"], ["py", "-3.13"], ["py", "-3.12"], ["py", "-3"], ["python3"]]
    : [["python3"], ["python"]];
const selected = candidates.find(
  ([command, ...prefix]) =>
    spawnSync(
      command,
      [
        ...prefix,
        "-c",
        "import sys; sys.exit(0 if sys.version_info[:2] >= (3, 11) else 1)",
      ],
      { cwd: root, stdio: "ignore", windowsHide: true, timeout: 5000 },
    ).status === 0,
);

if (!selected) {
  if (configured)
    console.error(`Interpretador indisponível ou incompatível: ${configured}`);
  console.error(
    "Instale o Python 3.12 ou 3.13 para rodar o motor do TubStruct, ou informe o executável em TUBSTRUCT_PYTHON.",
  );
  process.exit(1);
}

const [command, ...prefix] = selected;
const python = spawn(command, [...prefix, ...process.argv.slice(2)], {
  cwd: root,
  stdio: "inherit",
  windowsHide: true,
});
// On Windows Ctrl+C reaches Python through the shared console.
process.once("SIGINT", () => {
  if (!windows) python.kill("SIGINT");
});
process.once("SIGTERM", () => python.kill("SIGTERM"));
python.on("error", (error) => {
  console.error(`Não foi possível iniciar o Python: ${error.message}`);
  process.exitCode = 1;
});
python.on("exit", (code, signal) => {
  process.exitCode = code ?? (signal === "SIGINT" ? 130 : 1);
});
