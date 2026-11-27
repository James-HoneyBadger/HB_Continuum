<script setup lang="ts">
import { onMounted, ref } from "vue";
import { invoke } from "@tauri-apps/api/core";
import { save } from "@tauri-apps/plugin-dialog";

const props = defineProps<{ onError: (message: string) => void; onChanged: () => void }>();

interface CollectionSummary {
  id: number;
  workspace: string;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
  item_count: number;
}
interface CollectionItem {
  item_type: string;
  item_id: string;
  note: string;
  added_at: string;
  title: string;
  actor: string;
  date: string;
  kind: string;
  exists: boolean;
}
interface Collection extends CollectionSummary {
  item_count: number;
  items: CollectionItem[];
}

const workspaces = ref<string[]>([]);
const collections = ref<CollectionSummary[]>([]);
const current = ref<Collection | null>(null);
const draft = ref({ workspace: "General", name: "", description: "" });
const addition = ref({ itemType: "email", itemId: "", note: "" });
const notice = ref("");
const busy = ref(false);
const confirmingDelete = ref(false);

async function load() {
  try {
    const [workspaceResponse, collectionResponse] = await Promise.all([
      invoke("research_list", { table: "workspaces" }) as Promise<{ rows: any[][] }>,
      invoke("collections_list") as Promise<{ collections: CollectionSummary[] }>,
    ]);
    workspaces.value = workspaceResponse.rows.map((row) => String(row[0]));
    collections.value = collectionResponse.collections;
    if (!workspaces.value.includes(draft.value.workspace) && workspaces.value.length) {
      draft.value.workspace = workspaces.value[0];
    }
  } catch (e) {
    props.onError(String(e));
  }
}

async function open(collection: CollectionSummary) {
  try {
    current.value = (await invoke("collection_get", {
      collectionId: collection.id,
    })) as Collection;
    confirmingDelete.value = false;
    notice.value = "";
  } catch (e) {
    props.onError(String(e));
  }
}

async function create() {
  busy.value = true;
  notice.value = "";
  try {
    const created = (await invoke("collection_create", {
      workspace: draft.value.workspace,
      name: draft.value.name,
      description: draft.value.description,
    })) as Collection;
    notice.value = `Collection “${created.name}” created.`;
    draft.value.name = "";
    draft.value.description = "";
    await load();
    await open(created);
    props.onChanged();
  } catch (e) {
    props.onError(String(e));
  } finally {
    busy.value = false;
  }
}

async function addItem() {
  if (!current.value) return;
  busy.value = true;
  notice.value = "";
  try {
    current.value = (await invoke("collection_add", {
      collectionId: current.value.id,
      itemType: addition.value.itemType,
      itemId: addition.value.itemId.trim(),
      note: addition.value.note || null,
    })) as Collection;
    notice.value = "Record added.";
    addition.value.itemId = "";
    addition.value.note = "";
    await load();
    props.onChanged();
  } catch (e) {
    props.onError(String(e));
  } finally {
    busy.value = false;
  }
}

async function removeItem(item: CollectionItem) {
  if (!current.value) return;
  busy.value = true;
  try {
    current.value = (await invoke("collection_remove", {
      collectionId: current.value.id,
      itemType: item.item_type,
      itemId: item.item_id,
    })) as Collection;
    await load();
    props.onChanged();
  } catch (e) {
    props.onError(String(e));
  } finally {
    busy.value = false;
  }
}

async function deleteCollection() {
  if (!current.value) return;
  if (!confirmingDelete.value) {
    confirmingDelete.value = true;
    return;
  }
  busy.value = true;
  try {
    await invoke("collection_delete", { collectionId: current.value.id });
    current.value = null;
    confirmingDelete.value = false;
    notice.value = "Collection deleted. Referenced records were not affected.";
    await load();
    props.onChanged();
  } catch (e) {
    props.onError(String(e));
  } finally {
    busy.value = false;
  }
}

async function exportManifest() {
  if (!current.value) return;
  busy.value = true;
  try {
    const destination = await save({
      title: "Save evidence manifest",
      defaultPath: `evidence-${current.value.id}.md`,
      filters: [
        { name: "Markdown", extensions: ["md"] },
        { name: "JSON", extensions: ["json"] },
      ],
    });
    if (!destination) return;
    const format = destination.toLowerCase().endsWith(".json") ? "json" : "markdown";
    const result = (await invoke("collection_export", {
      collectionId: current.value.id,
      destination,
      format,
    })) as { path: string; bytes: number };
    notice.value = `Manifest written to ${result.path} (${result.bytes} bytes).`;
  } catch (e) {
    props.onError(String(e));
  } finally {
    busy.value = false;
  }
}

onMounted(load);
</script>

<template>
  <section class="collections">
    <p class="banner">
      Collections reference preserved records; they never copy, edit or delete originals. A manifest
      lists stable identifiers, notes and any item that has gone missing.
    </p>

    <div class="layout">
      <aside class="side">
        <h2>Collections</h2>
        <ul>
          <li v-for="collection in collections" :key="collection.id">
            <button
              :class="['entry', { active: current?.id === collection.id }]"
              @click="open(collection)"
            >
              <span class="name">{{ collection.name }}</span>
              <span class="meta">{{ collection.workspace }} · {{ collection.item_count }} items</span>
            </button>
          </li>
        </ul>
        <p v-if="!collections.length" class="meta">No collections yet.</p>

        <h2>New collection</h2>
        <label class="field">
          Workspace
          <select v-model="draft.workspace">
            <option v-for="workspace in workspaces" :key="workspace" :value="workspace">
              {{ workspace }}
            </option>
          </select>
        </label>
        <label class="field">
          Name
          <input v-model="draft.name" maxlength="100" />
        </label>
        <label class="field">
          Description
          <input v-model="draft.description" maxlength="4000" />
        </label>
        <button :disabled="busy || !draft.name.trim()" @click="create">Create</button>
      </aside>

      <div class="main">
        <template v-if="current">
          <div class="row">
            <h2>{{ current.name }}</h2>
            <button :disabled="busy" @click="exportManifest">Export manifest…</button>
            <button class="danger" :disabled="busy" @click="deleteCollection">
              {{ confirmingDelete ? "Confirm delete" : "Delete collection" }}
            </button>
            <button v-if="confirmingDelete" @click="confirmingDelete = false">Keep</button>
          </div>
          <p v-if="confirmingDelete" class="meta">
            Deleting a collection removes the collection and its notes. Referenced archived records
            and their originals are not affected.
          </p>
          <p class="meta">{{ current.workspace }} · {{ current.item_count }} items · {{ current.description }}</p>
          <p v-if="notice" class="notice">{{ notice }}</p>

          <h3>Add a record</h3>
          <div class="row add">
            <label class="field">
              Type
              <select v-model="addition.itemType">
                <option value="email">Archived email (SHA-256)</option>
                <option value="catalog">Catalog record id</option>
              </select>
            </label>
            <label class="field grow">
              Identifier
              <input v-model="addition.itemId" spellcheck="false" />
            </label>
            <label class="field grow">
              Note (optional)
              <input v-model="addition.note" maxlength="2000" />
            </label>
            <button :disabled="busy || !addition.itemId.trim()" @click="addItem">Add</button>
          </div>
          <p class="meta">
            Identifiers come from search results or the record reader. Adding the same record again
            updates its note rather than duplicating it.
          </p>

          <h3>Items</h3>
          <table v-if="current.items.length" class="items">
            <thead>
              <tr>
                <th>Type</th>
                <th>Title</th>
                <th>Actor</th>
                <th>Date</th>
                <th>Note</th>
                <th>Identifier</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in current.items" :key="item.item_type + item.item_id">
                <td>{{ item.kind || item.item_type }}</td>
                <td>
                  {{ item.title || "(missing record)" }}
                  <span v-if="!item.exists" class="bad">missing</span>
                </td>
                <td>{{ item.actor }}</td>
                <td>{{ item.date }}</td>
                <td>{{ item.note || "—" }}</td>
                <td class="id" :title="item.item_id">{{ item.item_id }}</td>
                <td><button :disabled="busy" @click="removeItem(item)">Remove</button></td>
              </tr>
            </tbody>
          </table>
          <p v-else class="meta">No records in this collection yet.</p>
        </template>
        <p v-else class="meta">Select a collection or create one.</p>
      </div>
    </div>
  </section>
</template>

<style scoped>
.collections {
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
.layout {
  display: flex;
  gap: 18px;
  align-items: flex-start;
}
.side {
  width: 280px;
  flex-shrink: 0;
}
.main {
  flex: 1;
  min-width: 0;
}
h2 {
  font-size: 14px;
  margin: 0 0 8px;
}
h3 {
  font-size: 13px;
  margin: 14px 0 6px;
}
ul {
  list-style: none;
  margin: 0 0 12px;
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
.name {
  font-weight: 600;
}
.row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: flex-end;
  margin-bottom: 8px;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 3px;
  font-size: 12px;
  color: var(--hb-text-secondary);
  margin-bottom: 8px;
}
.field.grow {
  flex: 1;
  min-width: 160px;
}
.field input,
.field select {
  padding: 5px 7px;
  border: 1px solid var(--hb-border);
  background: var(--hb-workspace);
  color: var(--hb-text);
  border-radius: var(--hb-radius);
}
.add {
  align-items: flex-end;
}
.meta {
  color: var(--hb-text-secondary);
  font-size: 12px;
  margin: 0 0 6px;
}
.notice {
  color: var(--hb-success-text);
  font-size: 12px;
}
.bad {
  color: var(--hb-error-text);
  font-size: 11px;
  margin-left: 4px;
}
.danger {
  border-color: var(--hb-error);
  color: var(--hb-error-text);
}
table.items {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
table.items th,
table.items td {
  text-align: left;
  padding: 4px 6px;
  border-bottom: 1px solid var(--hb-border);
}
table.items th {
  color: var(--hb-text-secondary);
  font-weight: 600;
}
td.id {
  font-family: var(--hb-font-mono);
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
@media (max-width: 900px) {
  .layout {
    flex-direction: column;
  }
  .side {
    width: 100%;
  }
}
</style>
