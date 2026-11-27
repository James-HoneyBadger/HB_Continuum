<script setup lang="ts">
import { computed, ref } from "vue";
import { invoke } from "@tauri-apps/api/core";
import QueryGroup from "./QueryGroup.vue";

const props = defineProps<{ onError: (message: string) => void; onChanged: () => void }>();

interface Rule {
  type: "rule";
  kind: string;
  value?: string;
  values?: string[];
  mode?: string;
  after?: number | null;
  before?: number | null;
}
interface Group {
  type: "group";
  op: "and" | "or" | "not";
  children: QueryNode[];
}
type QueryNode = Rule | Group;

interface ResultItem {
  source: string;
  id: string;
  kind: string;
  title: string;
  actor: string;
  date: string;
  snippet: string;
}
interface Result {
  items: ResultItem[];
  total: number;
  offset: number;
  limit: number;
  has_more: boolean;
  mode: string;
  definitions: string[];
}

function rootQuery(): Group {
  return {
    type: "group",
    op: "and",
    children: [{ type: "rule", kind: "text", value: "" }],
  };
}

const tree = ref<Group>(rootQuery());
const sourceScope = ref<"both" | "email" | "facebook">("both");
const limit = ref(100);
const offset = ref(0);
const result = ref<Result | null>(null);
const queryError = ref("");
const loading = ref(false);

const sources = computed(() =>
  sourceScope.value === "both" ? ["email", "facebook"] : [sourceScope.value],
);

function payload(node: QueryNode): Record<string, unknown> {
  if (node.type === "group") {
    return {
      type: "group",
      op: node.op,
      children: node.children.map(payload),
    };
  }
  if (node.kind === "text") {
    return { type: "rule", kind: "text", value: node.value ?? "" };
  }
  if (node.kind === "date") {
    return {
      type: "rule",
      kind: "date",
      after: node.after ?? null,
      before: node.before ?? null,
    };
  }
  const body: Record<string, unknown> = {
    type: "rule",
    kind: node.kind,
    values: node.values ?? [],
  };
  if (node.kind === "tag") body.mode = node.mode ?? "any";
  return body;
}

function validationMessage(node: QueryNode): string {
  if (node.type === "group") {
    if (!node.children.length) return "Every group needs at least one child.";
    if (node.op === "not" && node.children.length !== 1)
      return "A NOT group takes exactly one child.";
    for (const child of node.children) {
      const message = validationMessage(child);
      if (message) return message;
    }
    return "";
  }
  if (node.kind === "text" && !(node.value ?? "").trim())
    return "Enter a text expression, or remove the empty text rule.";
  if (["actor", "kind", "source", "tag"].includes(node.kind)
      && !(node.values ?? []).length)
    return `Select at least one ${node.kind} value.`;
  if (node.kind === "date" && !node.after && !node.before)
    return "A date rule needs a From or To date.";
  return "";
}

async function run(nextOffset = 0) {
  queryError.value = "";
  const message = validationMessage(tree.value);
  if (message) {
    queryError.value = message;
    return;
  }
  loading.value = true;
  try {
    offset.value = nextOffset;
    result.value = (await invoke("searchAdvanced", {
      query: payload(tree.value),
      sources: sources.value,
      limit: limit.value,
      offset: offset.value,
    })) as Result;
  } catch (e) {
    result.value = null;
    queryError.value = String(e);
    props.onError(String(e));
  } finally {
    loading.value = false;
  }
}

function reset() {
  tree.value = rootQuery();
  result.value = null;
  queryError.value = "";
  offset.value = 0;
}

function page(direction: -1 | 1) {
  if (!result.value) return;
  const next = Math.max(0, offset.value + direction * limit.value);
  void run(next);
}
</script>

<template>
  <section class="advanced">
    <header class="toolbar">
      <div>
        <h2>Advanced query</h2>
        <p class="hint">
          Nested boolean groups over stored records. Every rule is evaluated as a set;
          NOT excludes its child from the selected sources. Text rules use FTS5 syntax.
        </p>
      </div>
      <div class="controls">
        <label>
          Sources
          <select v-model="sourceScope">
            <option value="both">email + catalog</option>
            <option value="email">email only</option>
            <option value="facebook">catalog only</option>
          </select>
        </label>
        <label>
          Page size
          <select v-model.number="limit">
            <option :value="25">25</option>
            <option :value="50">50</option>
            <option :value="100">100</option>
            <option :value="250">250</option>
          </select>
        </label>
        <button type="button" :disabled="loading" @click="run(0)">
          {{ loading ? "Searching…" : "Search" }}
        </button>
        <button type="button" :disabled="loading" @click="reset">Clear</button>
      </div>
    </header>

    <QueryGroup :node="tree" :depth="0" />

    <p v-if="queryError" class="error" role="alert">{{ queryError }}</p>

    <div v-if="result" class="summary">
      <span>
        {{ result.total.toLocaleString() }} matching records
        <template v-if="result.items.length">
          · showing {{ result.offset + 1 }}–{{ result.offset + result.items.length }}
        </template>
      </span>
      <div class="pager">
        <button type="button" :disabled="loading || result.offset === 0" @click="page(-1)">
          Previous
        </button>
        <button type="button" :disabled="loading || !result.has_more" @click="page(1)">
          Next
        </button>
      </div>
    </div>

    <ol v-if="result && result.items.length" class="results">
      <li v-for="item in result.items" :key="`${item.source}-${item.id}`">
        <div class="result-head">
          <span class="badge">{{ item.source === "facebook" ? "catalog" : item.source }}</span>
          <span class="badge kind">{{ item.kind }}</span>
          <strong>{{ item.title || "Untitled" }}</strong>
        </div>
        <div class="result-meta">
          <span v-if="item.actor">{{ item.actor }}</span>
          <span v-if="item.date">{{ item.date }}</span>
        </div>
        <p v-if="item.snippet" class="snippet">{{ item.snippet }}</p>
      </li>
    </ol>
    <p v-else-if="result" class="hint">No records match this query.</p>

    <details v-if="result" class="definitions">
      <summary>What these results mean</summary>
      <ul>
        <li v-for="line in result.definitions" :key="line">{{ line }}</li>
      </ul>
    </details>
  </section>
</template>

<style scoped>
.advanced {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  overflow: auto;
}
.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
h2 {
  margin: 0 0 4px;
  font-size: 15px;
  font-weight: 600;
}
.hint {
  margin: 0;
  color: var(--hb-text-secondary);
  font-size: 12px;
  max-width: 620px;
}
.controls {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 8px;
}
label {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 11px;
  color: var(--hb-text-secondary);
}
select,
button {
  padding: 4px 8px;
  border: 1px solid var(--hb-border-strong);
  border-radius: var(--hb-radius);
  background: var(--hb-toolbar);
  color: var(--hb-text);
  font-size: 12px;
}
button {
  cursor: pointer;
}
button:disabled {
  cursor: default;
  opacity: 0.6;
}
.error {
  margin: 0;
  color: var(--hb-error-text);
  font-size: 12px;
}
.summary {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 12px;
  color: var(--hb-text-secondary);
}
.pager {
  display: flex;
  gap: 6px;
}
.results {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.results li {
  border: 1px solid var(--hb-border);
  border-radius: var(--hb-radius);
  background: var(--hb-panel-alt);
  padding: 8px 10px;
}
.result-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}
.badge {
  text-transform: uppercase;
  font-size: 9px;
  letter-spacing: 0.04em;
  padding: 1px 5px;
  border: 1px solid var(--hb-border-strong);
  border-radius: var(--hb-radius);
  color: var(--hb-text-secondary);
}
.badge.kind {
  border-style: dashed;
}
.result-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 3px;
  font-size: 11px;
  color: var(--hb-text-secondary);
}
.snippet {
  margin: 6px 0 0;
  font-size: 12px;
  white-space: pre-wrap;
}
.definitions {
  font-size: 12px;
  color: var(--hb-text-secondary);
}
.definitions ul {
  margin: 6px 0 0;
  padding-left: 18px;
}
</style>
