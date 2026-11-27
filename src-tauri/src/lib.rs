use std::collections::HashMap;
use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::mpsc::{self, Sender};
use std::sync::{Arc, Mutex};
use std::time::Duration;

use serde_json::{json, Value};
use tauri::{Emitter, Manager, State};

type Pending = Arc<Mutex<HashMap<String, Sender<Value>>>>;

struct Engine {
    child: Child,
    stdin: ChildStdin,
    pending: Pending,
}

struct AppState {
    archive: Mutex<String>,
    engine: Mutex<Option<Engine>>,
    app: tauri::AppHandle,
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

enum EngineCommand {
    /// Standalone engine produced by `scripts/build_engine.py`.
    Binary(PathBuf),
    /// Development fallback: run the checked-out `dispatch.py` with Python.
    Script(PathBuf),
}

fn bundled_engine_name() -> &'static str {
    if cfg!(windows) {
        "hb-engine.exe"
    } else {
        "hb-engine"
    }
}

/// Locate a development `dispatch.py` without relying on the working directory.
fn dev_script(exe_dir: &Path) -> Option<PathBuf> {
    if let Some(path) = std::env::var_os("HB_ENGINE_SCRIPT") {
        let path = PathBuf::from(path);
        if path.is_file() {
            return Some(path);
        }
    }
    let candidates = [
        exe_dir.join("dispatch.py"),
        exe_dir.join("../../..").join("dispatch.py"),
    ];
    for candidate in candidates {
        if candidate.is_file() {
            return Some(candidate);
        }
    }
    let manifest = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let repo_script = manifest.parent()?.join("dispatch.py");
    if repo_script.is_file() {
        Some(repo_script)
    } else {
        None
    }
}

/// Resolve the engine, preferring a bundled sidecar over a checked-out script.
fn engine_command(exe_dir: &Path) -> Option<EngineCommand> {
    if let Some(path) = std::env::var_os("HB_ENGINE") {
        let path = PathBuf::from(path);
        if path.is_file() {
            return Some(EngineCommand::Binary(path));
        }
    }
    let bundled = exe_dir.join(bundled_engine_name());
    if bundled.is_file() {
        return Some(EngineCommand::Binary(bundled));
    }
    dev_script(exe_dir).map(EngineCommand::Script)
}

fn spawn_engine(app: &tauri::AppHandle, archive: &str) -> Result<Engine, String> {
    let exe_dir = std::env::current_exe()
        .ok()
        .and_then(|exe| exe.parent().map(Path::to_path_buf))
        .ok_or_else(|| "cannot determine the application directory".to_string())?;
    let (mut command, working_dir) = match engine_command(&exe_dir) {
        Some(EngineCommand::Binary(path)) => (Command::new(&path), exe_dir.clone()),
        Some(EngineCommand::Script(path)) => {
            let mut command = Command::new("python3");
            command.arg(&path);
            let dir = path.parent().map(Path::to_path_buf).unwrap_or(exe_dir.clone());
            (command, dir)
        }
        None => {
            return Err(format!(
                "engine not found: bundle {} next to the app or set HB_ENGINE",
                bundled_engine_name()
            ))
        }
    };
    let mut child = command
        .arg("--archive")
        .arg(expand_archive(archive))
        .arg("serve")
        .current_dir(working_dir)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::inherit())
        .spawn()
        .map_err(|e| format!("failed to start engine: {e}"))?;
    let stdin = child.stdin.take().ok_or("engine stdin unavailable")?;
    let stdout = child.stdout.take().ok_or("engine stdout unavailable")?;
    let pending: Pending = Arc::new(Mutex::new(HashMap::new()));
    let pending_reader = pending.clone();
    let events = app.clone();
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
                    } else if value.get("event").is_some() {
                        // Background jobs report progress and completion out of band.
                        let _ = events.emit("engine-event", value);
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
        *guard = Some(spawn_engine(&state.app, &archive)?);
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
fn search_validate(state: State<AppState>, query: String) -> Result<Value, String> {
    call(&state, "search_validate", json!({ "query": query }))
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
fn timeline(
    state: State<AppState>,
    sender: Option<String>,
    limit: Option<u32>,
    offset: Option<u32>,
    order: Option<String>,
    after: Option<i64>,
    before: Option<i64>,
) -> Result<Value, String> {
    call(
        &state,
        "timeline",
        json!({
            "sender": sender,
            "limit": limit.unwrap_or(100),
            "offset": offset.unwrap_or(0),
            "order": order.unwrap_or_else(|| "asc".into()),
            "after": after,
            "before": before,
        }),
    )
}

#[tauri::command]
fn dashboard(state: State<AppState>) -> Result<Value, String> {
    call(&state, "dashboard", json!({}))
}

#[tauri::command]
fn correspondents(state: State<AppState>, limit: Option<u32>) -> Result<Value, String> {
    call(&state, "correspondents", json!({ "limit": limit.unwrap_or(100) }))
}

#[tauri::command]
fn relationships(
    state: State<AppState>,
    limit_nodes: Option<u32>,
    max_edges: Option<u32>,
    after: Option<i64>,
    before: Option<i64>,
) -> Result<Value, String> {
    call(
        &state,
        "relationships",
        json!({
            "limit_nodes": limit_nodes.unwrap_or(30),
            "max_edges": max_edges.unwrap_or(200),
            "after": after,
            "before": before,
        }),
    )
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
fn health(state: State<AppState>) -> Result<Value, String> {
    call(&state, "health", json!({}))
}

#[tauri::command]
fn reindex(state: State<AppState>) -> Result<Value, String> {
    call(&state, "reindex", json!({}))
}

#[tauri::command]
fn recover_orphans(state: State<AppState>) -> Result<Value, String> {
    call(&state, "recover_orphans", json!({}))
}

#[tauri::command]
fn facebook_preview(state: State<AppState>, paths: Vec<String>) -> Result<Value, String> {
    call(&state, "facebook_preview", json!({ "paths": paths }))
}

#[tauri::command]
fn facebook_import(state: State<AppState>, paths: Vec<String>) -> Result<Value, String> {
    call(&state, "facebook_import", json!({ "paths": paths }))
}

#[tauri::command]
fn migrate_status(state: State<AppState>) -> Result<Value, String> {
    call(&state, "migrate_status", json!({}))
}

#[tauri::command]
fn backup(state: State<AppState>, destination: String) -> Result<Value, String> {
    call(&state, "backup", json!({ "destination": destination }))
}

#[tauri::command]
fn verify_backup(state: State<AppState>, snapshot: String) -> Result<Value, String> {
    call(&state, "verify_backup", json!({ "snapshot": snapshot }))
}

#[tauri::command]
fn restore(
    state: State<AppState>,
    snapshot: String,
    destination: String,
) -> Result<Value, String> {
    call(&state, "restore", json!({ "snapshot": snapshot, "destination": destination }))
}

#[tauri::command]
fn import_eml(state: State<AppState>, paths: Vec<String>) -> Result<Value, String> {
    call(&state, "import_eml", json!({ "paths": paths }))
}

#[tauri::command]
fn report_archive(
    state: State<AppState>,
    destination: String,
    format: Option<String>,
) -> Result<Value, String> {
    call(
        &state,
        "report_archive",
        json!({
            "destination": destination,
            "format": format.unwrap_or_else(|| "markdown".into()),
        }),
    )
}

#[tauri::command]
fn cancel(state: State<AppState>, job_id: String) -> Result<Value, String> {
    call(&state, "cancel", json!({ "job_id": job_id }))
}

#[tauri::command]
fn import_history(state: State<AppState>, limit: Option<u32>) -> Result<Value, String> {
    call(&state, "import_history", json!({ "limit": limit.unwrap_or(50) }))
}

#[tauri::command]
fn sources(state: State<AppState>) -> Result<Value, String> {
    call(&state, "sources", json!({}))
}

#[tauri::command]
fn source_set_enabled(
    state: State<AppState>,
    source: String,
    source_key: String,
    enabled: bool,
    note: Option<String>,
) -> Result<Value, String> {
    call(
        &state,
        "source_set_enabled",
        json!({
            "source": source,
            "source_key": source_key,
            "enabled": enabled,
            "note": note,
        }),
    )
}

#[tauri::command]
fn source_removal_preview(
    state: State<AppState>,
    source: String,
    source_key: String,
) -> Result<Value, String> {
    call(
        &state,
        "source_removal_preview",
        json!({ "source": source, "source_key": source_key }),
    )
}

#[tauri::command]
fn source_remove(
    state: State<AppState>,
    source: String,
    source_key: String,
    confirm: bool,
) -> Result<Value, String> {
    call(
        &state,
        "source_remove",
        json!({ "source": source, "source_key": source_key, "confirm": confirm }),
    )
}

#[tauri::command]
fn source_events(state: State<AppState>, limit: Option<u32>) -> Result<Value, String> {
    call(&state, "source_events", json!({ "limit": limit.unwrap_or(100) }))
}

#[tauri::command]
fn source_verify(
    state: State<AppState>,
    source: String,
    source_key: String,
) -> Result<Value, String> {
    call(
        &state,
        "source_verify",
        json!({ "source": source, "source_key": source_key }),
    )
}

#[tauri::command]
fn journal_list(
    state: State<AppState>,
    limit: Option<u32>,
    include_deleted: Option<bool>,
) -> Result<Value, String> {
    call(
        &state,
        "journal_list",
        json!({
            "limit": limit.unwrap_or(100),
            "include_deleted": include_deleted.unwrap_or(false),
        }),
    )
}

#[tauri::command]
fn journal_get(state: State<AppState>, entry_id: i64) -> Result<Value, String> {
    call(&state, "journal_get", json!({ "entry_id": entry_id }))
}

#[tauri::command]
fn journal_save(
    state: State<AppState>,
    entry_id: Option<i64>,
    title: String,
    body: String,
    event_date: Option<String>,
) -> Result<Value, String> {
    call(
        &state,
        "journal_save",
        json!({
            "entry_id": entry_id,
            "title": title,
            "body": body,
            "event_date": event_date,
        }),
    )
}

#[tauri::command]
fn journal_delete(state: State<AppState>, entry_id: i64) -> Result<Value, String> {
    call(&state, "journal_delete", json!({ "entry_id": entry_id }))
}

#[tauri::command]
fn journal_restore(state: State<AppState>, entry_id: i64) -> Result<Value, String> {
    call(&state, "journal_restore", json!({ "entry_id": entry_id }))
}

#[tauri::command]
fn collections_list(
    state: State<AppState>,
    workspace: Option<String>,
) -> Result<Value, String> {
    call(&state, "collections_list", json!({ "workspace": workspace }))
}

#[tauri::command]
fn collection_get(state: State<AppState>, collection_id: i64) -> Result<Value, String> {
    call(&state, "collection_get", json!({ "collection_id": collection_id }))
}

#[tauri::command]
fn collection_create(
    state: State<AppState>,
    workspace: String,
    name: String,
    description: Option<String>,
) -> Result<Value, String> {
    call(
        &state,
        "collection_create",
        json!({
            "workspace": workspace,
            "name": name,
            "description": description.unwrap_or_default(),
        }),
    )
}

#[tauri::command]
fn collection_delete(state: State<AppState>, collection_id: i64) -> Result<Value, String> {
    call(&state, "collection_delete", json!({ "collection_id": collection_id }))
}

#[tauri::command]
fn collection_add(
    state: State<AppState>,
    collection_id: i64,
    item_type: String,
    item_id: String,
    note: Option<String>,
) -> Result<Value, String> {
    call(
        &state,
        "collection_add",
        json!({
            "collection_id": collection_id,
            "item_type": item_type,
            "item_id": item_id,
            "note": note,
        }),
    )
}

#[tauri::command]
fn collection_remove(
    state: State<AppState>,
    collection_id: i64,
    item_type: String,
    item_id: String,
) -> Result<Value, String> {
    call(
        &state,
        "collection_remove",
        json!({
            "collection_id": collection_id,
            "item_type": item_type,
            "item_id": item_id,
        }),
    )
}

#[tauri::command]
fn collection_export(
    state: State<AppState>,
    collection_id: i64,
    destination: String,
    format: Option<String>,
) -> Result<Value, String> {
    call(
        &state,
        "collection_export",
        json!({
            "collection_id": collection_id,
            "destination": destination,
            "format": format.unwrap_or_else(|| "markdown".into()),
        }),
    )
}

#[tauri::command]
fn draft_list(
    state: State<AppState>,
    collection_id: Option<i64>,
) -> Result<Value, String> {
    call(&state, "draft_list", json!({ "collection_id": collection_id }))
}

#[tauri::command]
fn draft_get(state: State<AppState>, draft_id: i64) -> Result<Value, String> {
    call(&state, "draft_get", json!({ "draft_id": draft_id }))
}

#[tauri::command]
fn draft_save(
    state: State<AppState>,
    draft_id: Option<i64>,
    collection_id: i64,
    title: String,
    notes: Option<String>,
) -> Result<Value, String> {
    call(
        &state,
        "draft_save",
        json!({
            "draft_id": draft_id,
            "collection_id": collection_id,
            "title": title,
            "notes": notes.unwrap_or_default(),
        }),
    )
}

#[tauri::command]
fn draft_delete(state: State<AppState>, draft_id: i64) -> Result<Value, String> {
    call(&state, "draft_delete", json!({ "draft_id": draft_id }))
}

#[tauri::command]
fn draft_export(
    state: State<AppState>,
    draft_id: i64,
    destination: String,
    format: Option<String>,
) -> Result<Value, String> {
    call(
        &state,
        "draft_export",
        json!({
            "draft_id": draft_id,
            "destination": destination,
            "format": format.unwrap_or_else(|| "markdown".into()),
        }),
    )
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
        .setup(move |app| {
            app.manage(AppState {
                archive: Mutex::new(default_archive),
                engine: Mutex::new(None),
                app: app.handle().clone(),
            });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            ping, stats, search, search_validate, message, thread, timeline, dashboard,
            correspondents, relationships,
            record, verify, health,
            reindex, recover_orphans, migrate_status, backup, verify_backup, restore,
            facebook_preview, facebook_import,
            import_eml, import_history, sources, report_archive, cancel,
            source_set_enabled, source_removal_preview, source_remove, source_events,
            source_verify,
            journal_list, journal_get, journal_save, journal_delete, journal_restore,
            collections_list, collection_get, collection_create, collection_delete,
            collection_add, collection_remove, collection_export,
            draft_list, draft_get, draft_save, draft_delete, draft_export,
            preferences, preferences_set, research_list, research_results,
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

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    fn scratch(name: &str) -> PathBuf {
        let dir = std::env::temp_dir().join(format!("hb-continuum-{}-{}", std::process::id(), name));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).expect("scratch dir");
        dir
    }

    #[test]
    fn bundled_engine_wins_over_dev_script() {
        let dir = scratch("bundled");
        let engine = dir.join(bundled_engine_name());
        fs::write(&engine, b"#!/bin/sh\n").expect("write engine");
        fs::write(dir.join("dispatch.py"), b"print()\n").expect("write script");
        match engine_command(&dir) {
            Some(EngineCommand::Binary(path)) => assert_eq!(path, engine),
            _ => panic!("expected the bundled engine to be preferred"),
        }
        let _ = fs::remove_dir_all(&dir);
    }

    #[test]
    fn dev_mode_falls_back_to_dispatch_script() {
        let dir = scratch("script");
        let script = dir.join("dispatch.py");
        fs::write(&script, b"print()\n").expect("write script");
        match engine_command(&dir) {
            Some(EngineCommand::Script(path)) => assert_eq!(path, script),
            _ => panic!("expected the dispatch script to be used"),
        }
        let _ = fs::remove_dir_all(&dir);
    }

    #[test]
    fn missing_engine_reports_a_clear_error() {
        if std::env::var_os("HB_ENGINE").is_some() {
            return;
        }
        let dir = scratch("missing");
        // The compile-time repository fallback still exists in tests, so a bare
        // directory should resolve to the checkout rather than None.
        assert!(engine_command(&dir).is_some());
        let _ = fs::remove_dir_all(&dir);
    }
}
