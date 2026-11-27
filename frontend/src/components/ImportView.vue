<script setup lang="ts">
import { ref } from "vue";
import { invoke } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-dialog";

const props = defineProps<{ onError: (message: string) => void; onChanged: () => void }>();

const importPath = ref("");
const importPaths = ref<string[]>([]);
const importResult = ref<any>(null);

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
