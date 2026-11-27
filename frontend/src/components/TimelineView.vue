<script setup lang="ts">
import { onMounted, ref } from "vue";
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

async function refresh() {
  loading.value = true;
  try {
    const sender = selectedSender.value ?? undefined;
    const [senderList, timeline] = await Promise.all([
      invoke("correspondents", { limit: 100 }) as Promise<Correspondent[]>,
      invoke("timeline", { sender, limit: 500 }) as Promise<TimelineRow[]>,
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
      <span v-if="selectedSender" class="meta">
        Filtered to {{ selectedSender }}
        <button class="link" @click="filter(null)">Show all</button>
      </span>
      <span v-else class="meta">{{ rows.length }} messages, undated last</span>
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
  gap: 8px;
  margin-bottom: 12px;
  align-items: center;
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
  border-color: #888;
  background: #f2f3f5;
}
.name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.count {
  color: #666;
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
  border-bottom: 1px solid #eee;
  text-align: left;
  cursor: pointer;
  font-size: 13px;
}
.entry:hover {
  background: #f7f7f8;
}
.date {
  width: 190px;
  color: #666;
  flex-shrink: 0;
}
.subject {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sender {
  color: #666;
  width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.detail {
  margin-top: 16px;
}
.body {
  background: #f2f3f5;
  padding: 10px;
  white-space: pre-wrap;
}
.meta {
  color: #666;
  font-size: 13px;
}
.link {
  border: none;
  background: transparent;
  color: #0b5cad;
  cursor: pointer;
  padding: 0 4px;
  text-decoration: underline;
}
</style>
