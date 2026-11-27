<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { invoke } from "@tauri-apps/api/core";

const props = defineProps<{ onError: (message: string) => void; onChanged: () => void }>();

interface YearBucket {
  year: number;
  count: number;
}
interface Dashboard {
  archive: {
    messages: number;
    origins: number;
    undated: number;
    earliest: string | null;
    latest: string | null;
  };
  catalog: { files: number; records: number };
  by_year: YearBucket[];
  storage: { raw_bytes: number; database_bytes: number; total_bytes: number };
}

const data = ref<Dashboard | null>(null);
const loading = ref(false);

const peak = computed(() =>
  Math.max(1, ...(data.value?.by_year.map((b) => b.count) ?? [1])),
);

function bytes(value: number): string {
  if (!value) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let index = 0;
  let size = value;
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024;
    index += 1;
  }
  return `${size.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

async function refresh() {
  loading.value = true;
  try {
    data.value = (await invoke("dashboard")) as Dashboard;
    props.onChanged();
  } catch (e) {
    props.onError(String(e));
  } finally {
    loading.value = false;
  }
}

onMounted(refresh);
</script>

<template>
  <section class="overview">
    <div class="row">
      <button :disabled="loading" @click="refresh">{{ loading ? "Loading…" : "Refresh" }}</button>
      <span class="meta">
        Unique records, mailbox occurrences and derived catalog entries are counted separately.
      </span>
    </div>

    <div v-if="data" class="cards">
      <article class="card">
        <h3>Archive</h3>
        <p class="figure">{{ data.archive.messages.toLocaleString() }}</p>
        <p class="meta">unique messages</p>
        <p class="meta">{{ data.archive.origins.toLocaleString() }} mailbox occurrences</p>
        <p class="meta">{{ data.archive.undated.toLocaleString() }} without a usable date</p>
      </article>

      <article class="card">
        <h3>Coverage</h3>
        <p class="figure">{{ data.archive.earliest ?? "—" }}</p>
        <p class="meta">earliest normalized date</p>
        <p class="meta">latest {{ data.archive.latest ?? "—" }}</p>
      </article>

      <article class="card">
        <h3>Catalog</h3>
        <p class="figure">{{ data.catalog.records.toLocaleString() }}</p>
        <p class="meta">source-independent records</p>
        <p class="meta">{{ data.catalog.files.toLocaleString() }} source files</p>
      </article>

      <article class="card">
        <h3>Storage</h3>
        <p class="figure">{{ bytes(data.storage.total_bytes) }}</p>
        <p class="meta">{{ bytes(data.storage.raw_bytes) }} preserved originals</p>
        <p class="meta">{{ bytes(data.storage.database_bytes) }} databases</p>
      </article>
    </div>

    <section v-if="data && data.by_year.length" class="years">
      <h3>Records by year</h3>
      <ul>
        <li v-for="bucket in data.by_year" :key="bucket.year">
          <span class="year">{{ bucket.year }}</span>
          <span class="bar-track">
            <span
              class="bar"
              :style="{ width: `${Math.max(2, (bucket.count / peak) * 100)}%` }"
              :title="`${bucket.count} records in ${bucket.year}`"
            ></span>
          </span>
          <span class="count">{{ bucket.count.toLocaleString() }}</span>
        </li>
      </ul>
      <p class="meta">Only records with a normalized date are counted.</p>
    </section>

    <p v-if="data && !data.by_year.length" class="meta">
      No messages with a usable date yet. Import mail to populate the historical timeline.
    </p>
  </section>
</template>

<style scoped>
.overview {
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 12px;
}
.card {
  background: var(--hb-workspace);
  border: 1px solid var(--hb-border);
  border-radius: var(--hb-radius);
  padding: 12px 14px;
}
.card h3 {
  margin: 0 0 6px;
  font-size: 12px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--hb-text-secondary);
}
.figure {
  margin: 0;
  font-size: 22px;
  font-weight: 600;
  color: var(--hb-text);
}
.meta {
  margin: 2px 0 0;
  color: var(--hb-text-secondary);
  font-size: 12px;
}
.years h3 {
  font-size: 13px;
  margin: 0 0 8px;
}
.years ul {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.years li {
  display: grid;
  grid-template-columns: 56px 1fr 64px;
  align-items: center;
  gap: 10px;
}
.year {
  font-variant-numeric: tabular-nums;
  color: var(--hb-text-secondary);
}
.bar-track {
  background: var(--hb-panel-alt);
  border: 1px solid var(--hb-border);
  height: 14px;
}
.bar {
  display: block;
  height: 100%;
  background: var(--hb-header);
}
.count {
  text-align: right;
  font-variant-numeric: tabular-nums;
  color: var(--hb-text-secondary);
}
</style>
