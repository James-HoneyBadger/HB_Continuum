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
fn message(state: State<AppState>, hash: String) -> Result<Value, String> {
    call(&state, "message", json!({ "hash": hash }))
}

#[tauri::command]
fn thread(state: State<AppState>, hash: String) -> Result<Value, String> {
    call(&state, "thread", json!({ "hash": hash }))
}

#[tauri::command]
fn record(state: State<AppState>, record_id: String) -> Result<Value, String> {
    call(&state, "record", json!({ "record_id": record_id }))
}

#[tauri::command]
fn verify(state: State<AppState>) -> Result<Value, String> {
    call(&state, "verify", json!({}))
}

#[tauri::command]
fn import_eml(state: State<AppState>, paths: Vec<String>) -> Result<Value, String> {
    call(&state, "import_eml", json!({ "paths": paths }))
}

#[tauri::command]
fn preferences(state: State<AppState>) -> Result<Value, String> {
    call(&state, "preferences", json!({}))
}

#[tauri::command]
fn preferences_set(state: State<AppState>, values: Value) -> Result<Value, String> {
    call(&state, "preferences_set", json!({ "values": values }))
}

#[tauri::command]
fn research_list(state: State<AppState>, table: String) -> Result<Value, String> {
    call(&state, "research_list", json!({ "table": table }))
}

#[tauri::command]
fn research_results(state: State<AppState>, workspace: String, name: String) -> Result<Value, String> {
    call(&state, "research_results", json!({ "workspace": workspace, "name": name }))
}

#[tauri::command]
fn research_workspace_save(
    state: State<AppState>,
    workspace: String,
    description: Option<String>,
) -> Result<Value, String> {
    call(&state, "research_workspace_save",
         json!({ "workspace": workspace, "description": description.unwrap_or_default() }))
}

#[tauri::command]
fn research_search_save(
    state: State<AppState>,
    workspace: String,
    name: String,
    query: String,
    tag: String,
    limit: u32,
) -> Result<Value, String> {
    call(&state, "research_search_save",
         json!({ "workspace": workspace, "name": name, "query": query, "tag": tag, "limit": limit }))
}

#[tauri::command]
fn research_tag(state: State<AppState>, hashes: Vec<String>, tag: String) -> Result<Value, String> {
    call(&state, "research_tag", json!({ "hashes": hashes, "tag": tag }))
}

#[tauri::command]
fn research_untag(state: State<AppState>, hashes: Vec<String>, tag: String) -> Result<Value, String> {
    call(&state, "research_untag", json!({ "hashes": hashes, "tag": tag }))
}

#[tauri::command]
fn research_apply_rules(state: State<AppState>) -> Result<Value, String> {
    call(&state, "research_apply_rules", json!({}))
}

#[tauri::command]
fn research_field_define(
    state: State<AppState>,
    name: String,
    kind: String,
    choices: Option<Vec<String>>,
) -> Result<Value, String> {
    call(&state, "research_field_define",
         json!({ "name": name, "kind": kind, "choices": choices.unwrap_or_default() }))
}

#[tauri::command]
fn research_metadata_set(
    state: State<AppState>,
    hash: String,
    field: String,
    value: String,
) -> Result<Value, String> {
    call(&state, "research_metadata_set", json!({ "hash": hash, "field": field, "value": value }))
}

#[tauri::command]
fn research_report_save(
    state: State<AppState>,
    name: String,
    workspace: String,
    search: String,
    columns: Vec<String>,
    group_by: Option<String>,
) -> Result<Value, String> {
    call(&state, "research_report_save", json!({
        "name": name, "workspace": workspace, "search": search,
        "columns": columns, "group_by": group_by.unwrap_or_default(),
    }))
}

#[tauri::command]
fn research_report_preview(state: State<AppState>, name: String) -> Result<Value, String> {
    call(&state, "research_report_preview", json!({ "name": name }))
}

#[tauri::command]
fn research_report_export(state: State<AppState>, name: String, path: String) -> Result<Value, String> {
    call(&state, "research_report_export", json!({ "name": name, "path": path }))
}

#[tauri::command]
fn export_evidence(state: State<AppState>, hashes: Vec<String>, destination: String) -> Result<Value, String> {
    call(&state, "export_evidence", json!({ "hashes": hashes, "destination": destination }))
}

#[tauri::command]
fn schedule_status(state: State<AppState>) -> Result<Value, String> {
    call(&state, "schedule_status", json!({}))
}

#[tauri::command]
fn schedule_profile_save(
    state: State<AppState>,
    name: String,
    host: String,
    user: String,
    folders: Vec<String>,
    minutes: Option<u32>,
    daily: Option<String>,
    enabled: bool,
) -> Result<Value, String> {
    call(&state, "schedule_profile_save", json!({
        "name": name, "host": host, "user": user, "folders": folders,
        "minutes": minutes, "daily": daily, "enabled": enabled,
    }))
}

#[tauri::command]
fn schedule_profile_enabled(state: State<AppState>, name: String, enabled: bool) -> Result<Value, String> {
    call(&state, "schedule_profile_enabled", json!({ "name": name, "enabled": enabled }))
}

#[tauri::command]
fn schedule_run(state: State<AppState>, name: Option<String>) -> Result<Value, String> {
    call(&state, "schedule_run", json!({ "name": name }))
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
        .plugin(tauri_plugin_dialog::init())
        .manage(AppState {
            archive: Mutex::new(default_archive),
            engine: Mutex::new(None),
        })
        .invoke_handler(tauri::generate_handler![
            ping, stats, search, message, thread, record, verify,
            import_eml, preferences, preferences_set, research_list, research_results,
            research_workspace_save, research_search_save, research_tag, research_untag,
            research_apply_rules, research_field_define, research_metadata_set,
            research_report_save, research_report_preview, research_report_export,
            export_evidence, schedule_status, schedule_profile_save,
            schedule_profile_enabled, schedule_run,
            set_archive, shutdown
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
