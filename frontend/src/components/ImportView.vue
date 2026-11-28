<script setup lang="ts">
import { onMounted, ref } from "vue";
import { invoke } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-dialog";
import { useEngineJob } from "../composables/useEngineJob";

const props = defineProps<{ onError: (message: string) => void; onChanged: () => void }>();

const importPath = ref("");
const importPaths = ref<string[]>([]);
const importResult = ref<any>(null);

const facebookPaths = ref<string[]>([]);
const facebookPreview = ref<any>(null);
const facebookResult = ref<any>(null);
const documentPaths = ref<string[]>([]);
const documentPreview = ref<any>(null);
const documentResult = ref<any>(null);
const history = ref<any[]>([]);
const historyAvailable = ref(true);
const { busy, progress, start, cancel } = useEngineJob();

async function loadHistory() {
  try {
    const response = (await invoke("import_history", { limit: 25 })) as {
      available: boolean;
      runs: any[];
    };
    historyAvailable.value = response.available;
    history.value = response.runs;
  } catch (e) {
    props.onError(String(e));
  }
}

async function chooseFiles() {
  try {
    const selected = await open({ multiple: true, filters: [{ name: "Email", extensions: ["eml"] }] });
    if (!selected) return;
    importPaths.value = Array.isArray(selected) ? selected : [selected];
    importResult.value = null;
  } catch (e) {
    props.onError(String(e));
  }
}

async function chooseFolder() {
  try {
    const selected = await open({ directory: true, multiple: false });
    if (!selected || Array.isArray(selected)) return;
    importPaths.value = [selected];
    importResult.value = null;
  } catch (e) {
    props.onError(String(e));
  }
}

async function chooseFacebookFiles() {
  try {
    const selected = await open({ multiple: true, filters: [{ name: "JSON", extensions: ["json"] }] });
    if (!selected) return;
    facebookPaths.value = Array.isArray(selected) ? selected : [selected];
    facebookPreview.value = null;
    facebookResult.value = null;
  } catch (e) {
    props.onError(String(e));
  }
}

async function chooseFacebookFolder() {
  try {
    const selected = await open({ directory: true, multiple: false });
    if (!selected || Array.isArray(selected)) return;
    facebookPaths.value = [selected];
    facebookPreview.value = null;
    facebookResult.value = null;
  } catch (e) {
    props.onError(String(e));
  }
}

async function runFacebookPreview() {
  facebookPreview.value = null;
  facebookResult.value = null;
  try {
    facebookPreview.value = (await invoke("facebook_preview", { paths: facebookPaths.value })) as any;
  } catch (e) {
    props.onError(String(e));
  }
}

async function runFacebookImport() {
  facebookPreview.value = null;
  facebookResult.value = null;
  try {
    const outcome = await start("facebook_import", { paths: facebookPaths.value });
    if (outcome.event === "job_error") {
      props.onError(String(outcome.message || "Facebook import failed"));
      return;
    }
    facebookResult.value = outcome.result;
    await loadHistory();
    props.onChanged();
  } catch (e) {
    props.onError(String(e));
  }
}

async function chooseDocumentFiles() {
  try {
    const selected = await open({
      multiple: true,
      filters: [{
        name: "Documents",
        extensions: ["txt", "md", "markdown", "csv", "json", "pdf", "docx"],
      }],
    });
    if (!selected) return;
    documentPaths.value = Array.isArray(selected) ? selected : [selected];
    documentPreview.value = null;
    documentResult.value = null;
  } catch (e) {
    props.onError(String(e));
  }
}

async function chooseDocumentFolder() {
  try {
    const selected = await open({ directory: true, multiple: false });
    if (!selected || Array.isArray(selected)) return;
    documentPaths.value = [selected];
    documentPreview.value = null;
    documentResult.value = null;
  } catch (e) {
    props.onError(String(e));
  }
}

async function runDocumentPreview() {
  documentPreview.value = null;
  documentResult.value = null;
  try {
    documentPreview.value = (await invoke("document_preview", {
      paths: documentPaths.value,
    })) as any;
  } catch (e) {
    props.onError(String(e));
  }
}

async function runDocumentImport() {
  documentPreview.value = null;
  documentResult.value = null;
  try {
    const outcome = await start("document_import", { paths: documentPaths.value });
    if (outcome.event === "job_error") {
      props.onError(String(outcome.message || "Document import failed"));
      return;
    }
    documentResult.value = outcome.result;
    await loadHistory();
    props.onChanged();
  } catch (e) {
    props.onError(String(e));
  }
}

async function runImport() {
  importResult.value = null;
  const paths = importPaths.value.length ? importPaths.value : importPath.value ? [importPath.value] : [];
  if (!paths.length) {
    props.onError("Choose .eml files or a folder first");
    return;
  }
  try {
    const outcome = await start("import_eml", { paths });
    if (outcome.event === "job_error") {
      props.onError(String(outcome.message || "EML import failed"));
      await loadHistory();
      return;
    }
    importResult.value = outcome.result;
    await loadHistory();
    props.onChanged();
  } catch (e) {
    props.onError(String(e));
  }
}

onMounted(loadHistory);
</script>

<template>
  <section>
    <h2>Import EML</h2>
    <p class="meta">
      Original message bytes are preserved under their SHA-256 and never modified. Import is idempotent.
    </p>
    <div class="row">
      <button :disabled="busy" @click="chooseFiles">Choose .eml files…</button>
      <button :disabled="busy" @click="chooseFolder">Choose folder…</button>
      <button @click="runImport" :disabled="busy || (!importPaths.length && !importPath)">
        {{ busy ? "Importing…" : "Import" }}
      </button>
      <button v-if="busy" @click="cancel">Cancel</button>
    </div>
    <p v-if="progress" class="meta">{{ progress }}</p>
    <p v-if="importPaths.length" class="meta">
      {{ importPaths.length === 1 ? importPaths[0] : importPaths.length + " files selected" }}
    </p>
    <div class="row">
      <input class="grow" v-model="importPath" placeholder="…or type a path to a .eml file or directory" />
    </div>
    <p v-if="importResult" class="meta">
      {{ importResult.files_seen }} files seen · {{ importResult.imported }} newly imported ·
      {{ importResult.existing }} already present · {{ importResult.errors.length }} errors
      <span v-if="importResult.cancelled">· cancelled, completed work was kept</span>
    </p>
    <ul v-if="importResult && importResult.errors.length" class="errors">
      <li v-for="e in importResult.errors" :key="e.path"><span class="meta">{{ e.path }}</span> {{ e.error }}</li>
    </ul>

    <h2>Import Facebook export</h2>
    <p class="meta">
      Reads a user-obtained Facebook JSON export offline. Original export files are never modified
      or uploaded; each record keeps its source JSON and import is idempotent.
    </p>
    <div class="row">
      <button @click="chooseFacebookFiles">Choose JSON files…</button>
      <button @click="chooseFacebookFolder">Choose export folder…</button>
      <button :disabled="!facebookPaths.length || busy" @click="runFacebookPreview">Preview</button>
      <button :disabled="!facebookPaths.length || busy" @click="runFacebookImport">Import</button>
    </div>
    <p v-if="facebookPaths.length" class="meta">
      {{ facebookPaths.length === 1 ? facebookPaths[0] : facebookPaths.length + " selections" }}
    </p>
    <p v-if="progress" class="meta">{{ progress }}</p>
    <p v-if="facebookPreview" class="meta">
      {{ facebookPreview.files_discovered }} files · {{ facebookPreview.supported_records }} supported
      records · {{ facebookPreview.unsupported_records }} unsupported
    </p>
    <ul v-if="facebookPreview && facebookPreview.warnings.length" class="errors">
      <li v-for="(warning, i) in facebookPreview.warnings" :key="i">{{ warning }}</li>
    </ul>
    <p v-if="facebookResult" class="meta">
      {{ facebookResult.files_imported }} files imported · {{ facebookResult.records_imported }} records ·
      {{ facebookResult.records_duplicate }} duplicates · {{ facebookResult.files_skipped }} files skipped
    </p>
    <ul v-if="facebookResult && facebookResult.warnings.length" class="errors">
      <li v-for="(warning, i) in facebookResult.warnings" :key="i">{{ warning }}</li>
    </ul>

    <h2>Import documents</h2>
    <p class="meta">
      Imports local text, Markdown, CSV, JSON, PDF and DOCX into the source-independent catalog.
      Originals are hashed and referenced, never copied or uploaded. PDF and DOCX text extraction
      requires an optional local package; files without extractable text are reported, not faked.
    </p>
    <div class="row">
      <button :disabled="busy" @click="chooseDocumentFiles">Choose document files…</button>
      <button :disabled="busy" @click="chooseDocumentFolder">Choose folder…</button>
      <button :disabled="!documentPaths.length || busy" @click="runDocumentPreview">Preview</button>
      <button :disabled="!documentPaths.length || busy" @click="runDocumentImport">Import</button>
    </div>
    <p v-if="documentPaths.length" class="meta">
      {{ documentPaths.length === 1 ? documentPaths[0] : documentPaths.length + " selections" }}
    </p>
    <p v-if="documentPreview" class="meta">
      {{ documentPreview.files_discovered }} files ·
      {{ documentPreview.supported_files }} supported ·
      {{ documentPreview.unsupported_files }} unsupported
    </p>
    <ul v-if="documentPreview && documentPreview.extractor_warnings.length" class="errors">
      <li v-for="(warning, i) in documentPreview.extractor_warnings" :key="i">{{ warning }}</li>
    </ul>
    <ul v-if="documentPreview && documentPreview.warnings.length" class="errors">
      <li v-for="(warning, i) in documentPreview.warnings" :key="i">{{ warning }}</li>
    </ul>
    <p v-if="documentResult" class="meta">
      {{ documentResult.records_imported }} documents imported ·
      {{ documentResult.files_skipped }} already present ·
      {{ documentResult.extraction_failures }} extraction failures ·
      {{ documentResult.characters_indexed.toLocaleString() }} characters indexed ·
      {{ documentResult.pages_indexed }} pages indexed
      <span v-if="documentResult.cancelled">· cancelled, completed work was kept</span>
    </p>
    <ul v-if="documentResult && documentResult.errors.length" class="errors">
      <li v-for="(error, i) in documentResult.errors" :key="i">
        <span class="meta">{{ error.path }}</span> {{ error.error }}
      </li>
    </ul>

    <h2>Import history</h2>
    <p v-if="!historyAvailable" class="meta">
      This archive predates import tracking; new runs will be recorded after it is opened by this build.
    </p>
    <table v-else-if="history.length" class="history">
      <thead>
        <tr>
          <th>Finished</th>
          <th>Source</th>
          <th>Target</th>
          <th>Status</th>
          <th>Seen</th>
          <th>New</th>
          <th>Existing</th>
          <th>Failed</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="run in history" :key="run.id">
          <td>{{ run.finished_at || run.started_at }}</td>
          <td>{{ run.source }}</td>
          <td class="target" :title="run.source_key">{{ run.source_key || "—" }}</td>
          <td :class="{ bad: run.status === 'error' }">{{ run.status }}</td>
          <td>{{ run.records_seen ?? "—" }}</td>
          <td>{{ run.records_new ?? "—" }}</td>
          <td>{{ run.records_existing ?? "—" }}</td>
          <td>{{ run.records_failed ?? "—" }}</td>
        </tr>
      </tbody>
    </table>
    <p v-else class="meta">No imports recorded yet.</p>
    <p class="meta">
      Counts describe what the engine actually processed in each run; a cancelled run keeps the
      records it already committed, and re-running it is safe.
    </p>
  </section>
</template>

<style scoped>
.row {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  align-items: center;
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
}
.meta {
  color: var(--hb-text-secondary);
  font-size: 13px;
}
.errors {
  color: var(--hb-error-text);
  font-size: 13px;
}
.history {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
.history th,
.history td {
  text-align: left;
  padding: 4px 6px;
  border-bottom: 1px solid var(--hb-border);
  font-variant-numeric: tabular-nums;
}
.history th {
  color: var(--hb-text-secondary);
  font-weight: 600;
}
.history td.bad {
  color: var(--hb-error-text);
}
.history td.target {
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
