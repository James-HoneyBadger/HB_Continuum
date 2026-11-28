<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { invoke } from "@tauri-apps/api/core";

const props = defineProps<{ onError: (message: string) => void; onChanged: () => void }>();

interface GraphNode {
  id: string;
  source: string;
  actor: string;
  messages: number;
  shared_threads: number;
}

interface EdgeExample {
  kind: string;
  id: string;
  title: string;
  date: string;
}

interface GraphEdge {
  source: string;
  target: string;
  source_type: string;
  source_actor: string;
  target_actor: string;
  threads: number;
  messages: number;
  examples: EdgeExample[];
}

interface Graph {
  nodes: GraphNode[];
  edges: GraphEdge[];
  truncated: boolean;
  definitions: string[];
}

const graph = ref<Graph | null>(null);
const loading = ref(false);
const nodeLimit = ref(30);
const edgeLimit = ref(200);
const fromDate = ref("");
const toDate = ref("");

function epoch(value: string): number | undefined {
  return value ? Math.floor(new Date(`${value}T00:00:00Z`).getTime() / 1000) : undefined;
}

async function refresh() {
  loading.value = true;
  try {
    graph.value = (await invoke("relationships", {
      limitNodes: nodeLimit.value,
      maxEdges: edgeLimit.value,
      after: epoch(fromDate.value),
      before: toDate.value
        ? epoch(toDate.value)! + 86400
        : undefined,
    })) as Graph;
  } catch (e) {
    props.onError(String(e));
  } finally {
    loading.value = false;
  }
}

const positions = computed(() => {
  const nodes = graph.value?.nodes ?? [];
  if (!nodes.length || nodes.length > 16) return new Map<string, { x: number; y: number }>();
  const layout = new Map<string, { x: number; y: number }>();
  const center = 190;
  const radius = 140;
  nodes.forEach((node, index) => {
    const angle = (2 * Math.PI * index) / nodes.length - Math.PI / 2;
    layout.set(node.id, {
      x: center + radius * Math.cos(angle),
      y: center + radius * Math.sin(angle),
    });
  });
  return layout;
});

const drawn = computed(() =>
  graph.value && graph.value.nodes.length > 0 && graph.value.nodes.length <= 16,
);

function shortActor(actor: string): string {
  return actor.length > 26 ? `${actor.slice(0, 24)}…` : actor;
}

function strokeWidth(edge: GraphEdge): number {
  return Math.min(6, 1 + Math.log2(edge.threads + 1));
}

onMounted(refresh);
</script>

<template>
  <section class="relationships">
    <header class="toolbar">
      <div>
        <h2>Relationships</h2>
        <p class="hint">
          Observed co-participation in shared email threads and catalog conversations. Not a
          claim of personal or causal connection.
        </p>
      </div>
      <div class="controls">
        <label>
          From
          <input v-model="fromDate" type="date" @change="refresh" />
        </label>
        <label>
          To
          <input v-model="toDate" type="date" @change="refresh" />
        </label>
        <label>
          Nodes
          <input v-model.number="nodeLimit" type="number" min="2" max="100" @change="refresh" />
        </label>
        <label>
          Edges
          <input v-model.number="edgeLimit" type="number" min="1" max="500" @change="refresh" />
        </label>
        <button type="button" :disabled="loading" @click="refresh">
          {{ loading ? "Building…" : "Refresh" }}
        </button>
      </div>
    </header>

    <div v-if="graph" class="summary">
      <span>{{ graph.nodes.length }} participants</span>
      <span>{{ graph.edges.length }} shared-thread pairs</span>
      <span v-if="graph.truncated" class="status-warn">
        Truncated: more participants or pairs exist than the current limits show.
      </span>
    </div>

    <figure v-if="drawn && graph" class="diagram">
      <svg viewBox="0 0 380 380" role="img" aria-label="Shared-thread network diagram">
        <line
          v-for="(edge, index) in graph.edges"
          :key="`edge-${index}`"
          :x1="positions.get(edge.source)?.x"
          :y1="positions.get(edge.source)?.y"
          :x2="positions.get(edge.target)?.x"
          :y2="positions.get(edge.target)?.y"
          :stroke-width="strokeWidth(edge)"
        />
        <g v-for="node in graph.nodes" :key="node.id">
          <circle
            :cx="positions.get(node.id)?.x"
            :cy="positions.get(node.id)?.y"
            :r="4 + Math.min(8, node.shared_threads * 2)"
          />
          <text
            :x="positions.get(node.id)?.x"
            :y="(positions.get(node.id)?.y ?? 0) + 18"
            text-anchor="middle"
          >
            {{ shortActor(node.actor) }}
          </text>
        </g>
      </svg>
      <figcaption>Line thickness grows with the number of shared threads.</figcaption>
    </figure>
    <p v-else-if="graph && graph.nodes.length" class="hint">
      {{ graph.nodes.length }} participants is too many to draw legibly; use the table below.
    </p>

    <table v-if="graph && graph.edges.length">
      <thead>
        <tr>
          <th>Participants</th>
          <th>Source</th>
          <th>Shared threads</th>
          <th>Messages</th>
          <th>Examples</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(edge, index) in graph.edges" :key="index">
          <td>{{ edge.source_actor }} ↔ {{ edge.target_actor }}</td>
          <td>{{ edge.source_type }}</td>
          <td>{{ edge.threads }}</td>
          <td>{{ edge.messages }}</td>
          <td>
            <ul class="examples">
              <li v-for="example in edge.examples" :key="example.id">
                <span class="kind">{{ example.kind }}</span>
                {{ example.title || "Untitled" }}
                <span v-if="example.date" class="date">{{ example.date }}</span>
              </li>
            </ul>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-else-if="graph" class="hint">
      No shared threads found in this archive or date range.
    </p>

    <details v-if="graph" class="definitions">
      <summary>What these figures mean</summary>
      <ul>
        <li v-for="line in graph.definitions" :key="line">{{ line }}</li>
      </ul>
    </details>
  </section>
</template>

<style scoped>
.relationships {
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
  max-width: 520px;
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
input {
  padding: 4px 6px;
  border: 1px solid var(--hb-border-strong);
  border-radius: var(--hb-radius);
  background: var(--hb-workspace);
  color: var(--hb-text);
  width: 110px;
}
button {
  padding: 5px 12px;
  border: 1px solid var(--hb-border-strong);
  border-radius: var(--hb-radius);
  background: var(--hb-toolbar);
  color: var(--hb-text);
  cursor: pointer;
}
button:disabled {
  cursor: default;
  opacity: 0.6;
}
.summary {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  font-size: 12px;
  color: var(--hb-text-secondary);
}
.status-warn {
  color: var(--hb-warning);
}
.diagram {
  margin: 0;
  border: 1px solid var(--hb-border);
  border-radius: var(--hb-radius);
  background: var(--hb-panel);
  max-width: 420px;
}
svg {
  width: 100%;
  height: auto;
}
line {
  stroke: var(--hb-accent);
  stroke-opacity: 0.5;
}
circle {
  fill: var(--hb-accent);
}
text {
  font-size: 9px;
  fill: var(--hb-text);
}
figcaption {
  padding: 6px 10px;
  font-size: 11px;
  color: var(--hb-text-secondary);
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
th,
td {
  text-align: left;
  padding: 6px 8px;
  border-bottom: 1px solid var(--hb-border);
  vertical-align: top;
}
th {
  color: var(--hb-text-secondary);
  font-weight: 600;
}
.examples {
  margin: 0;
  padding-left: 14px;
}
.kind {
  text-transform: uppercase;
  font-size: 9px;
  letter-spacing: 0.04em;
  color: var(--hb-text-secondary);
}
.date {
  margin-left: 6px;
  color: var(--hb-text-secondary);
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
