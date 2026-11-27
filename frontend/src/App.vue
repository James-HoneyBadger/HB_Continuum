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
      </li>
    </ul>
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
</style>
