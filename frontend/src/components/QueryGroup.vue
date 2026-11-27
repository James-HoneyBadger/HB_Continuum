<script setup lang="ts">
import { ref } from "vue";

defineOptions({ name: "QueryGroup" });

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

const props = defineProps<{
  node: Group;
  depth: number;
  onRemove?: () => void;
}>();

const kinds = ["text", "actor", "kind", "source", "date", "tag"] as const;
const recordKinds = ["message", "post", "comment", "event", "media", "reaction"];
const newKind = ref<string>("text");

function makeRule(kind: string): Rule {
  if (kind === "text") return { type: "rule", kind, value: "" };
  if (kind === "date") return { type: "rule", kind, after: null, before: null };
  if (kind === "kind") return { type: "rule", kind, values: ["message"] };
  if (kind === "source") return { type: "rule", kind, values: ["email", "facebook"] };
  if (kind === "tag") return { type: "rule", kind, values: [], mode: "any" };
  return { type: "rule", kind, values: [] };
}

function addRule() {
  if (props.node.children.length >= 20) return;
  props.node.children.push(makeRule(newKind.value));
}

function addGroup() {
  if (props.node.children.length >= 20) return;
  props.node.children.push({ type: "group", op: "and", children: [makeRule("text")] });
}

function removeChild(index: number) {
  props.node.children.splice(index, 1);
}

function changeKind(rule: Rule, event: Event) {
  const kind = (event.target as HTMLSelectElement).value;
  Object.keys(rule).forEach((key) => {
    if (key !== "type" && key !== "kind") delete (rule as any)[key];
  });
  const fresh = makeRule(kind);
  rule.kind = kind;
  Object.assign(rule, fresh);
}

function setText(rule: Rule, event: Event) {
  rule.value = (event.target as HTMLInputElement).value;
}

function toggleFromEvent(rule: Rule, value: string, event: Event) {
  const checked = (event.target as HTMLInputElement).checked;
  const values = rule.values ?? [];
  rule.values = checked
    ? [...values.filter((item) => item !== value), value]
    : values.filter((item) => item !== value);
}

function setValues(rule: Rule, event: Event) {
  const text = (event.target as HTMLInputElement).value;
  rule.values = text
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);
}

function hasValue(rule: Rule, value: string) {
  return (rule.values ?? []).includes(value);
}

function epoch(value: string): number | null {
  if (!value) return null;
  return Math.floor(new Date(`${value}T00:00:00Z`).getTime() / 1000);
}

function toIso(value?: number | null): string {
  if (!value) return "";
  return new Date(value * 1000).toISOString().slice(0, 10);
}

function setAfter(rule: Rule, event: Event) {
  rule.after = epoch((event.target as HTMLInputElement).value);
}

function setBefore(rule: Rule, event: Event) {
  const start = epoch((event.target as HTMLInputElement).value);
  rule.before = start === null ? null : start + 86400;
}
</script>

<template>
  <fieldset class="group" :class="`op-${node.op}`">
    <legend>
      <select v-model="node.op" aria-label="Group operator">
        <option value="and">ALL of (AND)</option>
        <option value="or">ANY of (OR)</option>
        <option value="not">NOT</option>
      </select>
      <button
        v-if="depth > 0"
        type="button"
        class="remove"
        title="Remove this group"
        @click="onRemove?.()"
      >
        Remove group
      </button>
    </legend>

    <div v-for="(child, index) in node.children" :key="index" class="child">
      <QueryGroup
        v-if="child.type === 'group'"
        :node="child"
        :depth="depth + 1"
        :on-remove="() => removeChild(index)"
      />
      <div v-else class="rule">
        <select
          :value="child.kind"
          aria-label="Rule kind"
          @change="changeKind(child, $event)"
        >
          <option v-for="kind in kinds" :key="kind" :value="kind">{{ kind }}</option>
        </select>

        <input
          v-if="child.kind === 'text'"
          :value="child.value"
          class="grow"
          placeholder='Text or FTS expression, e.g. (gold OR silver) AND invoice'
          @input="setText(child, $event)"
        />

        <template v-else-if="child.kind === 'actor'">
          <input
            :value="(child.values ?? []).join(', ')"
            class="grow"
            placeholder="One or more senders or actors, comma separated"
            @input="setValues(child, $event)"
          />
        </template>

        <template v-else-if="child.kind === 'kind'">
          <label v-for="kind in recordKinds" :key="kind" class="check">
            <input
              type="checkbox"
              :checked="hasValue(child, kind)"
              @change="toggleFromEvent(child, kind, $event)"
            />
            {{ kind }}
          </label>
        </template>

        <template v-else-if="child.kind === 'source'">
          <label class="check">
            <input
              type="checkbox"
              :checked="hasValue(child, 'email')"
              @change="toggleFromEvent(child, 'email', $event)"
            />
            email
          </label>
          <label class="check">
            <input
              type="checkbox"
              :checked="hasValue(child, 'facebook')"
              @change="toggleFromEvent(child, 'facebook', $event)"
            />
            catalog
          </label>
        </template>

        <template v-else-if="child.kind === 'date'">
          <label class="check">
            From
            <input
              type="date"
              :value="toIso(child.after)"
              @change="setAfter(child, $event)"
            />
          </label>
          <label class="check">
            To (inclusive)
            <input
              type="date"
              :value="toIso(child.before ? child.before - 86400 : null)"
              @change="setBefore(child, $event)"
            />
          </label>
        </template>

        <template v-else-if="child.kind === 'tag'">
          <input
            :value="(child.values ?? []).join(', ')"
            class="grow"
            placeholder="Tags, comma separated"
            @input="setValues(child, $event)"
          />
          <select v-model="child.mode" aria-label="Tag match mode">
            <option value="any">any tag</option>
            <option value="all">all tags</option>
          </select>
        </template>

        <button type="button" class="remove" @click="removeChild(index)">Remove</button>
      </div>
    </div>

    <div class="add">
      <select v-model="newKind" aria-label="Rule type to add">
        <option v-for="kind in kinds" :key="kind" :value="kind">{{ kind }}</option>
      </select>
      <button type="button" @click="addRule">Add rule</button>
      <button type="button" @click="addGroup">Add group</button>
      <span v-if="node.children.length >= 20" class="limit">20-child limit reached</span>
    </div>
  </fieldset>
</template>

<style scoped>
.group {
  border: 1px solid var(--hb-border-strong);
  border-radius: var(--hb-radius);
  padding: 8px 10px 10px;
  margin: 0;
  background: var(--hb-workspace);
}
.group.op-or {
  border-color: var(--hb-accent);
}
.group.op-not {
  border-color: var(--hb-error);
}
legend {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 4px;
  font-size: 11px;
  color: var(--hb-text-secondary);
}
.child {
  margin-top: 6px;
}
.rule {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}
input,
select,
button {
  padding: 4px 6px;
  border: 1px solid var(--hb-border-strong);
  border-radius: var(--hb-radius);
  background: var(--hb-panel-alt);
  color: var(--hb-text);
  font-size: 12px;
}
.grow {
  flex: 1;
  min-width: 220px;
}
.check {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--hb-text-secondary);
}
.check input[type="date"] {
  width: 130px;
}
button {
  cursor: pointer;
}
.remove {
  color: var(--hb-error-text);
}
.add {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
}
.limit {
  font-size: 11px;
  color: var(--hb-warning-text);
}
</style>
