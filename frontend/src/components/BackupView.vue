<script setup lang="ts">
import { onMounted, ref } from "vue";
import { invoke } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-dialog";
import { useEngineJob } from "../composables/useEngineJob";

const props = defineProps<{ onError: (message: string) => void; onChanged: () => void }>();

interface DatabaseReport {
  present?: boolean;
  version?: number;
  target: number;
  pending?: number[];
  error?: string;
}

const schema = ref<Record<string, DatabaseReport> | null>(null);
const backupDestination = ref("");
const snapshot = ref("");
const restoreDestination = ref("");
const notice = ref("");
const restored = ref("");
const { busy, progress, start } = useEngineJob();

async function refreshSchema() {
  try {
    schema.value = (await invoke("migrate_status")) as Record<string, DatabaseReport>;
  } catch (e) {
    props.onError(String(e));
  }
}

async function choose(field: "backup" | "snapshot" | "restore") {
  try {
    const selected = await open({ directory: true, multiple: false });
    if (!selected || Array.isArray(selected)) return;
    if (field === "backup") backupDestination.value = selected;
    else if (field === "snapshot") snapshot.value = selected;
    else restoreDestination.value = selected;
  } catch (e) {
    props.onError(String(e));
  }
}

function reset() {
  notice.value = "";
  restored.value = "";
}

async function runBackup() {
  reset();
  try {
    const outcome = await start("backup", { destination: backupDestination.value.trim() });
    if (outcome.event === "job_error") {
      props.onError(String(outcome.message || "backup failed"));
      return;
    }
    notice.value = `Snapshot verified: ${outcome.result?.files ?? 0} files written to ${backupDestination.value}.`;
    await refreshSchema();
  } catch (e) {
    props.onError(String(e));
  }
}

async function runVerify() {
  reset();
  try {
    const outcome = await start("verify_backup", { snapshot: snapshot.value.trim() });
    if (outcome.event === "job_error") {
      props.onError(String(outcome.message || "snapshot verification failed"));
      return;
    }
    notice.value = `Snapshot verified: ${outcome.result?.files ?? 0} files, hashes and indexes match.`;
  } catch (e) {
    props.onError(String(e));
  }
}

async function runRestore() {
  reset();
  try {
    const outcome = await start("restore", {
      snapshot: snapshot.value.trim(),
      destination: restoreDestination.value.trim(),
    });
    if (outcome.event === "job_error") {
      props.onError(String(outcome.message || "restore failed"));
      return;
    }
    restored.value = restoreDestination.value.trim();
    notice.value = "Restored copy verified. Scheduling profiles in it are disabled.";
    props.onChanged();
  } catch (e) {
    props.onError(String(e));
  }
}

onMounted(refreshSchema);
</script>

<template>
  <section class="view">
    <p v-if="progress" class="meta">{{ progress }}</p>

    <h2>Schema</h2>
    <ul v-if="schema" class="schema">
      <li v-for="(entry, name) in schema" :key="name">
        <strong>{{ name }}</strong>
        <template v-if="!entry.present">· not present (target {{ entry.target }})</template>
        <template v-else-if="entry.error">· <span class="bad">{{ entry.error }}</span></template>
        <template v-else>
          · schema {{ entry.version }} of {{ entry.target }} ·
          <span v-if="entry.pending && entry.pending.length">pending {{ entry.pending.join(", ") }}</span>
          <span v-else>up to date</span>
        </template>
      </li>
    </ul>
    <p class="meta">
      Databases migrate when the engine opens them; this view never changes a schema.
    </p>

    <h2>Backup</h2>
    <div class="row">
      <input v-model="backupDestination" class="grow" placeholder="New folder outside the archive" />
      <button :disabled="busy" @click="choose('backup')">Browse…</button>
      <button :disabled="busy || !backupDestination" @click="runBackup">Create verified backup</button>
    </div>
    <p class="meta">
      Copies databases, configuration and every original with a SHA-256 manifest. Existing
      destinations are refused; the snapshot is validated before it is published.
    </p>

    <h2>Verify snapshot</h2>
    <div class="row">
      <input v-model="snapshot" class="grow" placeholder="Snapshot folder" />
      <button :disabled="busy" @click="choose('snapshot')">Browse…</button>
      <button :disabled="busy || !snapshot" @click="runVerify">Verify snapshot</button>
    </div>

    <h2>Restore</h2>
    <div class="row">
      <input v-model="restoreDestination" class="grow" placeholder="New folder for the restored archive" />
      <button :disabled="busy" @click="choose('restore')">Browse…</button>
      <button :disabled="busy || !snapshot || !restoreDestination" @click="runRestore">
        Restore to new folder
      </button>
    </div>
    <p class="meta">
      Restores from the snapshot chosen above into an empty destination, verifies the copy and
      disables its scheduling profiles. Keychain credentials are never part of a snapshot.
    </p>
    <p v-if="restored" class="meta">
      Restored to {{ restored }} — enter that path in the Archive field at the top to open it.
    </p>

    <p v-if="notice" class="notice">{{ notice }}</p>
  </section>
</template>

<style scoped>
h2 {
  font-size: 15px;
  margin: 18px 0 8px;
}
.row {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
  align-items: center;
}
.grow {
  flex: 1;
}
input {
  padding: 8px;
  font-size: 14px;
  box-sizing: border-box;
}
button {
  padding: 8px 16px;
}
.meta {
  color: var(--hb-text-secondary);
  font-size: 13px;
}
.notice {
  color: var(--hb-success-text);
  font-size: 13px;
}
.bad {
  color: var(--hb-error-text);
}
.schema {
  font-size: 13px;
  margin: 0 0 8px;
  padding-left: 20px;
}
</style>
