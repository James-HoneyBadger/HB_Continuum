<script setup lang="ts">
import { onMounted, onUnmounted, ref } from "vue";
import { invoke } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-dialog";
import OverviewView from "./components/OverviewView.vue";
import SearchView from "./components/SearchView.vue";
import AdvancedSearchView from "./components/AdvancedSearchView.vue";
import ImportView from "./components/ImportView.vue";
import SourcesView from "./components/SourcesView.vue";
import CollectionsView from "./components/CollectionsView.vue";
import JournalView from "./components/JournalView.vue";
import ReportsView from "./components/ReportsView.vue";
import ResearchView from "./components/ResearchView.vue";
import SyncView from "./components/SyncView.vue";
import PreferencesView from "./components/PreferencesView.vue";
import HealthView from "./components/HealthView.vue";
import BackupView from "./components/BackupView.vue";
import TimelineView from "./components/TimelineView.vue";
import RelationshipsView from "./components/RelationshipsView.vue";
import IntelligenceView from "./components/IntelligenceView.vue";

interface Stats {
  archive: { messages: number; origins: number };
  catalog: { files: number; records: number };
}

interface EncryptionStatus {
  encrypted: boolean;
  unlocked: boolean;
}

const tabs = [
  "Overview",
  "Intelligence",
  "Timeline",
  "Relationships",
  "Search",
  "Advanced",
  "Sources",
  "Import",
  "Research",
  "Collections",
  "Journal",
  "Reports",
  "Sync",
  "Health",
  "Backup",
  "Preferences",
] as const;
const tab = ref<(typeof tabs)[number]>("Overview");
const tabHelp: Record<(typeof tabs)[number], string> = {
  Overview: "Archive summary and coverage",
  Intelligence: "Ask questions and inspect cited evidence",
  Timeline: "Browse records in date order",
  Relationships: "Thread co-participation",
  Search: "Search email, Facebook and documents",
  Advanced: "Build an explicit boolean query",
  Sources: "Coverage and removal of imported sources",
  Import: "Import EML, Facebook exports and documents",
  Research: "Saved searches, rules and reports",
  Collections: "Named evidence collections",
  Journal: "Your retrospective notes",
  Reports: "Archive consistency reports",
  Sync: "Scheduled mailbox synchronization",
  Health: "Local consistency checks and repair",
  Backup: "Verified snapshots and restoration",
  Preferences: "Archive-specific settings",
};

const archive = ref("~/.hb-dispatch");
const stats = ref<Stats | null>(null);
const error = ref("");
const verifyResult = ref<{ checked: number; bad: string[] } | null>(null);
const encryption = ref<EncryptionStatus>({ encrypted: false, unlocked: false });
const password = ref("");
const unlocking = ref(false);
const working = ref(false);
const archiveExists = ref<boolean | null>(null);
const boundaryAck = ref(localStorage.getItem("hb.boundaryNotice") === "acknowledged");

async function acknowledgeBoundary() {
  try {
    await invoke("acknowledge_boundary_notice");
  } catch (e) {
    error.value = String(e);
  }
  boundaryAck.value = true;
  localStorage.setItem("hb.boundaryNotice", "acknowledged");
}

async function refreshStats() {
  try {
    stats.value = (await invoke("stats")) as Stats;
    error.value = "";
  } catch (e) {
    error.value = String(e);
  }
}

async function refreshEncryption() {
  try {
    encryption.value = (await invoke("encryption_status")) as EncryptionStatus;
    if (encryption.value.encrypted && !encryption.value.unlocked) {
      stats.value = null;
    }
  } catch (e) {
    error.value = String(e);
  }
}

async function refreshArchive() {
  error.value = "";
  try {
    const status = (await invoke("archive_status")) as { exists: boolean };
    archiveExists.value = Boolean(status.exists);
    if (!status.exists) {
      stats.value = null;
      verifyResult.value = null;
      encryption.value = { encrypted: false, unlocked: false };
      return;
    }
    encryption.value = { encrypted: false, unlocked: false };
    await refreshEncryption();
    if (!encryption.value.encrypted || encryption.value.unlocked) {
      await refreshStats();
    }
  } catch (e) {
    archiveExists.value = null;
    error.value = String(e);
  }
}

async function applyArchive() {
  if (!archive.value.trim()) {
    error.value = "Enter an archive folder or choose one.";
    return;
  }
  error.value = "";
  verifyResult.value = null;
  stats.value = null;
  password.value = "";
  archiveExists.value = null;
  working.value = true;
  try {
    await invoke("set_archive", { path: archive.value.trim() });
    await refreshArchive();
  } catch (e) {
    archiveExists.value = null;
    error.value = String(e);
  } finally {
    working.value = false;
  }
}

async function chooseArchiveFolder() {
  error.value = "";
  try {
    const selected = await open({
      directory: true,
      multiple: false,
      title: "Choose an HB Continuum archive folder",
    });
    if (!selected || Array.isArray(selected)) return;
    archive.value = selected;
    await applyArchive();
  } catch (e) {
    error.value = String(e);
  }
}

async function createArchive() {
  if (!archive.value.trim()) {
    error.value = "Choose a folder for the new archive first.";
    return;
  }
  error.value = "";
  stats.value = null;
  archiveExists.value = null;
  working.value = true;
  try {
    await invoke("create_archive", { path: archive.value.trim() });
    await invoke("set_archive", { path: archive.value.trim() });
    await refreshArchive();
  } catch (e) {
    archiveExists.value = null;
    error.value = String(e);
  } finally {
    working.value = false;
  }
}

async function unlockArchive() {
  if (!password.value) return;
  unlocking.value = true;
  error.value = "";
  try {
    encryption.value = (await invoke("encryption_unlock", {
      password: password.value,
    })) as EncryptionStatus;
    password.value = "";
    await refreshStats();
  } catch (e) {
    error.value = String(e);
  } finally {
    unlocking.value = false;
  }
}

async function lockArchive() {
  error.value = "";
  password.value = "";
  try {
    encryption.value = (await invoke("encryption_lock")) as EncryptionStatus;
    stats.value = null;
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

function selectTab(name: (typeof tabs)[number]) {
  tab.value = name;
  error.value = "";
}

function openArchiveFromChild(path: string) {
  archive.value = path;
  void applyArchive();
}

function handleShortcut(event: KeyboardEvent) {
  if (!(event.metaKey || event.ctrlKey) || event.altKey) return;
  if (event.key.toLowerCase() !== "f") return;
  if (archiveExists.value !== true || (encryption.value.encrypted && !encryption.value.unlocked)) return;
  event.preventDefault();
  selectTab("Search");
}

onMounted(() => {
  void refreshArchive();
  window.addEventListener("keydown", handleShortcut);
});
onUnmounted(() => window.removeEventListener("keydown", handleShortcut));
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
          <input
            v-model="archive"
            placeholder="~/.hb-dispatch"
            spellcheck="false"
            @keyup.enter="applyArchive"
          />
        </label>
        <button :disabled="working" @click="applyArchive">
          {{ working ? "Working…" : "Open" }}
        </button>
        <button :disabled="working" @click="chooseArchiveFolder">Open folder…</button>
        <button
          :disabled="working || !archiveExists || (encryption.encrypted && !encryption.unlocked)"
          @click="runVerify"
        >
          Verify integrity
        </button>
        <button v-if="encryption.encrypted && encryption.unlocked" @click="lockArchive">
          Lock
        </button>
      </div>
    </header>

    <section v-if="archiveExists && !boundaryAck" class="boundary-notice" aria-live="polite">
      <div>
        <strong>What encryption covers.</strong>
        An encrypted archive protects <code>archive.sqlite3</code>,
        <code>research.sqlite3</code> and <code>catalog.sqlite3</code>. Original
        EML files, imported documents, preferences, exports and logs are stored
        as ordinary files and stay readable on disk. Use FileVault, BitLocker or
        an encrypted container for the archive folder as well.
      </div>
      <button class="secondary" @click="acknowledgeBoundary">Understood</button>
    </section>

    <section v-if="archiveExists === null" class="center-state" aria-live="polite">
      <h2>{{ error ? "Could not open the archive" : "Opening archive…" }}</h2>
      <p class="meta">
        {{ error || "Checking the selected archive folder." }}
      </p>
      <div v-if="error" class="row">
        <button :disabled="working" @click="refreshArchive">Try again</button>
        <button :disabled="working" @click="chooseArchiveFolder">Choose another folder…</button>
      </div>
    </section>

    <section v-else-if="encryption.encrypted && !encryption.unlocked" class="unlock-panel">
      <h2>Encrypted archive locked</h2>
      <p class="meta">
        Enter the archive password. It is used only in memory to unlock this session and is
        never saved to preferences, logs or command-line arguments.
      </p>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <div class="row">
        <input
          v-model="password"
          type="password"
          autocomplete="current-password"
          autofocus
          placeholder="Archive password"
          @keyup.enter="unlockArchive"
        />
        <button :disabled="unlocking || !password" @click="unlockArchive">
          {{ unlocking ? "Unlocking…" : "Unlock" }}
        </button>
      </div>
    </section>

    <section v-else-if="archiveExists === false" class="center-state">
      <h2>No archive at this location</h2>
      <p class="meta">
        HB Continuum keeps each archive in its own folder. Choose an existing archive or
        create a new one here. Nothing is downloaded or uploaded.
      </p>
      <p class="path"><code>{{ archive }}</code></p>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <div class="row">
        <button :disabled="working" @click="createArchive">
          {{ working ? "Creating…" : "Create archive here" }}
        </button>
        <button :disabled="working" @click="chooseArchiveFolder">Choose another folder…</button>
      </div>
      <p class="meta">
        New archives created here use standard SQLite files. To create an encrypted archive,
        run <code>dispatch.py --archive PATH init-encrypted</code> before opening it. Existing
        encrypted archives can be opened from this screen.
      </p>
    </section>

    <div v-else class="body">
      <nav class="nav" aria-label="Workspaces">
        <button
          v-for="name in tabs"
          :key="name"
          type="button"
          :class="['nav-item', { active: tab === name }]"
          :aria-current="tab === name ? 'page' : undefined"
          :title="tabHelp[name]"
          @click="selectTab(name)"
        >
          {{ name }}
        </button>
      </nav>

      <main class="workspace" :aria-label="tab">
        <p v-if="error" class="error" role="alert">{{ error }}</p>
        <OverviewView v-if="tab === 'Overview'" :on-error="reportError" :on-changed="refreshStats" />
        <IntelligenceView v-else-if="tab === 'Intelligence'" :on-error="reportError" :on-changed="refreshStats" />
        <SearchView v-else-if="tab === 'Search'" :on-error="reportError" :on-changed="refreshStats" />
        <AdvancedSearchView v-else-if="tab === 'Advanced'" :on-error="reportError" :on-changed="refreshStats" />
        <TimelineView v-else-if="tab === 'Timeline'" :on-error="reportError" :on-changed="refreshStats" />
        <RelationshipsView v-else-if="tab === 'Relationships'" :on-error="reportError" :on-changed="refreshStats" />
        <SourcesView v-else-if="tab === 'Sources'" :on-error="reportError" :on-changed="refreshStats" />
        <ImportView v-else-if="tab === 'Import'" :on-error="reportError" :on-changed="refreshStats" />
        <ResearchView v-else-if="tab === 'Research'" :on-error="reportError" :on-changed="refreshStats" />
        <CollectionsView v-else-if="tab === 'Collections'" :on-error="reportError" :on-changed="refreshStats" />
        <JournalView v-else-if="tab === 'Journal'" :on-error="reportError" :on-changed="refreshStats" />
        <ReportsView v-else-if="tab === 'Reports'" :on-error="reportError" :on-changed="refreshStats" />
        <SyncView v-else-if="tab === 'Sync'" :on-error="reportError" :on-changed="refreshStats" />
        <HealthView v-else-if="tab === 'Health'" :on-error="reportError" :on-changed="refreshStats" />
        <BackupView
          v-else-if="tab === 'Backup'"
          :on-error="reportError"
          :on-changed="refreshStats"
          :on-open-archive="openArchiveFromChild"
        />
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
.boundary-notice {
  display: flex;
  align-items: center;
  gap: 16px;
  justify-content: space-between;
  padding: 10px 16px;
  background: var(--hb-warning-bg, #fff6d6);
  color: var(--hb-warning-text, #4a3a00);
  border-bottom: 1px solid var(--hb-border-strong);
  font-size: 0.9rem;
  line-height: 1.4;
}
.boundary-notice code {
  font-size: 0.85em;
}
.boundary-notice button {
  flex: 0 0 auto;
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
.unlock-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  max-width: 560px;
  margin: 0 auto;
  padding: 24px;
  gap: 12px;
}
.unlock-panel h2 {
  margin: 0;
  font-size: 18px;
}
.unlock-panel .row {
  display: flex;
  gap: 8px;
}
.unlock-panel input {
  flex: 1;
  padding: 9px;
  font-size: 14px;
}
.center-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  max-width: 620px;
  margin: 0 auto;
  padding: 28px;
  gap: 12px;
}
.center-state h2 {
  margin: 0;
  font-size: 19px;
}
.center-state .row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.path {
  margin: 0;
  padding: 8px 10px;
  background: var(--hb-panel-alt);
  border: 1px solid var(--hb-border);
  border-radius: var(--hb-radius);
  overflow-wrap: anywhere;
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
