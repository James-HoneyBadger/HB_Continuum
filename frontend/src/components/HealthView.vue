<script setup lang="ts">
import { onMounted, onUnmounted, ref } from "vue";
import { invoke } from "@tauri-apps/api/core";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";

const props = defineProps<{ onError: (message: string) => void; onChanged: () => void }>();

interface Diagnosis {
  sqlite_ok: boolean;
  foreign_key_errors: number;
  messages: number;
  index_missing: string[];
  index_extra: string[];
  index_duplicate_rows: number;
  raw_missing: string[];
  raw_unindexed: string[];
  raw_invalid: string[];
}

const diagnosis = ref<Diagnosis | null>(null);
const busy = ref(false);
const progress = ref("");
const activeJob = ref("");
const checked = ref("");

let unlisten: UnlistenFn | null = null;

function problemCount(d: Diagnosis) {
  return (
    d.foreign_key_errors +
    d.index_missing.length +
    d.index_extra.length +
    d.index_duplicate_rows +
    d.raw_missing.length +
    d.raw_unindexed.length +
    d.raw_invalid.length
  );
}

async function refresh() {
  try {
    diagnosis.value = (await invoke("health")) as Diagnosis;
    checked.value = new Date().toLocaleTimeString();
  } catch (e) {
    props.onError(String(e));
  }
}

async function startRepair(kind: "reindex" | "recover_orphans") {
  if (busy.value) return;
  busy.value = true;
  progress.value = "starting…";
  try {
    const response = (await invoke(kind)) as { job_id: string };
    activeJob.value = response.job_id;
  } catch (e) {
    busy.value = false;
    progress.value = "";
    props.onError(String(e));
  }
}

function handleEvent(payload: any) {
  if (!activeJob.value || payload.job_id !== activeJob.value) return;
  if (payload.event === "progress") {
    progress.value = `${payload.done}/${payload.total} ${payload.status}`;
  } else if (payload.event === "job_complete") {
    const result = payload.result || {};
    const count = result.reindexed ?? result.recovered?.length ?? 0;
    progress.value = `${result.action === "recover" ? "Recovered" : "Reindexed"} ${count}` +
      (result.cancelled ? " (cancelled, progress kept)" : "");
    busy.value = false;
    activeJob.value = "";
    void refresh().then(() => props.onChanged());
  } else if (payload.event === "job_error") {
    progress.value = "";
    busy.value = false;
    activeJob.value = "";
    props.onError(String(payload.message || "repair failed"));
  }
}

onMounted(async () => {
  unlisten = await listen("engine-event", (event) => handleEvent(event.payload));
  await refresh();
});

onUnmounted(() => {
  if (unlisten) unlisten();
});
</script>

<template>
  <section class="view">
    <div class="row">
      <button :disabled="busy" @click="refresh">Re-check</button>
      <button :disabled="busy" @click="startRepair('reindex')">Reindex derived data</button>
      <button :disabled="busy" @click="startRepair('recover_orphans')">Recover orphaned files</button>
      <span v-if="checked" class="meta">checked {{ checked }}</span>
    </div>
    <p v-if="progress" class="meta">{{ progress }}</p>

    <div v-if="diagnosis" class="summary">
      <p :class="['headline', { bad: !diagnosis.sqlite_ok || problemCount(diagnosis) }]">
        <template v-if="diagnosis.sqlite_ok && !problemCount(diagnosis)">
          Locally consistent · {{ diagnosis.messages }} messages · no missing, extra or altered data
        </template>
        <template v-else>
          {{ problemCount(diagnosis) }} issue(s) found · {{ diagnosis.messages }} messages
        </template>
      </p>
      <ul class="counts">
        <li>SQLite quick check: {{ diagnosis.sqlite_ok ? "ok" : "failed" }}</li>
        <li>Foreign key errors: {{ diagnosis.foreign_key_errors }}</li>
        <li>Missing search rows: {{ diagnosis.index_missing.length }}</li>
        <li>Search rows without a message: {{ diagnosis.index_extra.length }}</li>
        <li>Duplicate search rows: {{ diagnosis.index_duplicate_rows }}</li>
        <li>Missing original files: {{ diagnosis.raw_missing.length }}</li>
        <li>Unindexed originals: {{ diagnosis.raw_unindexed.length }}</li>
        <li>Altered or unsafe originals: {{ diagnosis.raw_invalid.length }}</li>
      </ul>
      <details>
        <summary>Full report</summary>
        <pre class="json">{{ JSON.stringify(diagnosis, null, 2) }}</pre>
      </details>
      <p class="meta">
        Health reports local consistency only; it cannot prove that a mailbox was fully downloaded.
        Reindexing rebuilds derived text from the preserved originals and can be interrupted safely.
      </p>
    </div>
  </section>
</template>

<style scoped>
.row {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  align-items: center;
}
button {
  padding: 8px 16px;
}
.meta {
  color: #666;
  font-size: 13px;
}
.headline {
  font-size: 15px;
}
.headline.bad {
  color: #b00020;
}
.counts {
  font-size: 13px;
  color: #333;
}
.json {
  background: #f2f3f5;
  padding: 10px;
  font-size: 12px;
  overflow-x: auto;
}
</style>
