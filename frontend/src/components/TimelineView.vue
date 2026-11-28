<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from "vue";
import { invoke } from "@tauri-apps/api/core";

const props = defineProps<{ onError: (message: string) => void; onChanged: () => void }>();

interface TimelineRow {
  source: "email" | "document";
  hash: string | null;
  record_id: string | null;
  kind: string;
  subject: string;
  sender: string;
  date: string;
}

interface Correspondent {
  sender: string;
  count: number;
}

interface Collection {
  id: number;
  workspace: string;
  name: string;
}

const senders = ref<Correspondent[]>([]);
const rows = ref<TimelineRow[]>([]);
const selectedSender = ref<string | null>(null);
const detail = ref<any>(null);
const detailPanel = ref<HTMLElement | null>(null);
const collections = ref<Collection[]>([]);
const collectionId = ref<number | null>(null);
const collectionNote = ref("");
const collectionNotice = ref("");
const loading = ref(false);
const pageSize = 100;
const offset = ref(0);
const order = ref<"asc" | "desc">("asc");
const includeDocuments = ref(true);
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
        sources:
          includeDocuments.value && !selectedSender.value ? ["email", "document"] : ["email"],
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
  collectionNotice.value = "";
  try {
    detail.value =
      row.source === "document"
        ? await invoke("record", { recordId: row.record_id })
        : await invoke("message", { hash: row.hash });
    await nextTick();
    detailPanel.value?.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (e) {
    props.onError(String(e));
  }
}

function toggleDocuments() {
  offset.value = 0;
  detail.value = null;
  void refresh();
}

async function loadCollections() {
  try {
    const response = (await invoke("collections_list")) as { collections: Collection[] };
    collections.value = response.collections;
  } catch (e) {
    props.onError(String(e));
  }
}

async function addDetailToCollection() {
  collectionNotice.value = "";
  if (!collectionId.value) {
    collectionNotice.value = "Choose a collection first.";
    return;
  }
  const isDocument = Boolean(detail.value?.record_id);
  if (!detail.value?.hash && !isDocument) {
    collectionNotice.value = "Open a message or document first.";
    return;
  }
  try {
    await invoke("collection_add", {
      collectionId: collectionId.value,
      itemType: isDocument ? "catalog" : "email",
      itemId: isDocument ? detail.value.record_id : detail.value.hash,
      note: collectionNote.value || null,
    });
    collectionNotice.value = `Added this ${isDocument ? "document" : "message"} to the selected collection.`;
    collectionNote.value = "";
    props.onChanged();
  } catch (e) {
    props.onError(String(e));
  }
}

onMounted(() => {
  void refresh();
  void loadCollections();
});
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
      <label class="documents-toggle">
        <input
          v-model="includeDocuments"
          type="checkbox"
          :disabled="Boolean(selectedSender)"
          @change="toggleDocuments"
        />
        Include documents
      </label>
      <span v-if="selectedSender" class="meta">
        Filtered to {{ selectedSender }}
        <button class="link" @click="filter(null)">Show all</button>
      </span>
      <span v-if="loading" class="meta">Loading…</span>
      <span v-else class="meta">
        {{ rows.length }} entries from position {{ offset + 1 }},
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
          <li v-for="r in rows" :key="r.source + (r.record_id || r.hash)">
            <button class="entry" @click="open(r)">
              <span class="badge">{{ r.source }}</span>
              <span class="date">{{ r.date || "undated" }}</span>
              <span class="subject">{{ r.subject || (r.source === "document" ? "(unnamed document)" : "(no subject)") }}</span>
              <span class="sender">{{ r.sender }}</span>
            </button>
          </li>
        </ul>
        <p v-if="!rows.length && !loading" class="meta">No entries in this archive.</p>
      </div>
    </div>

    <section v-if="detail" ref="detailPanel" class="detail">
      <h3>{{ detail.subject || detail.source_key || "(no subject)" }}</h3>
      <p class="meta">{{ detail.sender || detail.actor }} {{ detail.date || detail.occurred_at }}</p>
      <div class="row">
        <select v-model="collectionId">
          <option :value="null">Choose collection…</option>
          <option v-for="collection in collections" :key="collection.id" :value="collection.id">
            {{ collection.workspace }} / {{ collection.name }}
          </option>
        </select>
        <input v-model="collectionNote" placeholder="Collection note (optional)" maxlength="2000" />
        <button :disabled="!collectionId" @click="addDetailToCollection">
          Add this item to collection
        </button>
      </div>
      <p v-if="collectionNotice" class="notice">{{ collectionNotice }}</p>
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
.documents-toggle {
  display: flex;
  gap: 4px;
  align-items: center;
  color: var(--hb-text-secondary);
  font-size: 13px;
}
.badge {
  border: 1px solid var(--hb-border);
  border-radius: 4px;
  padding: 0 4px;
  color: var(--hb-text-secondary);
  font-size: 11px;
  text-transform: uppercase;
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
.notice {
  color: var(--hb-success-text);
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
