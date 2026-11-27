<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { invoke } from "@tauri-apps/api/core";

const props = defineProps<{ onError: (message: string) => void; onChanged: () => void }>();

interface TimelineRow {
  hash: string;
  subject: string;
  sender: string;
  date: string;
}

interface Correspondent {
  sender: string;
  count: number;
}

const senders = ref<Correspondent[]>([]);
const rows = ref<TimelineRow[]>([]);
const selectedSender = ref<string | null>(null);
const detail = ref<any>(null);
const loading = ref(false);
const pageSize = 100;
const offset = ref(0);
const order = ref<"asc" | "desc">("asc");
const fromDate = ref("");
const toDate = ref("");
const canPrev = computed(() => offset.value > 0);
const canNext = computed(() => rows.value.length === pageSize);

async function refresh() {
  loading.value = true;
  try {
    const sender = selectedSender.value ?? undefined;
    const after = fromDate.value
      ? Math.floor(new Date(`${fromDate.value}T00:00:00Z`).getTime() / 1000)
      : undefined;
    const before = toDate.value
      ? Math.floor(new Date(`${toDate.value}T00:00:00Z`).getTime() / 1000) + 86400
      : undefined;
    const [senderList, timeline] = await Promise.all([
      invoke("correspondents", { limit: 100 }) as Promise<Correspondent[]>,
      invoke("timeline", {
        sender,
        limit: pageSize,
        offset: offset.value,
        order: order.value,
        after,
        before,
      }) as Promise<TimelineRow[]>,
    ]);
    senders.value = senderList;
    rows.value = timeline;
  } catch (e) {
    props.onError(String(e));
  } finally {
    loading.value = false;
  }
}

function filter(sender: string | null) {
  selectedSender.value = sender;
  offset.value = 0;
  detail.value = null;
  void refresh();
}

function turn(direction: -1 | 1) {
  offset.value = Math.max(0, offset.value + direction * pageSize);
  detail.value = null;
  void refresh();
}

function applyRange() {
  offset.value = 0;
  detail.value = null;
  void refresh();
}

function clearRange() {
  fromDate.value = "";
  toDate.value = "";
  applyRange();
}

function setOrder(next: "asc" | "desc") {
  order.value = next;
  offset.value = 0;
  detail.value = null;
  void refresh();
}

async function open(row: TimelineRow) {
  try {
    detail.value = await invoke("message", { hash: row.hash });
  } catch (e) {
    props.onError(String(e));
  }
}

onMounted(refresh);
</script>

<template>
  <section class="view">
    <div class="row">
      <button :disabled="loading" @click="refresh">Refresh</button>
      <button :disabled="loading" @click="setOrder(order === 'asc' ? 'desc' : 'asc')">
        {{ order === "asc" ? "Oldest first" : "Newest first" }}
      </button>
      <button :disabled="loading || !canPrev" @click="turn(-1)">Previous</button>
      <button :disabled="loading || !canNext" @click="turn(1)">Next</button>
      <label class="range">
        From
        <input v-model="fromDate" type="date" @change="applyRange" />
      </label>
      <label class="range">
        To
        <input v-model="toDate" type="date" @change="applyRange" />
      </label>
      <button v-if="fromDate || toDate" @click="clearRange">Clear range</button>
      <span v-if="selectedSender" class="meta">
        Filtered to {{ selectedSender }}
        <button class="link" @click="filter(null)">Show all</button>
      </span>
      <span v-else class="meta">
        {{ rows.length }} messages from position {{ offset + 1 }},
        {{ fromDate || toDate ? "filtered by date" : "undated last" }}
      </span>
    </div>

    <div class="panes">
      <aside class="senders">
        <h3>Correspondents</h3>
        <ul>
          <li>
            <button :class="{ active: !selectedSender }" @click="filter(null)">All senders</button>
          </li>
          <li v-for="c in senders" :key="c.sender">
            <button
              :class="{ active: selectedSender === c.sender }"
              :title="c.sender"
              @click="filter(c.sender)"
            >
              <span class="name">{{ c.sender || "(unknown)" }}</span>
              <span class="count">{{ c.count }}</span>
            </button>
          </li>
        </ul>
      </aside>

      <div class="timeline">
        <h3>Timeline</h3>
        <ul>
          <li v-for="r in rows" :key="r.hash">
            <button class="entry" @click="open(r)">
              <span class="date">{{ r.date || "undated" }}</span>
              <span class="subject">{{ r.subject || "(no subject)" }}</span>
              <span class="sender">{{ r.sender }}</span>
            </button>
          </li>
        </ul>
        <p v-if="!rows.length && !loading" class="meta">No messages in this archive.</p>
      </div>
    </div>

    <section v-if="detail" class="detail">
      <h3>{{ detail.subject || "(no subject)" }}</h3>
      <p class="meta">{{ detail.sender }} {{ detail.date }}</p>
      <pre class="body">{{ detail.body }}</pre>
    </section>
  </section>
</template>

<style scoped>
.row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
  align-items: center;
}
.range {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--hb-text-secondary);
}
.range input {
  padding: 4px 6px;
  border: 1px solid var(--hb-border);
  background: var(--hb-workspace);
}
.panes {
  display: flex;
  gap: 16px;
  align-items: flex-start;
}
.senders {
  width: 240px;
  flex-shrink: 0;
}
h3 {
  font-size: 14px;
  margin: 0 0 8px;
}
ul {
  list-style: none;
  margin: 0;
  padding: 0;
}
.senders li {
  margin-bottom: 4px;
}
.senders button {
  width: 100%;
  display: flex;
  justify-content: space-between;
  gap: 8px;
  padding: 6px 8px;
  background: transparent;
  border: 1px solid transparent;
  text-align: left;
  cursor: pointer;
}
.senders button.active {
  border-color: var(--hb-border-strong);
  background: var(--hb-panel-alt);
}
.name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.count {
  color: var(--hb-text-secondary);
  font-size: 12px;
}
.timeline {
  flex: 1;
  min-width: 0;
}
.entry {
  width: 100%;
  display: flex;
  gap: 12px;
  padding: 6px 8px;
  background: transparent;
  border: none;
  border-bottom: 1px solid var(--hb-border);
  text-align: left;
  cursor: pointer;
  font-size: 13px;
}
.entry:hover {
  background: var(--hb-panel-alt);
}
.date {
  width: 190px;
  color: var(--hb-text-secondary);
  flex-shrink: 0;
}
.subject {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sender {
  color: var(--hb-text-secondary);
  width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.detail {
  margin-top: 16px;
}
.body {
  background: var(--hb-panel-alt);
  padding: 10px;
  white-space: pre-wrap;
}
.meta {
  color: var(--hb-text-secondary);
  font-size: 13px;
}
.link {
  border: none;
  background: transparent;
  color: var(--hb-link);
  cursor: pointer;
  padding: 0 4px;
  text-decoration: underline;
}
</style>
