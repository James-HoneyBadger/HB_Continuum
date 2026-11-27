<script setup lang="ts">
import { onMounted, ref } from "vue";
import { invoke } from "@tauri-apps/api/core";
import OverviewView from "./components/OverviewView.vue";
import SearchView from "./components/SearchView.vue";
import ImportView from "./components/ImportView.vue";
import ResearchView from "./components/ResearchView.vue";
import SyncView from "./components/SyncView.vue";
import PreferencesView from "./components/PreferencesView.vue";
import HealthView from "./components/HealthView.vue";
import BackupView from "./components/BackupView.vue";
import TimelineView from "./components/TimelineView.vue";

interface Stats {
  archive: { messages: number; origins: number };
  catalog: { files: number; records: number };
}

const tabs = [
  "Overview",
  "Search",
  "Timeline",
  "Import",
  "Research",
  "Sync",
  "Health",
  "Backup",
  "Preferences",
] as const;
const tab = ref<(typeof tabs)[number]>("Overview");

const archive = ref("~/.hb-dispatch");
const stats = ref<Stats | null>(null);
const error = ref("");
const verifyResult = ref<{ checked: number; bad: string[] } | null>(null);

async function refreshStats() {
  try {
    stats.value = (await invoke("stats")) as Stats;
  } catch (e) {
    error.value = String(e);
  }
}

async function applyArchive() {
  error.value = "";
  verifyResult.value = null;
  try {
    await invoke("set_archive", { path: archive.value });
    await refreshStats();
  } catch (e) {
    error.value = String(e);
  }
}

async function runVerify() {
  error.value = "";
  verifyResult.value = null;
  try {
    verifyResult.value = (await invoke("verify")) as { checked: number; bad: string[] };
  } catch (e) {
    error.value = String(e);
  }
}

function reportError(message: string) {
  error.value = message;
}

onMounted(refreshStats);
</script>

<template>
  <div class="shell">
    <header class="app-header">
      <div class="brand">
        <h1>HB Continuum</h1>
        <span class="tagline">Personal historical research workstation</span>
      </div>
      <div class="archive-bar">
        <label class="grow">
          Archive
          <input v-model="archive" placeholder="~/.hb-dispatch" spellcheck="false" />
        </label>
        <button @click="applyArchive">Open</button>
        <button @click="runVerify">Verify integrity</button>
      </div>
    </header>

    <div class="body">
      <nav class="nav" aria-label="Workspaces">
        <button
          v-for="name in tabs"
          :key="name"
          type="button"
          :class="['nav-item', { active: tab === name }]"
          :aria-current="tab === name ? 'page' : undefined"
          @click="tab = name"
        >
          {{ name }}
        </button>
      </nav>

      <main class="workspace" :aria-label="tab">
        <p v-if="error" class="error" role="alert">{{ error }}</p>
        <OverviewView v-if="tab === 'Overview'" :on-error="reportError" :on-changed="refreshStats" />
        <SearchView v-else-if="tab === 'Search'" :on-error="reportError" :on-changed="refreshStats" />
        <TimelineView v-else-if="tab === 'Timeline'" :on-error="reportError" :on-changed="refreshStats" />
        <ImportView v-else-if="tab === 'Import'" :on-error="reportError" :on-changed="refreshStats" />
        <ResearchView v-else-if="tab === 'Research'" :on-error="reportError" :on-changed="refreshStats" />
        <SyncView v-else-if="tab === 'Sync'" :on-error="reportError" :on-changed="refreshStats" />
        <HealthView v-else-if="tab === 'Health'" :on-error="reportError" :on-changed="refreshStats" />
        <BackupView v-else-if="tab === 'Backup'" :on-error="reportError" :on-changed="refreshStats" />
        <PreferencesView v-else :on-error="reportError" :on-changed="refreshStats" />
      </main>
    </div>

    <footer class="statusbar">
      <span v-if="stats">
        {{ stats.archive.messages.toLocaleString() }} messages ·
        {{ stats.archive.origins.toLocaleString() }} mailbox origins ·
        {{ stats.catalog.records.toLocaleString() }} catalog records
      </span>
      <span v-else>No archive statistics yet.</span>
      <span v-if="verifyResult" :class="verifyResult.bad.length ? 'status-error' : 'status-ok'">
        {{ verifyResult.checked }} checked · {{ verifyResult.bad.length }} failed
      </span>
    </footer>
  </div>
</template>

<style scoped>
.shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--hb-app-bg);
}
.app-header {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px;
  background: var(--hb-header);
  color: var(--hb-header-text);
  border-bottom: 1px solid var(--hb-border-strong);
}
.brand {
  display: flex;
  flex-direction: column;
}
h1 {
  font-size: 17px;
  font-weight: 600;
  margin: 0;
  letter-spacing: 0.01em;
}
.tagline {
  font-size: 11px;
  opacity: 0.85;
}
.archive-bar {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  min-width: 360px;
  flex: 1;
  max-width: 620px;
}
.grow {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 11px;
}
input {
  padding: 5px 7px;
  border: 1px solid var(--hb-border-strong);
  border-radius: var(--hb-radius);
  background: var(--hb-workspace);
  color: var(--hb-text);
  width: 100%;
}
button {
  padding: 5px 12px;
  border: 1px solid var(--hb-border-strong);
  border-radius: var(--hb-radius);
  background: var(--hb-toolbar);
  color: var(--hb-text);
  cursor: pointer;
}
button:hover:not(:disabled) {
  background: var(--hb-panel);
}
button:disabled {
  cursor: default;
  opacity: 0.6;
}
.body {
  flex: 1;
  display: flex;
  min-height: 0;
}
.nav {
  width: 168px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
  padding: 8px;
  background: var(--hb-panel);
  border-right: 1px solid var(--hb-border);
  overflow-y: auto;
}
.nav-item {
  border: 1px solid transparent;
  background: transparent;
  text-align: left;
  padding: 6px 9px;
  border-radius: var(--hb-radius);
}
.nav-item:hover {
  background: var(--hb-panel-alt);
}
.nav-item.active {
  background: var(--hb-workspace);
  border-color: var(--hb-border);
  color: var(--hb-info-text);
  font-weight: 600;
}
.workspace {
  flex: 1;
  min-width: 0;
  overflow: auto;
  padding: 16px 20px;
  background: var(--hb-workspace);
}
.error {
  color: var(--hb-error-text);
  background: var(--hb-panel);
  border: 1px solid var(--hb-error);
  border-radius: var(--hb-radius);
  padding: 6px 10px;
  margin: 0 0 12px;
}
.statusbar {
  display: flex;
  gap: 18px;
  justify-content: space-between;
  padding: 4px 12px;
  font-size: 11px;
  color: var(--hb-text-secondary);
  background: var(--hb-toolbar);
  border-top: 1px solid var(--hb-border);
}
.status-ok {
  color: var(--hb-success-text);
}
.status-error {
  color: var(--hb-error-text);
}
@media (max-width: 720px) {
  .body {
    flex-direction: column;
  }
  .nav {
    width: auto;
    flex-direction: row;
    flex-wrap: wrap;
    border-right: none;
    border-bottom: 1px solid var(--hb-border);
  }
  .archive-bar {
    min-width: 0;
  }
}
</style>
