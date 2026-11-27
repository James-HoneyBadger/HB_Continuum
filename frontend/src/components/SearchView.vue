<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
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
const page = ref(1);
const pageSize = 50;
const hasMore = ref(false);
const fromDate = ref("");
const toDate = ref("");
const sourceEmail = ref(true);
const sourceFacebook = ref(true);
const sendersText = ref("");
const kind = ref("");
const tagsText = ref("");
const totalIsExact = ref(true);
const capped = ref(false);
const validationError = ref("");
const humanQuery = computed(() => {
  const parts: string[] = [];
  if (query.value.trim()) parts.push(`text "${query.value.trim()}"`);
  const chosen = [
    sourceEmail.value ? "email" : null,
    sourceFacebook.value ? "Facebook" : null,
  ].filter((value): value is string => value !== null);
  parts.push(chosen.length ? `in ${chosen.join(" and ")}` : "no source selected");
  if (sendersText.value.trim()) parts.push(`sender/actor ${sendersText.value.trim()}`);
  if (kind.value) parts.push(`kind ${kind.value}`);
  if (tagsText.value.trim()) parts.push(`tagged ${tagsText.value.trim()}`);
  if (fromDate.value || toDate.value) {
    parts.push(`dated ${fromDate.value || "..."} to ${toDate.value || "..."}`);
  }
  return parts.join(" · ");
});
const collections = ref<{ id: number; workspace: string; name: string }[]>([]);
const collectionId = ref<number | null>(null);
const collectionNote = ref("");

async function loadCollections() {
  try {
    const response = (await invoke("collections_list")) as {
      collections: { id: number; workspace: string; name: string }[];
    };
    collections.value = response.collections;
  } catch (e) {
    props.onError(String(e));
  }
}

async function addSelectedToCollection() {
  notice.value = "";
  if (!collectionId.value) {
    notice.value = "Choose a collection first.";
    return;
  }
  if (!selected.value.length) {
    notice.value = "Select one or more results first.";
    return;
  }
  const targets = results.value.filter((item) => selected.value.includes(item.id));
  try {
    for (const item of targets) {
      await invoke("collection_add", {
        collectionId: collectionId.value,
        itemType: item.source === "email" ? "email" : "catalog",
        itemId: item.id,
        note: collectionNote.value || null,
      });
    }
    notice.value = `Added ${targets.length} record(s) to the selected collection.`;
    collectionNote.value = "";
    props.onChanged();
  } catch (e) {
    props.onError(String(e));
  }
}
const detail = ref<any>(null);
const threadView = ref<any[] | null>(null);
const selected = ref<string[]>([]);
const tagName = ref("");
const notice = ref("");

function splitList(value: string): string[] | undefined {
  const items = value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  return items.length ? items : undefined;
}

async function runSearch(target = 1) {
  notice.value = "";
  const sources = [
    sourceEmail.value ? "email" : null,
    sourceFacebook.value ? "facebook" : null,
  ].filter((value): value is string => value !== null);
  if (!sources.length) {
    notice.value = "Choose at least one source.";
    return;
  }
  validationError.value = "";
  try {
    const validation = (await invoke("search_validate", {
      query: query.value,
    })) as { valid: boolean; message: string };
    if (!validation.valid) {
      validationError.value = validation.message;
      return;
    }
  } catch (e) {
    props.onError(String(e));
    return;
  }
  busy.value = true;
  try {
    const after = fromDate.value
      ? Math.floor(new Date(`${fromDate.value}T00:00:00Z`).getTime() / 1000)
      : undefined;
    const before = toDate.value
      ? Math.floor(new Date(`${toDate.value}T00:00:00Z`).getTime() / 1000) + 86400
      : undefined;
    const response = (await invoke("search", {
      query: query.value,
      sources,
      page: target,
      pageSize,
      after,
      before,
      senders: splitList(sendersText.value),
      kinds: kind.value ? [kind.value] : undefined,
      tags: splitList(tagsText.value),
    })) as {
      items: ResultItem[];
      total: number;
      has_more: boolean;
      total_is_exact: boolean;
      capped: boolean;
    };
    results.value = response.items;
    total.value = response.total;
    hasMore.value = response.has_more;
    totalIsExact.value = response.total_is_exact;
    capped.value = response.capped;
    page.value = target;
    selected.value = [];
    detail.value = null;
    threadView.value = null;
  } catch (e) {
    props.onError(String(e));
  } finally {
    busy.value = false;
  }
}

onMounted(loadCollections);

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
    <form class="row" @submit.prevent="runSearch(1)">
      <input
        class="grow"
        v-model="query"
        placeholder="Search archived email and Facebook records"
        autocomplete="off"
      />
      <label class="range">
        From
        <input v-model="fromDate" type="date" />
      </label>
      <label class="range">
        To
        <input v-model="toDate" type="date" />
      </label>
      <button type="submit" :disabled="busy">{{ busy ? "Searching…" : "Search" }}</button>
    </form>

    <div class="row filters">
      <label class="check"><input v-model="sourceEmail" type="checkbox" /> Email</label>
      <label class="check"><input v-model="sourceFacebook" type="checkbox" /> Facebook</label>
      <label class="range">
        Sender/actor
        <input v-model="sendersText" placeholder="exact, comma-separated" />
      </label>
      <label class="range">
        Kind
        <select v-model="kind">
          <option value="">Any kind</option>
          <option value="message">Message</option>
          <option value="post">Post</option>
          <option value="comment">Comment</option>
          <option value="event">Event</option>
          <option value="media">Media</option>
          <option value="reaction">Reaction</option>
        </select>
      </label>
      <label class="range">
        Tags
        <input v-model="tagsText" placeholder="any of, comma-separated" />
      </label>
    </div>

    <p class="query-summary">{{ humanQuery }}</p>
    <p v-if="validationError" class="error" role="alert">{{ validationError }}</p>
    <details class="syntax">
      <summary>Query syntax</summary>
      <ul>
        <li>Quotes match an exact phrase: <code>"silver invoice"</code>.</li>
        <li>A trailing asterisk matches a prefix: <code>invoice*</code>.</li>
        <li>Uppercase <code>AND</code>, <code>OR</code> and <code>NOT</code> combine terms.</li>
        <li>Parentheses group expressions; <code>NEAR(a b, 5)</code> finds nearby terms.</li>
        <li>Filters above are applied in addition to the text expression.</li>
      </ul>
    </details>

    <p v-if="total !== null && query" class="count">
      {{ total }} results<span v-if="!totalIsExact"> (at least)</span> · page {{ page }} ·
      {{ selected.length }} selected
      <span v-if="capped"> · listing limited to the first 5000 matches; refine the query</span>
    </p>
    <div v-if="query && (page > 1 || hasMore)" class="row">
      <button :disabled="busy || page <= 1" @click="runSearch(page - 1)">Previous</button>
      <button :disabled="busy || !hasMore" @click="runSearch(page + 1)">Next</button>
    </div>
    <p v-if="notice" class="notice">{{ notice }}</p>

    <div v-if="results.length" class="row">
      <input v-model="tagName" placeholder="Tag name" />
      <button @click="tagSelected">Tag selected</button>
      <button @click="exportSelected">Export selected</button>
    </div>

    <div v-if="results.length" class="row">
      <select v-model="collectionId">
        <option :value="null">Choose collection…</option>
        <option v-for="collection in collections" :key="collection.id" :value="collection.id">
          {{ collection.workspace }} / {{ collection.name }}
        </option>
      </select>
      <input v-model="collectionNote" placeholder="Collection note (optional)" maxlength="2000" />
      <button :disabled="!collectionId || !selected.length" @click="addSelectedToCollection">
        Add selected to collection
      </button>
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
.range {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--hb-text-secondary);
}
.range input,
.range select {
  padding: 4px 6px;
  border: 1px solid var(--hb-border);
  background: var(--hb-workspace);
  border-radius: var(--hb-radius);
}
.filters {
  align-items: center;
  gap: 14px;
}
.check {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--hb-text-secondary);
}
.query-summary {
  font-size: 12px;
  color: var(--hb-text-secondary);
  margin: 0 0 8px;
}
.error {
  color: var(--hb-error-text);
  font-size: 12px;
  margin: 0 0 8px;
}
.syntax {
  font-size: 12px;
  color: var(--hb-text-secondary);
  margin-bottom: 8px;
}
.syntax summary {
  cursor: pointer;
}
.syntax ul {
  margin: 4px 0 0;
  padding-left: 18px;
}
.syntax code {
  font-family: var(--hb-font-mono);
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
  color: var(--hb-text-secondary);
}
.results {
  list-style: none;
  padding: 0;
}
.results li {
  border-top: 1px solid var(--hb-border);
  padding: 12px 0;
}
.badge {
  display: inline-block;
  padding: 2px 8px;
  margin: 0 8px;
  border-radius: 999px;
  background: var(--hb-selection);
  font-size: 12px;
}
.meta {
  color: var(--hb-text-secondary);
  margin-left: 8px;
  font-size: 12px;
}
.snippet {
  margin: 6px 0 0;
  color: var(--hb-text);
  white-space: pre-wrap;
}
.row-actions {
  margin: 6px 0 0;
}
.detail {
  border-top: 2px solid var(--hb-border-strong);
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
  color: var(--hb-text);
  background: var(--hb-panel-alt);
  padding: 12px;
  border-radius: 4px;
}
.json {
  white-space: pre-wrap;
  font-size: 12px;
}
.thread-message {
  border-top: 1px solid var(--hb-border);
  padding: 10px 0;
}
.title {
  font-weight: 600;
}
</style>
