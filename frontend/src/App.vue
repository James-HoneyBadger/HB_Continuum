<script setup lang="ts">
import { onMounted, ref } from "vue";
import { invoke } from "@tauri-apps/api/core";

interface ArchiveStats {
  messages: number;
  origins: number;
}

interface CatalogStats {
  files: number;
  records: number;
}

interface Stats {
  archive: ArchiveStats;
  catalog: CatalogStats;
}

interface ResultItem {
  source: string;
  id: string;
  kind: string;
  title: string;
  actor: string;
  date: string;
  snippet: string;
}

const archive = ref("~/.hb-dispatch");
const query = ref("");
const stats = ref<Stats | null>(null);
const results = ref<ResultItem[]>([]);
const total = ref(0);
const error = ref("");
const busy = ref(false);

async function refreshStats() {
  error.value = "";
  try {
    stats.value = (await invoke("stats")) as Stats;
  } catch (e) {
    error.value = String(e);
  }
}

async function applyArchive() {
  try {
    await invoke("set_archive", { path: archive.value });
    await refreshStats();
  } catch (e) {
    error.value = String(e);
  }
}

async function runSearch() {
  busy.value = true;
  error.value = "";
  try {
    const response = (await invoke("search", {
      query: query.value,
      sources: ["email", "facebook"],
      page: 1,
      pageSize: 50,
    })) as { items: ResultItem[]; total: number };
    results.value = response.items;
    total.value = response.total;
  } catch (e) {
    error.value = String(e);
    results.value = [];
    total.value = 0;
  } finally {
    busy.value = false;
  }
}

const detail = ref<any>(null);
const threadView = ref<any[] | null>(null);
const verifyResult = ref<{ checked: number; bad: string[] } | null>(null);

async function openMessage(id: string) {
  error.value = "";
  try {
    detail.value = await invoke("message", { hash: id });
    threadView.value = null;
  } catch (e) {
    error.value = String(e);
  }
}

async function openRecord(id: string) {
  error.value = "";
  try {
    detail.value = await invoke("record", { recordId: id });
    threadView.value = null;
  } catch (e) {
    error.value = String(e);
  }
}

async function openThread(id: string) {
  error.value = "";
  try {
    const response = (await invoke("thread", { hash: id })) as { messages: any[] };
    threadView.value = response.messages;
    detail.value = null;
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

onMounted(refreshStats);
</script>

<template>
  <main class="app">
    <h1>HB Continuum</h1>

    <section class="row">
      <label class="grow">
        Archive
        <input v-model="archive" placeholder="~/.hb-dispatch" />
      </label>
      <button @click="applyArchive">Open</button>
    </section>

    <form class="row" @submit.prevent="runSearch">
      <input
        class="grow"
        v-model="query"
        placeholder="Search archived email and Facebook records"
        autocomplete="off"
      />
      <button type="submit" :disabled="busy">{{ busy ? "Searching…" : "Search" }}</button>
    </form>

    <p class="actions">
      <button @click="runVerify">Verify integrity</button>
    </p>
    <p v-if="verifyResult" class="verify">
      {{ verifyResult.checked }} checked · {{ verifyResult.bad.length }} failed
    </p>

    <p v-if="stats" class="stats">
      {{ stats.archive.messages }} messages · {{ stats.archive.origins }} mailbox origins ·
      {{ stats.catalog.records }} catalog records
    </p>
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="total" class="count">{{ total }} results</p>

    <ul class="results">
      <li v-for="item in results" :key="item.source + item.id">
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
  </main>
</template>

<style scoped>
.app {
  max-width: 900px;
  margin: 0 auto;
  padding: 24px;
  font-family: system-ui, sans-serif;
}
.row {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
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
.stats {
  color: #555;
}
.error {
  color: #b00020;
}
.count {
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
  margin-right: 8px;
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
.actions {
  margin: 8px 0;
}
.verify {
  color: #444;
}
.row-actions {
  margin: 6px 0 0;
}
.detail {
  border-top: 2px solid #ccc;
  margin-top: 20px;
  padding-top: 12px;
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
  color: #333;
}
.thread-message {
  border-top: 1px solid #e0e0e0;
  padding: 10px 0;
}
.title {
  font-weight: 600;
}
</style>
