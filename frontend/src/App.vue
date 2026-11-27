<script setup lang="ts">
import { onMounted, ref } from "vue";
import { invoke } from "@tauri-apps/api/core";
import SearchView from "./components/SearchView.vue";
import ImportView from "./components/ImportView.vue";
import ResearchView from "./components/ResearchView.vue";
import SyncView from "./components/SyncView.vue";
import PreferencesView from "./components/PreferencesView.vue";
import HealthView from "./components/HealthView.vue";
import BackupView from "./components/BackupView.vue";

interface Stats {
  archive: { messages: number; origins: number };
  catalog: { files: number; records: number };
}

const tabs = ["Search", "Import", "Research", "Sync", "Preferences", "Health", "Backup"] as const;
const tab = ref<(typeof tabs)[number]>("Search");

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
  <main class="app">
    <header>
      <h1>HB Continuum</h1>
      <section class="row">
        <label class="grow">
          Archive
          <input v-model="archive" placeholder="~/.hb-dispatch" />
        </label>
        <button @click="applyArchive">Open</button>
        <button @click="runVerify">Verify integrity</button>
      </section>
      <p v-if="stats" class="stats">
        {{ stats.archive.messages }} messages · {{ stats.archive.origins }} mailbox origins ·
        {{ stats.catalog.records }} catalog records
      </p>
      <p v-if="verifyResult" class="stats">
        {{ verifyResult.checked }} checked · {{ verifyResult.bad.length }} failed
      </p>
      <p v-if="error" class="error">{{ error }}</p>
    </header>

    <nav class="tabs">
      <button
        v-for="name in tabs"
        :key="name"
        :class="['tab', { active: tab === name }]"
        @click="tab = name"
      >
        {{ name }}
      </button>
    </nav>

    <div class="panel">
      <SearchView v-if="tab === 'Search'" :on-error="reportError" :on-changed="refreshStats" />
      <ImportView v-else-if="tab === 'Import'" :on-error="reportError" :on-changed="refreshStats" />
      <ResearchView v-else-if="tab === 'Research'" :on-error="reportError" :on-changed="refreshStats" />
      <SyncView v-else-if="tab === 'Sync'" :on-error="reportError" :on-changed="refreshStats" />
      <PreferencesView v-else-if="tab === 'Preferences'" :on-error="reportError" :on-changed="refreshStats" />
      <HealthView v-else-if="tab === 'Health'" :on-error="reportError" :on-changed="refreshStats" />
      <BackupView v-else :on-error="reportError" :on-changed="refreshStats" />
    </div>
  </main>
</template>

<style>
body {
  margin: 0;
  background: #fbfbfc;
}
</style>

<style scoped>
.app {
  max-width: 980px;
  margin: 0 auto;
  padding: 24px;
  font-family: system-ui, sans-serif;
  color: #1b1b1b;
}
h1 {
  font-size: 22px;
  margin: 0 0 14px;
}
.row {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
  align-items: flex-end;
}
.grow {
  flex: 1;
}
input {
  padding: 8px;
  font-size: 14px;
  box-sizing: border-box;
  width: 100%;
}
button {
  padding: 8px 16px;
  cursor: pointer;
}
.stats {
  color: #555;
  font-size: 13px;
  margin: 4px 0;
}
.error {
  color: #b00020;
  font-size: 13px;
}
.tabs {
  display: flex;
  gap: 4px;
  border-bottom: 1px solid #ddd;
  margin: 16px 0 18px;
}
.tab {
  border: none;
  background: none;
  padding: 10px 16px;
  font-size: 14px;
  color: #555;
  border-bottom: 2px solid transparent;
  cursor: pointer;
}
.tab.active {
  color: #123a6b;
  border-bottom-color: #123a6b;
  font-weight: 600;
}
.panel {
  min-height: 320px;
}
</style>
