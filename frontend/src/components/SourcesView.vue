<script setup lang="ts">
import { onMounted, ref } from "vue";
import { invoke } from "@tauri-apps/api/core";
import { useEngineJob } from "../composables/useEngineJob";

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
  disabled: boolean;
  note: string | null;
}
interface CatalogSource {
  source_type: string;
  files: number;
  records: number;
  bytes: number;
  earliest: string | null;
  latest: string | null;
  disabled: boolean;
  note: string | null;
}
interface SourceEvent {
  id: number;
  source: string;
  source_key: string;
  action: string;
  at: string;
  detail: string | null;
}
interface Verification {
  source: string;
  source_key: string;
  checked: number;
  ok: number;
  bad: string[];
  missing: string[];
  cancelled: boolean;
}
interface RemovalPreview {
  source: string;
  source_key: string;
  records_removed: number;
  records_retained: number;
  origins_removed: number;
  raw_bytes_freed: number;
  catalog_records_removed: number;
  catalog_files_removed: number;
  explanation: string[];
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
const busy = ref(false);
const events = ref<SourceEvent[]>([]);
const pending = ref<RemovalPreview | null>(null);
const verification = ref<Verification | null>(null);
const { busy: verifying, progress: verifyProgress, start: startVerify, cancel: cancelVerify } =
  useEngineJob();

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

async function loadEvents() {
  try {
    const response = (await invoke("source_events", { limit: 12 })) as { events: SourceEvent[] };
    events.value = response.events;
  } catch (e) {
    props.onError(String(e));
  }
}

async function refresh() {
  loading.value = true;
  try {
    data.value = (await invoke("sources")) as Sources;
    await loadEvents();
    props.onChanged();
  } catch (e) {
    props.onError(String(e));
  } finally {
    loading.value = false;
  }
}

async function toggle(source: "email" | "catalog", sourceKey: string, enabled: boolean) {
  busy.value = true;
  try {
    await invoke("source_set_enabled", { source, sourceKey, enabled });
    await refresh();
  } catch (e) {
    props.onError(String(e));
  } finally {
    busy.value = false;
  }
}

async function verify(source: "email" | "catalog", sourceKey: string) {
  verification.value = null;
  try {
    const outcome = await startVerify("source_verify", { source, sourceKey });
    if (outcome.event === "job_error") {
      props.onError(String(outcome.message || "Verification failed"));
      return;
    }
    verification.value = outcome.result;
  } catch (e) {
    props.onError(String(e));
  }
}

async function previewRemoval(source: "email" | "catalog", sourceKey: string) {
  try {
    pending.value = (await invoke("source_removal_preview", {
      source,
      sourceKey,
    })) as RemovalPreview;
  } catch (e) {
    props.onError(String(e));
  }
}

async function confirmRemoval() {
  if (!pending.value) return;
  busy.value = true;
  try {
    await invoke("source_remove", {
      source: pending.value.source,
      sourceKey: pending.value.source_key,
      confirm: true,
    });
    pending.value = null;
    await refresh();
  } catch (e) {
    props.onError(String(e));
  } finally {
    busy.value = false;
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
          <th>Status</th>
          <th>Actions</th>
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
          <td :class="{ disabled: account.disabled }" :title="account.note || ''">
            {{ account.disabled ? "Disabled" : "Enabled" }}
          </td>
          <td class="actions">
            <button
              :disabled="busy || verifying"
              @click="toggle('email', account.account, account.disabled)"
            >
              {{ account.disabled ? "Enable" : "Disable" }}
            </button>
            <button :disabled="busy || verifying" @click="verify('email', account.account)">
              Verify
            </button>
            <button :disabled="busy || verifying" @click="previewRemoval('email', account.account)">
              Remove…
            </button>
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
          <th>Status</th>
          <th>Actions</th>
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
          <td :class="{ disabled: source.disabled }" :title="source.note || ''">
            {{ source.disabled ? "Disabled" : "Enabled" }}
          </td>
          <td class="actions">
            <button
              :disabled="busy || verifying"
              @click="toggle('catalog', source.source_type, source.disabled)"
            >
              {{ source.disabled ? "Enable" : "Disable" }}
            </button>
            <button :disabled="busy || verifying" @click="verify('catalog', source.source_type)">
              Verify
            </button>
            <button :disabled="busy || verifying" @click="previewRemoval('catalog', source.source_type)">
              Remove…
            </button>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-else-if="data" class="meta">No catalog sources have been imported yet.</p>

    <section v-if="pending" class="removal" role="alertdialog" aria-label="Confirm source removal">
      <h3>Remove {{ pending.source_key }}?</h3>
      <ul>
        <li v-for="line in pending.explanation" :key="line">{{ line }}</li>
      </ul>
      <p class="meta">
        Records deleted: {{ pending.records_removed.toLocaleString() }} ·
        shared records retained: {{ pending.records_retained.toLocaleString() }} ·
        originals freed: {{ bytes(pending.raw_bytes_freed) }}
      </p>
      <div class="row">
        <button class="danger" :disabled="busy" @click="confirmRemoval">
          Confirm removal
        </button>
        <button :disabled="busy" @click="pending = null">Cancel</button>
      </div>
    </section>

    <p v-if="verifyProgress" class="meta">
      {{ verifyProgress }}
      <button v-if="verifying" @click="cancelVerify">Cancel</button>
    </p>

    <section v-if="verification" class="verify" role="status">
      <h3>Verification: {{ verification.source_key }}</h3>
      <p class="meta">
        {{ verification.checked.toLocaleString() }} checked ·
        {{ verification.ok.toLocaleString() }} verified ·
        {{ verification.bad.length.toLocaleString() }} altered ·
        {{ verification.missing.length.toLocaleString() }} missing
        <span v-if="verification.cancelled"> · cancelled</span>
      </p>
      <p class="meta">
        Hash checks detect changed bytes. They are not proof of authenticity, legal admissibility
        or chain of custody.
      </p>
      <details v-if="verification.bad.length || verification.missing.length">
        <summary>Show affected items (first 20 of each)</summary>
        <ul>
          <li v-for="item in verification.bad.slice(0, 20)" :key="'bad-' + item" class="bad">
            altered: {{ item }}
          </li>
          <li v-for="item in verification.missing.slice(0, 20)" :key="'missing-' + item">
            missing: {{ item }}
          </li>
        </ul>
      </details>
    </section>

    <h2>Source activity</h2>
    <p class="meta">
      Disabling a source stops new automatic imports; its historical records stay searchable and
      visible. Removal deletes only the records described in the preview.
    </p>
    <table v-if="events.length" class="events">
      <thead>
        <tr><th>When</th><th>Action</th><th>Source</th><th>Target</th><th>Note</th></tr>
      </thead>
      <tbody>
        <tr v-for="event in events" :key="event.id">
          <td>{{ event.at }}</td>
          <td>{{ event.action }}</td>
          <td>{{ event.source }}</td>
          <td class="target" :title="event.source_key">{{ event.source_key }}</td>
          <td>{{ event.detail || "—" }}</td>
        </tr>
      </tbody>
    </table>
    <p v-else class="meta">No source activity recorded yet.</p>

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
.disabled {
  color: var(--hb-warning-text);
  font-weight: 600;
}
td.actions {
  white-space: nowrap;
}
td.actions button {
  padding: 3px 8px;
  margin-right: 4px;
  font-size: 12px;
}
.removal {
  background: var(--hb-panel-alt);
  border: 1px solid var(--hb-error);
  border-radius: var(--hb-radius);
  padding: 10px 12px;
}
.removal h3 {
  margin: 0 0 6px;
  font-size: 13px;
  color: var(--hb-error-text);
}
.removal ul {
  margin: 0 0 6px;
  padding-left: 18px;
  font-size: 12px;
}
.danger {
  border-color: var(--hb-error);
  color: var(--hb-error-text);
}
.verify {
  background: var(--hb-panel-alt);
  border: 1px solid var(--hb-info);
  border-radius: var(--hb-radius);
  padding: 10px 12px;
}
.verify h3 {
  margin: 0 0 6px;
  font-size: 13px;
  color: var(--hb-info-text);
}
.verify ul {
  margin: 6px 0 0;
  padding-left: 18px;
  font-size: 12px;
  word-break: break-all;
}
.events td.target {
  max-width: 240px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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
