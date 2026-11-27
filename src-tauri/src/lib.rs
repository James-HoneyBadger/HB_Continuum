use std::collections::HashMap;
use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::mpsc::{self, Sender};
use std::sync::{Arc, Mutex};
use std::time::Duration;

use serde_json::{json, Value};
use tauri::State;

type Pending = Arc<Mutex<HashMap<String, Sender<Value>>>>;

struct Engine {
    child: Child,
    stdin: ChildStdin,
    pending: Pending,
}

struct AppState {
    archive: Mutex<String>,
    engine: Mutex<Option<Engine>>,
}

static COUNTER: AtomicU64 = AtomicU64::new(1);

fn expand_archive(path: &str) -> String {
    if let Some(home) = std::env::var_os("HOME") {
        if path == "~" {
            return home.to_string_lossy().into_owned();
        }
        if let Some(rest) = path.strip_prefix("~/") {
            return PathBuf::from(home).join(rest).to_string_lossy().into_owned();
        }
    }
    path.to_string()
}

fn script_path() -> Result<PathBuf, String> {
    let manifest = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let repo = manifest
        .parent()
        .ok_or_else(|| "no repository root".to_string())?;
    let script = repo.join("dispatch.py");
    if script.is_file() {
        Ok(script)
    } else {
        Err(format!("dispatch.py not found at {}", script.display()))
    }
}

fn spawn_engine(archive: &str) -> Result<Engine, String> {
    let script = script_path()?;
    let mut child = Command::new("python3")
        .arg(&script)
        .arg("--archive")
        .arg(expand_archive(archive))
        .arg("serve")
        .current_dir(script.parent().expect("script has parent"))
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::inherit())
        .spawn()
        .map_err(|e| format!("failed to start engine: {e}"))?;
    let stdin = child.stdin.take().ok_or("engine stdin unavailable")?;
    let stdout = child.stdout.take().ok_or("engine stdout unavailable")?;
    let pending: Pending = Arc::new(Mutex::new(HashMap::new()));
    let pending_reader = pending.clone();
    std::thread::spawn(move || {
        let reader = BufReader::new(stdout);
        for line in reader.lines() {
            match line {
                Ok(line) => {
                    let value: Value = serde_json::from_str(&line).unwrap_or(Value::Null);
                    if let Some(id) = value.get("request_id").and_then(|v| v.as_str()) {
                        if let Some(tx) = pending_reader.lock().expect("pending lock").remove(id) {
                            let _ = tx.send(value);
                        }
                    }
                }
                Err(_) => break,
            }
        }
    });
    Ok(Engine { child, stdin, pending })
}

fn call(state: &AppState, method: &str, params: Value) -> Result<Value, String> {
    let id = COUNTER.fetch_add(1, Ordering::SeqCst).to_string();
    let (tx, rx) = mpsc::channel();
    let mut guard = state.engine.lock().expect("engine lock");
    if guard.is_none() {
        let archive = state.archive.lock().expect("archive lock").clone();
        *guard = Some(spawn_engine(&archive)?);
    }
    let engine = guard.as_mut().expect("engine present");
    engine
        .pending
        .lock()
        .expect("pending lock")
        .insert(id.clone(), tx);
    let line = json!({
        "protocol_version": 1,
        "request_id": id,
        "method": method,
        "params": params,
    })
    .to_string();
    writeln!(engine.stdin, "{line}").map_err(|e| format!("engine write failed: {e}"))?;
    drop(guard);

    let value = rx
        .recv_timeout(Duration::from_secs(15))
        .map_err(|e| format!("engine did not respond: {e}"))?;
    if let Some(error) = value.get("error") {
        let message = error
            .get("message")
            .and_then(|m| m.as_str())
            .unwrap_or("engine error");
        return Err(message.to_string());
    }
    Ok(value.get("result").cloned().unwrap_or(Value::Null))
}

#[tauri::command]
fn ping(state: State<AppState>) -> Result<Value, String> {
    call(&state, "ping", json!({}))
}

#[tauri::command]
fn stats(state: State<AppState>) -> Result<Value, String> {
    call(&state, "stats", json!({}))
}

#[tauri::command]
fn search(
    state: State<AppState>,
    query: String,
    sources: Option<Vec<String>>,
    page: Option<u32>,
    page_size: Option<u32>,
) -> Result<Value, String> {
    call(
        &state,
        "search",
        json!({
            "query": query,
            "sources": sources.unwrap_or_else(|| vec!["email".to_string(), "facebook".to_string()]),
            "page": page.unwrap_or(1),
            "page_size": page_size.unwrap_or(20),
        }),
    )
}

#[tauri::command]
fn set_archive(state: State<AppState>, path: String) -> Result<(), String> {
    let mut guard = state.engine.lock().expect("engine lock");
    if let Some(mut engine) = guard.take() {
        let _ = writeln!(
            engine.stdin,
            "{}",
            json!({"protocol_version": 1, "request_id": "shutdown", "method": "shutdown", "params": {}})
        );
        let _ = engine.child.kill();
    }
    *state.archive.lock().expect("archive lock") = path;
    Ok(())
}

#[tauri::command]
fn shutdown(state: State<AppState>) -> Result<(), String> {
    let mut guard = state.engine.lock().expect("engine lock");
    if let Some(mut engine) = guard.take() {
        let _ = writeln!(
            engine.stdin,
            "{}",
            json!({"protocol_version": 1, "request_id": "shutdown", "method": "shutdown", "params": {}})
        );
        let _ = engine.child.kill();
    }
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let default_archive = std::env::var("HB_ARCHIVE").unwrap_or_else(|_| "~/.hb-dispatch".to_string());
    tauri::Builder::default()
        .manage(AppState {
            archive: Mutex::new(default_archive),
            engine: Mutex::new(None),
        })
        .invoke_handler(tauri::generate_handler![ping, stats, search, set_archive, shutdown])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
