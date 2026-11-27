<script setup lang="ts">
import { ref } from "vue";
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
const { busy, progress, start } = useEngineJob();

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
    importResult.value = (await invoke("import_eml", { paths })) as any;
    props.onChanged();
  } catch (e) {
    props.onError(String(e));
  }
}
</script>

<template>
  <section>
    <h2>Import EML</h2>
    <p class="meta">
      Original message bytes are preserved under their SHA-256 and never modified. Import is idempotent.
    </p>
    <div class="row">
      <button @click="chooseFiles">Choose .eml files…</button>
      <button @click="chooseFolder">Choose folder…</button>
      <button @click="runImport" :disabled="!importPaths.length && !importPath">Import</button>
    </div>
    <p v-if="importPaths.length" class="meta">
      {{ importPaths.length === 1 ? importPaths[0] : importPaths.length + " files selected" }}
    </p>
    <div class="row">
      <input class="grow" v-model="importPath" placeholder="…or type a path to a .eml file or directory" />
    </div>
    <p v-if="importResult" class="meta">
      {{ importResult.files_seen }} files seen · {{ importResult.imported }} newly imported ·
      {{ importResult.errors.length }} errors
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
  color: #666;
  font-size: 13px;
}
.errors {
  color: #b00020;
  font-size: 13px;
}
</style>
