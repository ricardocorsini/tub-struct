#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::{path::PathBuf, process::Stdio, time::Duration};
use tokio::{io::AsyncWriteExt, process::Command, sync::Semaphore};

struct EngineState { slots: Semaphore }

fn worker_command() -> Result<Command, String> {
    #[cfg(debug_assertions)]
    {
        let python = std::env::var("TUBSTRUCT_PYTHON").unwrap_or_else(|_| {
            if cfg!(windows) { "python".into() } else { "python3".into() }
        });
        let mut command = Command::new(python);
        let root = PathBuf::from(env!("CARGO_MANIFEST_DIR")).parent().unwrap().to_owned();
        command.arg(root.join("backend/worker.py"));
        Ok(command)
    }
    #[cfg(not(debug_assertions))]
    {
        let name = if cfg!(windows) { "tubstruct-engine.exe" } else { "tubstruct-engine" };
        let path = std::env::current_exe().map_err(|e| e.to_string())?.with_file_name(name);
        if !path.is_file() { return Err("Motor de cálculo não encontrado junto ao aplicativo. Reinstale o TubStruct.".into()); }
        Ok(Command::new(path))
    }
}

#[tauri::command]
async fn engine_request(request: serde_json::Value, state: tauri::State<'_, EngineState>) -> Result<serde_json::Value, String> {
    let body = serde_json::to_vec(&request).map_err(|e| e.to_string())?;
    if body.len() > 2_000_000 { return Err("Arquivo maior que 2 MB.".into()); }
    let _permit = state.slots.acquire().await.map_err(|e| e.to_string())?;
    let mut command = worker_command()?;
    command.stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::piped()).kill_on_drop(true);
    #[cfg(windows)]
    command.creation_flags(0x08000000);
    let mut child = command.spawn().map_err(|e| format!("Não foi possível iniciar o motor: {e}"))?;
    let mut stdin = child.stdin.take().ok_or("Entrada do motor indisponível")?;
    stdin.write_all(&body).await.map_err(|e| e.to_string())?;
    drop(stdin);
    let output = tokio::time::timeout(Duration::from_secs(300), child.wait_with_output()).await
        .map_err(|_| "Tempo limite de 5 minutos. Reduza a varredura.")?
        .map_err(|e| e.to_string())?;
    if !output.status.success() {
        eprintln!("{}", String::from_utf8_lossy(&output.stderr));
        return Err("O motor encerrou sem concluir. Confira a instalação e os dados.".into());
    }
    serde_json::from_slice(&output.stdout).map_err(|e| format!("Resposta inválida do motor: {e}"))
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .manage(EngineState { slots: Semaphore::new(2) })
        .invoke_handler(tauri::generate_handler![engine_request])
        .run(tauri::generate_context!())
        .expect("Não foi possível abrir o TubStruct");
}
