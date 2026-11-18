export const desktop = () => "__TAURI_INTERNALS__" in window;
export async function request<T>(data: Record<string, unknown>): Promise<T> {
  let response: { ok: boolean; data: T; error?: string };
  if (desktop()) {
    const { invoke } = await import("@tauri-apps/api/core");
    response = await invoke("engine_request", { request: data });
  } else {
    try {
      const r = await fetch("/api/request", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
        signal: AbortSignal.timeout(310_000),
      });
      response = await r.json();
    } catch {
      throw new Error(
        "O motor local não respondeu. Execute npm run dev na pasta do TubStruct e abra o endereço mostrado no terminal.",
      );
    }
  }
  if (!response.ok)
    throw new Error(response.error || "O cálculo não foi concluído.");
  return response.data;
}
export async function saveText(
  filename: string,
  text: string,
  mime = "application/json",
): Promise<boolean> {
  if (desktop()) {
    const { save } = await import("@tauri-apps/plugin-dialog");
    const { writeTextFile } = await import("@tauri-apps/plugin-fs");
    const path = await save({ defaultPath: filename });
    if (!path) return false;
    await writeTextFile(path, text);
    return true;
  }
  const url = URL.createObjectURL(new Blob([text], { type: mime }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  return true;
}
export const safeName = (name: string) =>
  name
    .normalize("NFKD")
    .replace(/[^a-zA-Z0-9_-]/g, "_")
    .slice(0, 80) || "TubStruct";
export const csvCell = (v: unknown): string =>
  `"${String(v ?? "")
    .replace(/^[=+@-]/, "'$&")
    .replace(/"/g, '""')}"`;
