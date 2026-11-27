<script setup lang="ts">
import { onMounted, ref } from "vue";
import { invoke } from "@tauri-apps/api/core";

const props = defineProps<{ onError: (message: string) => void; onChanged: () => void }>();

interface LastImport {
  status: string;
  at: string;
  records_new: number;
}
interface EmailAccount {
  account: string;
  messages: number;
  origins: number;
  folders: number;
  earliest: string | null;
  latest: string | null;
  last_import: LastImport | null;
}
interface CatalogSource {
  source_type: string;
  files: number;
  records: number;
  bytes: number;
  earliest: string | null;
  latest: string | null;
}
interface Sources {
  email_accounts: EmailAccount[];
  catalog_sources: CatalogSource[];
  catalog: { files: number; records: number };
  storage: { raw_bytes: number; database_bytes: number; total_bytes: number };
  history_available: boolean;
}

const data = ref<Sources | null>(null);
const loading = ref(false);

function bytes(value: number): string {
  if (!value) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let size = value;
  let index = 0;
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024;
    index += 1;
  }
  return `${size.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

async function refresh() {
  loading.value = true;
  try {
    data.value = (await invoke("sources")) as Sources;
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
  <section class="sources">
    <div class="row">
      <button :disabled="loading" @click="refresh">{{ loading ? "Loading…" : "Refresh" }}</button>
      <span class="meta">Derived from stored provenance and import history.</span>
    </div>

    <h2>Email accounts</h2>
    <p class="meta">
      A message present in several folders counts once under <em>messages</em> and once per mailbox
      under <em>origins</em>. Importing some folders never proves an account is complete.
    </p>
    <table v-if="data && data.email_accounts.length">
      <thead>
        <tr>
          <th>Account</th>
          <th>Messages</th>
          <th>Origins</th>
          <th>Folders</th>
          <th>Earliest</th>
          <th>Latest</th>
          <th>Last import</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="account in data.email_accounts" :key="account.account">
          <td class="account" :title="account.account">{{ account.account }}</td>
          <td>{{ account.messages.toLocaleString() }}</td>
          <td>{{ account.origins.toLocaleString() }}</td>
          <td>{{ account.folders }}</td>
          <td>{{ account.earliest ?? "—" }}</td>
          <td>{{ account.latest ?? "—" }}</td>
          <td>
            <template v-if="account.last_import">
              <span :class="{ bad: account.last_import.status === 'error' }">
                {{ account.last_import.status }}
              </span>
              <span class="meta"> {{ account.last_import.at }}</span>
            </template>
            <span v-else class="meta">{{ data.history_available ? "not recorded" : "unavailable" }}</span>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-else-if="data" class="meta">
      No mailbox origins yet. Importing .eml files preserves messages without claiming an account;
      IMAP synchronization records the account and folders it read.
    </p>

    <h2>Catalog sources</h2>
    <table v-if="data && data.catalog_sources.length">
      <thead>
        <tr>
          <th>Source</th>
          <th>Records</th>
          <th>Source files</th>
          <th>Size</th>
          <th>Earliest</th>
          <th>Latest</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="source in data.catalog_sources" :key="source.source_type">
          <td>{{ source.source_type }}</td>
          <td>{{ source.records.toLocaleString() }}</td>
          <td>{{ source.files.toLocaleString() }}</td>
          <td>{{ bytes(source.bytes) }}</td>
          <td>{{ source.earliest?.slice(0, 10) ?? "—" }}</td>
          <td>{{ source.latest?.slice(0, 10) ?? "—" }}</td>
        </tr>
      </tbody>
    </table>
    <p v-else-if="data" class="meta">No catalog sources have been imported yet.</p>

    <h2>Storage</h2>
    <div v-if="data" class="cards">
      <article class="card">
        <h3>Preserved originals</h3>
        <p class="figure">{{ bytes(data.storage.raw_bytes) }}</p>
        <p class="meta">Byte-exact EML files addressed by SHA-256</p>
      </article>
      <article class="card">
        <h3>Databases</h3>
        <p class="figure">{{ bytes(data.storage.database_bytes) }}</p>
        <p class="meta">Archive, catalog and research databases</p>
      </article>
      <article class="card">
        <h3>Total footprint</h3>
        <p class="figure">{{ bytes(data.storage.total_bytes) }}</p>
        <p class="meta">Originals plus databases, excluding backups</p>
      </article>
    </div>

    <p class="meta">
      Coverage is reported only from what has actually been imported. A large message count is not
      by itself evidence that a mailbox, account or export was captured completely.
    </p>
  </section>
</template>

<style scoped>
.sources {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.row {
  display: flex;
  align-items: center;
  gap: 10px;
}
h2 {
  font-size: 14px;
  margin: 10px 0 0;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
  background: var(--hb-workspace);
  border: 1px solid var(--hb-border);
}
th,
td {
  text-align: left;
  padding: 5px 7px;
  border-bottom: 1px solid var(--hb-border);
  font-variant-numeric: tabular-nums;
}
th {
  background: var(--hb-panel);
  color: var(--hb-text-secondary);
  font-weight: 600;
}
td.account {
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.bad {
  color: var(--hb-error-text);
}
.meta {
  color: var(--hb-text-secondary);
  font-size: 12px;
  margin: 0;
}
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}
.card {
  background: var(--hb-workspace);
  border: 1px solid var(--hb-border);
  border-radius: var(--hb-radius);
  padding: 10px 14px;
}
.card h3 {
  margin: 0 0 4px;
  font-size: 12px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--hb-text-secondary);
}
.figure {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}
</style>
