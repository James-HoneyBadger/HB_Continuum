<script setup lang="ts">
import { computed, ref } from "vue";
import { save } from "@tauri-apps/plugin-dialog";
import { useEngineJob } from "../composables/useEngineJob";

const props = defineProps<{ onError: (message: string) => void; onChanged: () => void }>();

type Format = "markdown" | "json" | "html";
const format = ref<Format>("markdown");
const result = ref<{ path: string; format: string; bytes: number } | null>(null);
const { busy, progress, start, cancel } = useEngineJob();

const extension = computed(() =>
  format.value === "markdown" ? "md" : format.value === "json" ? "json" : "html",
);
const label = computed(() =>
  format.value === "markdown" ? "Markdown" : format.value === "json" ? "JSON" : "HTML",
);

async function exportReport() {
  result.value = null;
  const stamp = new Date().toISOString().slice(0, 10).replace(/-/g, "");
  try {
    const destination = await save({
      title: "Save archive report",
      defaultPath: `hb-continuum-report-${stamp}.${extension.value}`,
      filters: [{ name: label.value, extensions: [extension.value] }],
    });
    if (!destination) return;
    const outcome = await start("report_archive", {
      destination,
      format: format.value,
    });
    if (outcome.event === "job_error") {
      props.onError(String(outcome.message || "Report generation failed"));
      return;
    }
    result.value = outcome.result;
    props.onChanged();
  } catch (e) {
    props.onError(String(e));
  }
}
</script>

<template>
  <section class="reports">
    <h2>Archive report</h2>
    <p class="meta">
      A single self-contained document describing what this archive actually contains: unique
      messages and mailbox origins, normalized date coverage, records by year, email accounts,
      catalog sources, consistency checks, recent imports and explicit limitations.
    </p>

    <div class="row">
      <label class="field">
        Format
        <select v-model="format" :disabled="busy">
          <option value="markdown">Markdown (.md)</option>
          <option value="json">JSON (.json)</option>
          <option value="html">Standalone HTML (.html)</option>
        </select>
      </label>
      <button :disabled="busy" @click="exportReport">
        {{ busy ? "Generating…" : "Save archive report…" }}
      </button>
      <button v-if="busy" @click="cancel">Cancel</button>
    </div>
    <p v-if="progress" class="meta">{{ progress }}</p>
    <p v-if="result" class="ok">
      Report written to {{ result.path }} ({{ result.bytes }} bytes, {{ result.format }}).
    </p>

    <h3>What the report does not claim</h3>
    <ul class="limits">
      <li>Counts describe stored records, not what exists on a remote service.</li>
      <li>Importing folders or files does not prove a source was captured completely.</li>
      <li>Hash verification detects changed bytes; it is not legal certification.</li>
      <li>Records without a normalized date are excluded from coverage and year counts.</li>
    </ul>
    <p class="meta">
      Reports are written outside the archive and never replace an existing file. If you choose an
      existing name, generation stops and asks you to pick a new one. Generating a report scans the
      archive for consistency but does not modify it.
    </p>
  </section>
</template>

<style scoped>
.reports {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-width: 820px;
}
h2 {
  font-size: 15px;
  margin: 0;
}
h3 {
  font-size: 13px;
  margin: 10px 0 4px;
}
.row {
  display: flex;
  align-items: flex-end;
  gap: 10px;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 3px;
  font-size: 12px;
  color: var(--hb-text-secondary);
}
select {
  padding: 5px 7px;
  border: 1px solid var(--hb-border);
  background: var(--hb-workspace);
  border-radius: var(--hb-radius);
}
.meta {
  color: var(--hb-text-secondary);
  font-size: 12px;
  margin: 0;
}
.ok {
  color: var(--hb-success-text);
  font-size: 12px;
  margin: 0;
  word-break: break-all;
}
.limits {
  margin: 0;
  padding-left: 18px;
  font-size: 12px;
  color: var(--hb-text-secondary);
}
</style>
