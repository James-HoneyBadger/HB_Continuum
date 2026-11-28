<script setup lang="ts">
import { onMounted, ref } from "vue";
import { invoke } from "@tauri-apps/api/core";
import { useEngineJob } from "../composables/useEngineJob";

const props = defineProps<{ onError: (message: string) => void; onChanged: () => void }>();

interface CatalogSource {
  source_type: string;
  files: number;
  records: number;
}

interface CatalogDiagnosis {
  available: boolean;
  schema_version?: number;
  schema_current?: boolean;
  sqlite_ok?: boolean;
  foreign_key_errors?: number;
  records?: number;
  source_files?: number;
  index_rows?: number;
  index_missing_rows?: number;
  index_extra_rows?: number;
  index_duplicate_rows?: number;
  dangling_file_references?: number;
  invalid_attachments?: number | null;
  sources?: CatalogSource[];
  consistent?: boolean;
}

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
  undated: number | null;
  catalog?: CatalogDiagnosis;
}

const diagnosis = ref<Diagnosis | null>(null);
const checked = ref("");
const { busy, progress, start } = useEngineJob();

function catalogProblemCount(c: CatalogDiagnosis | undefined) {
  if (!c || !c.available) return 0;
  return (
    (c.sqlite_ok === false ? 1 : 0) +
    (c.schema_current === false ? 1 : 0) +
    (c.foreign_key_errors || 0) +
    (c.index_missing_rows || 0) +
    (c.index_extra_rows || 0) +
    (c.index_duplicate_rows || 0) +
    (c.dangling_file_references || 0) +
    (c.invalid_attachments || 0)
  );
}

function problemCount(d: Diagnosis) {
  return (
    d.foreign_key_errors +
    d.index_missing.length +
    d.index_extra.length +
    d.index_duplicate_rows +
    d.raw_missing.length +
    d.raw_unindexed.length +
    d.raw_invalid.length +
    catalogProblemCount(d.catalog)
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

async function startRepair(kind: "reindex" | "recover_orphans" | "catalog_reindex") {
  try {
    const outcome = await start(kind);
    if (outcome.event === "job_error") {
      props.onError(String(outcome.message || "repair failed"));
      return;
    }
    const result = outcome.result || {};
    const count = result.reindexed ?? result.records_reindexed ?? result.recovered?.length ?? 0;
    progress.value = `${result.action === "recover" ? "Recovered" :
      result.action === "catalog_reindex" ? "Reindexed catalog" : "Reindexed"} ${count}` +
      (result.cancelled ? " (cancelled, progress kept)" : "");
    await refresh();
    props.onChanged();
  } catch (e) {
    props.onError(String(e));
  }
}

onMounted(refresh);
</script>

<template>
  <section class="view">
    <div class="row">
      <button :disabled="busy" @click="refresh">Re-check</button>
      <button :disabled="busy" @click="startRepair('reindex')">Reindex derived data</button>
      <button :disabled="busy" @click="startRepair('catalog_reindex')">Reindex catalog</button>
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
        <li v-if="diagnosis.undated !== null">
          Records without a normalized date: {{ diagnosis.undated }} (sorted last in the timeline)
        </li>
      </ul>
      <template v-if="diagnosis.catalog?.available">
        <p class="section-title">Catalog</p>
        <ul class="counts">
          <li>
            Schema: v{{ diagnosis.catalog.schema_version }}
            ({{ diagnosis.catalog.schema_current === false ? "needs migration" : "current" }})
          </li>
          <li>SQLite quick check: {{ diagnosis.catalog.sqlite_ok ? "ok" : "failed" }}</li>
          <li>Foreign key errors: {{ diagnosis.catalog.foreign_key_errors }}</li>
          <li>
            Records: {{ diagnosis.catalog.records }}
            · Source files: {{ diagnosis.catalog.source_files }}
            · Index rows: {{ diagnosis.catalog.index_rows }}
          </li>
          <li>Missing index rows: {{ diagnosis.catalog.index_missing_rows }}</li>
          <li>Index rows without a record: {{ diagnosis.catalog.index_extra_rows }}</li>
          <li>Duplicate index rows: {{ diagnosis.catalog.index_duplicate_rows }}</li>
          <li>Records without a source file: {{ diagnosis.catalog.dangling_file_references }}</li>
          <li v-if="diagnosis.catalog.invalid_attachments !== null">
            Unreadable attachment metadata: {{ diagnosis.catalog.invalid_attachments }}
          </li>
        </ul>
      </template>
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
  color: var(--hb-text-secondary);
  font-size: 13px;
}
.headline {
  font-size: 15px;
}
.headline.bad {
  color: var(--hb-error-text);
}
.section-title {
  margin: 14px 0 4px;
  font-size: 14px;
  font-weight: 600;
}
.counts {
  font-size: 13px;
  color: var(--hb-text);
}
.json {
  background: var(--hb-panel-alt);
  padding: 10px;
  font-size: 12px;
  overflow-x: auto;
}
</style>
