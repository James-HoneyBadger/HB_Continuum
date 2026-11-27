<script setup lang="ts">
import { ref } from "vue";
import { invoke } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-dialog";

const props = defineProps<{ onError: (message: string) => void; onChanged: () => void }>();

interface ResultItem {
  source: string;
  id: string;
  kind: string;
  title: string;
  actor: string;
  date: string;
  snippet: string;
}

const query = ref("");
const results = ref<ResultItem[]>([]);
const total = ref(0);
const busy = ref(false);
const detail = ref<any>(null);
const threadView = ref<any[] | null>(null);
const selected = ref<string[]>([]);
const tagName = ref("");
const notice = ref("");

async function runSearch() {
  busy.value = true;
  notice.value = "";
  try {
    const response = (await invoke("search", {
      query: query.value,
      sources: ["email", "facebook"],
      page: 1,
      pageSize: 50,
    })) as { items: ResultItem[]; total: number };
    results.value = response.items;
    total.value = response.total;
    selected.value = [];
    detail.value = null;
    threadView.value = null;
  } catch (e) {
    props.onError(String(e));
  } finally {
    busy.value = false;
  }
}

function toggle(id: string) {
  const i = selected.value.indexOf(id);
  if (i >= 0) selected.value.splice(i, 1);
  else selected.value.push(id);
}

async function openMessage(id: string) {
  try {
    detail.value = await invoke("message", { hash: id });
    threadView.value = null;
  } catch (e) {
    props.onError(String(e));
  }
}

async function openRecord(id: string) {
  try {
    detail.value = await invoke("record", { recordId: id });
    threadView.value = null;
  } catch (e) {
    props.onError(String(e));
  }
}

async function openThread(id: string) {
  try {
    const response = (await invoke("thread", { hash: id })) as { messages: any[] };
    threadView.value = response.messages;
    detail.value = null;
  } catch (e) {
    props.onError(String(e));
  }
}

async function tagSelected() {
  notice.value = "";
  const hashes = selected.value.filter((id) =>
    results.value.some((r) => r.id === id && r.source === "email"),
  );
  if (!hashes.length) {
    notice.value = "Select at least one email message to tag.";
    return;
  }
  const tag = tagName.value.trim();
  if (!tag) {
    notice.value = "Enter a tag name.";
    return;
  }
  try {
    await invoke("research_tag", { hashes, tag });
    notice.value = `Tagged ${hashes.length} message(s) as “${tag}”.`;
    props.onChanged();
  } catch (e) {
    props.onError(String(e));
  }
}

async function exportSelected() {
  notice.value = "";
  const hashes = selected.value;
  if (!hashes.length) {
    notice.value = "Select one or more messages to export.";
    return;
  }
  try {
    const parent = await open({
      directory: true,
      multiple: false,
      title: "Choose a parent folder for the evidence package",
    });
    if (!parent || Array.isArray(parent)) return;
    const stamp = new Date().toISOString().replace(/[-:.]/g, "").slice(0, 15) + "Z";
    const destination = `${parent}/evidence-${stamp}`;
    const response = (await invoke("export_evidence", { hashes, destination })) as {
      messages: number;
    };
    notice.value = `Exported ${response.messages} message(s) to ${destination}`;
    props.onChanged();
  } catch (e) {
    props.onError(String(e));
  }
}
</script>

<template>
  <section>
    <form class="row" @submit.prevent="runSearch">
      <input
        class="grow"
        v-model="query"
        placeholder="Search archived email and Facebook records"
        autocomplete="off"
      />
      <button type="submit" :disabled="busy">{{ busy ? "Searching…" : "Search" }}</button>
    </form>

    <p v-if="total" class="count">{{ total }} results · {{ selected.length }} selected</p>
    <p v-if="notice" class="notice">{{ notice }}</p>

    <div v-if="results.length" class="row">
      <input v-model="tagName" placeholder="Tag name" />
      <button @click="tagSelected">Tag selected</button>
      <button @click="exportSelected">Export selected</button>
    </div>

    <ul class="results">
      <li v-for="item in results" :key="item.source + item.id">
        <input type="checkbox" :checked="selected.includes(item.id)" @change="toggle(item.id)" />
        <span class="badge">{{ item.source }}</span>
        <strong>{{ item.title || item.kind }}</strong>
        <span class="meta">{{ item.actor }} {{ item.date }}</span>
        <p class="snippet">{{ item.snippet }}</p>
        <p class="row-actions">
          <button v-if="item.source === 'email'" @click="openMessage(item.id)">Open</button>
          <button v-if="item.source === 'email'" @click="openThread(item.id)">Thread</button>
          <button v-else @click="openRecord(item.id)">Open</button>
        </p>
      </li>
    </ul>

    <section v-if="detail" class="detail">
      <h2>{{ detail.subject || detail.source_key }}</h2>
      <p class="meta">{{ detail.sender || detail.actor }} {{ detail.date || detail.occurred_at }}</p>
      <div v-if="detail.attachments?.length" class="attachments">
        <h3>Attachments (indexed metadata)</h3>
        <ul>
          <li v-for="(a, i) in detail.attachments" :key="i">
            {{ a.filename }} · {{ a.mime }} · {{ a.characters }} indexed characters
          </li>
        </ul>
      </div>
      <pre class="body">{{ detail.body }}</pre>
      <details v-if="detail.original_json">
        <summary>Original record JSON</summary>
        <pre class="json">{{ detail.original_json }}</pre>
      </details>
    </section>

    <section v-if="threadView" class="detail">
      <h2>Conversation</h2>
      <div v-for="m in threadView" :key="m.hash" class="thread-message">
        <p class="meta">{{ m.sender }} {{ m.date }}</p>
        <p class="title">{{ m.subject }}</p>
        <pre class="body">{{ m.body }}</pre>
      </div>
    </section>
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
}
input:not([type="checkbox"]) {
  width: 100%;
}
button {
  padding: 8px 16px;
}
.count,
.notice {
  color: #444;
}
.results {
  list-style: none;
  padding: 0;
}
.results li {
  border-top: 1px solid #e0e0e0;
  padding: 12px 0;
}
.badge {
  display: inline-block;
  padding: 2px 8px;
  margin: 0 8px;
  border-radius: 999px;
  background: #eef1f6;
  font-size: 12px;
}
.meta {
  color: #777;
  margin-left: 8px;
  font-size: 12px;
}
.snippet {
  margin: 6px 0 0;
  color: #333;
  white-space: pre-wrap;
}
.row-actions {
  margin: 6px 0 0;
}
.detail {
  border-top: 2px solid #ccc;
  margin-top: 20px;
  padding-top: 12px;
}
.attachments {
  margin-bottom: 12px;
}
.attachments ul {
  margin: 4px 0 0;
  padding-left: 20px;
}
.body {
  white-space: pre-wrap;
  font-family: system-ui, sans-serif;
  color: #222;
  background: #f7f7f7;
  padding: 12px;
  border-radius: 4px;
}
.json {
  white-space: pre-wrap;
  font-size: 12px;
}
.thread-message {
  border-top: 1px solid #e0e0e0;
  padding: 10px 0;
}
.title {
  font-weight: 600;
}
</style>
