<script setup lang="ts">
import { onMounted, ref } from "vue";
import { invoke } from "@tauri-apps/api/core";

const props = defineProps<{ onError: (message: string) => void; onChanged: () => void }>();

interface Revision {
  revision: number;
  title: string;
  body: string;
  event_date: string | null;
  recorded_at: string;
}
interface EntrySummary {
  id: number;
  title: string;
  event_date: string | null;
  created_at: string;
  updated_at: string;
  revision: number;
  deleted_at: string | null;
}
interface Entry extends EntrySummary {
  body: string;
  revisions: Revision[];
}

const entries = ref<EntrySummary[]>([]);
const current = ref<Entry | null>(null);
const title = ref("");
const body = ref("");
const eventDate = ref("");
const showDeleted = ref(false);
const confirmingDelete = ref(false);
const viewing = ref<Revision | null>(null);
const notice = ref("");
const busy = ref(false);

async function refresh() {
  try {
    const response = (await invoke("journal_list", {
      limit: 500,
      includeDeleted: showDeleted.value,
    })) as { entries: EntrySummary[] };
    entries.value = response.entries;
  } catch (e) {
    props.onError(String(e));
  }
}

function clearEditor() {
  current.value = null;
  title.value = "";
  body.value = "";
  eventDate.value = "";
  viewing.value = null;
  confirmingDelete.value = false;
  notice.value = "";
}

async function edit(entry: EntrySummary) {
  try {
    const full = (await invoke("journal_get", { entryId: entry.id })) as Entry;
    current.value = full;
    title.value = full.title;
    body.value = full.body;
    eventDate.value = full.event_date ? full.event_date.slice(0, 10) : "";
    viewing.value = null;
    confirmingDelete.value = false;
    notice.value = "";
  } catch (e) {
    props.onError(String(e));
  }
}

async function save() {
  busy.value = true;
  notice.value = "";
  try {
    const saved = (await invoke("journal_save", {
      entryId: current.value?.id ?? null,
      title: title.value,
      body: body.value,
      eventDate: eventDate.value || null,
    })) as Entry;
    notice.value = `Saved revision ${saved.revision}.`;
    current.value = saved;
    await refresh();
    props.onChanged();
  } catch (e) {
    props.onError(String(e));
  } finally {
    busy.value = false;
  }
}

async function remove() {
  if (!current.value) return;
  if (!confirmingDelete.value) {
    confirmingDelete.value = true;
    return;
  }
  busy.value = true;
  try {
    current.value = (await invoke("journal_delete", {
      entryId: current.value.id,
    })) as Entry;
    confirmingDelete.value = false;
    notice.value = "Entry removed from normal views; its revisions are retained.";
    await refresh();
    props.onChanged();
  } catch (e) {
    props.onError(String(e));
  } finally {
    busy.value = false;
  }
}

async function restore() {
  if (!current.value) return;
  busy.value = true;
  try {
    current.value = (await invoke("journal_restore", {
      entryId: current.value.id,
    })) as Entry;
    notice.value = "Entry restored.";
    await refresh();
    props.onChanged();
  } catch (e) {
    props.onError(String(e));
  } finally {
    busy.value = false;
  }
}

onMounted(refresh);
</script>

<template>
  <section class="journal">
    <p class="banner">
      Journal entries are your own retrospective records. They are stored in the research overlay,
      never merged with preserved original evidence, and every edit adds a revision.
    </p>

    <div class="panes">
      <aside class="list">
        <div class="row">
          <button @click="clearEditor">New entry</button>
          <label class="toggle">
            <input v-model="showDeleted" type="checkbox" @change="refresh" />
            Show removed
          </label>
        </div>
        <ul>
          <li v-for="entry in entries" :key="entry.id">
            <button
              :class="['entry', { active: current?.id === entry.id, removed: entry.deleted_at }]"
              @click="edit(entry)"
            >
              <span class="entry-title">{{ entry.title }}</span>
              <span class="meta">
                {{ entry.event_date?.slice(0, 10) || "no event date" }} ·
                rev {{ entry.revision }}
                <template v-if="entry.deleted_at"> · removed</template>
              </span>
            </button>
          </li>
        </ul>
        <p v-if="!entries.length" class="meta">No journal entries yet.</p>
      </aside>

      <div class="editor">
        <div class="row">
          <h2>{{ current ? `Entry ${current.id}` : "New entry" }}</h2>
          <button :disabled="busy" @click="save">Save revision</button>
          <button v-if="current && !current.deleted_at" class="danger" :disabled="busy" @click="remove">
            {{ confirmingDelete ? "Confirm remove" : "Remove" }}
          </button>
          <button v-if="current && current.deleted_at" :disabled="busy" @click="restore">Restore</button>
          <button v-if="confirmingDelete" @click="confirmingDelete = false">Keep entry</button>
        </div>
        <p v-if="confirmingDelete" class="meta">
          Removing hides the entry from normal views. Nothing is destroyed: revisions remain available
          when “Show removed” is enabled, and the entry can be restored.
        </p>
        <p v-if="notice" class="notice">{{ notice }}</p>

        <label class="field">
          Title
          <input v-model="title" maxlength="200" />
        </label>
        <label class="field">
          Event date (optional, when the event happened)
          <input v-model="eventDate" type="date" />
        </label>
        <label class="field grow">
          Entry
          <textarea v-model="body" rows="12"></textarea>
        </label>
        <p class="meta">
          Dates are ISO calendar dates. The recording time is captured separately for each revision.
        </p>

        <section v-if="current" class="history">
          <h3>Revision history</h3>
          <ul>
            <li v-for="revision in current.revisions" :key="revision.revision">
              <button :class="['revision', { active: viewing?.revision === revision.revision }]"
                @click="viewing = revision">
                Revision {{ revision.revision }} · recorded {{ revision.recorded_at }}
              </button>
            </li>
          </ul>
          <div v-if="viewing" class="preview">
            <h4>{{ viewing.title }}</h4>
            <p class="meta">{{ viewing.event_date || "no event date" }}</p>
            <pre>{{ viewing.body }}</pre>
          </div>
        </section>
      </div>
    </div>
  </section>
</template>

<style scoped>
.journal {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.banner {
  margin: 0;
  padding: 8px 10px;
  background: var(--hb-panel-alt);
  border-left: 3px solid var(--hb-info);
  font-size: 12px;
  color: var(--hb-text-secondary);
}
.panes {
  display: flex;
  gap: 16px;
  align-items: flex-start;
}
.list {
  width: 280px;
  flex-shrink: 0;
}
.row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}
.list ul,
.history ul {
  list-style: none;
  margin: 0;
  padding: 0;
}
.entry {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 2px;
  text-align: left;
  background: transparent;
  border: 1px solid transparent;
  padding: 6px 8px;
  cursor: pointer;
}
.entry:hover {
  background: var(--hb-panel-alt);
}
.entry.active {
  background: var(--hb-workspace);
  border-color: var(--hb-border-strong);
}
.entry.removed {
  opacity: 0.6;
}
.entry-title {
  font-weight: 600;
}
.editor {
  flex: 1;
  min-width: 0;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 3px;
  font-size: 12px;
  color: var(--hb-text-secondary);
  margin-bottom: 8px;
}
.field input,
.field textarea {
  padding: 6px 8px;
  border: 1px solid var(--hb-border);
  background: var(--hb-workspace);
  color: var(--hb-text);
  border-radius: var(--hb-radius);
}
.field textarea {
  resize: vertical;
  min-height: 160px;
  font-family: var(--hb-font-mono);
  font-size: 12px;
}
.danger {
  border-color: var(--hb-error);
  color: var(--hb-error-text);
}
.notice {
  color: var(--hb-success-text);
  font-size: 12px;
  margin: 0 0 8px;
}
.meta {
  color: var(--hb-text-secondary);
  font-size: 12px;
  margin: 0;
}
h2 {
  font-size: 14px;
  margin: 0;
  flex: 1;
}
.history {
  margin-top: 12px;
  border-top: 1px solid var(--hb-border);
  padding-top: 10px;
}
.history h3 {
  font-size: 13px;
  margin: 0 0 6px;
}
.revision {
  background: transparent;
  border: 1px solid transparent;
  text-align: left;
  padding: 4px 6px;
  width: 100%;
  cursor: pointer;
  font-size: 12px;
}
.revision.active {
  border-color: var(--hb-border-strong);
  background: var(--hb-panel-alt);
}
.preview {
  margin-top: 8px;
  padding: 8px 10px;
  background: var(--hb-panel-alt);
  border: 1px solid var(--hb-border);
}
.preview h4 {
  margin: 0 0 4px;
  font-size: 13px;
}
.preview pre {
  margin: 6px 0 0;
  white-space: pre-wrap;
  font-family: var(--hb-font-mono);
  font-size: 12px;
}
@media (max-width: 900px) {
  .panes {
    flex-direction: column;
  }
  .list {
    width: 100%;
  }
}
</style>
