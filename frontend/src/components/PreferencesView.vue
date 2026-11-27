<script setup lang="ts">
import { ref } from "vue";
import { invoke } from "@tauri-apps/api/core";

const props = defineProps<{ onError: (message: string) => void; onChanged: () => void }>();

const values = ref<Record<string, any>>({});
const fields = ref<any[]>([]);
const notice = ref("");

async function load() {
  try {
    const response = (await invoke("preferences")) as { values: Record<string, any>; fields: any[] };
    values.value = response.values;
    fields.value = response.fields;
  } catch (e) {
    props.onError(String(e));
  }
}

async function save() {
  notice.value = "";
  try {
    const response = (await invoke("preferences_set", { values: values.value })) as {
      values: Record<string, any>;
    };
    values.value = response.values;
    notice.value = "Preferences saved. Restart the workstation to apply appearance changes.";
    props.onChanged();
  } catch (e) {
    props.onError(String(e));
  }
}

function groups(): string[] {
  return [...new Set(fields.value.map((f) => f.group))];
}

load();
</script>

<template>
  <section>
    <h2>Preferences</h2>
    <p class="meta">
      Validated, archive-specific settings. AI remains disabled unless enabled here and the backend is set to Ollama.
    </p>
    <div v-for="group in groups()" :key="group" class="group">
      <h3>{{ group }}</h3>
      <div v-for="field in fields.filter((f) => f.group === group)" :key="field.key" class="pref-row">
        <label :title="field.key">{{ field.label }}</label>
        <input v-if="field.kind === 'bool'" type="checkbox" v-model="values[field.key]" />
        <input v-else-if="field.kind === 'int'" type="number" v-model.number="values[field.key]" />
        <select v-else-if="field.kind === 'choice'" v-model="values[field.key]">
          <option v-for="opt in field.allowed" :key="opt" :value="opt">{{ opt }}</option>
        </select>
        <input v-else v-model="values[field.key]" />
      </div>
    </div>
    <button @click="save">Save preferences</button>
    <p v-if="notice" class="notice">{{ notice }}</p>
  </section>
</template>

<style scoped>
.group {
  margin-bottom: 18px;
}
.pref-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}
.pref-row label {
  flex: 0 0 300px;
  font-size: 13px;
}
.pref-row input,
.pref-row select {
  flex: 1;
  max-width: 420px;
  padding: 6px;
}
button {
  padding: 8px 16px;
}
.meta {
  color: #666;
  font-size: 13px;
}
.notice {
  color: #2e6b2e;
}
</style>
