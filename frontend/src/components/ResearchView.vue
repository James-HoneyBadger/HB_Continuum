<script setup lang="ts">
import { ref } from "vue";
import { invoke } from "@tauri-apps/api/core";
import { save as saveDialog } from "@tauri-apps/plugin-dialog";

const props = defineProps<{ onError: (message: string) => void; onChanged: () => void }>();

const workspaces = ref<any[][]>([]);
const searches = ref<any[][]>([]);
const fields = ref<any[][]>([]);
const reports = ref<any[][]>([]);
const tags = ref<any[][]>([]);
const notice = ref("");

const workspace = ref({ name: "", description: "" });
const search = ref({ workspace: "General", name: "", query: "", tag: "", limit: 1000 });
const fieldDraft = ref({ name: "", kind: "text", choices: "" });
const metadata = ref({ hash: "", field: "", value: "" });
const reportDraft = ref({ name: "", workspace: "General", search: "", columns: "subject;sender;date;hash", group: "" });
const preview = ref<{ name: string; columns: string[]; rows: any[] } | null>(null);
const reportName = ref("");
const runResult = ref<any[]>([]);
const runName = ref("");

async function refresh() {
  try {
    const [w, s, f, r, t] = await Promise.all([
      invoke("research_list", { table: "workspaces" }) as Promise<any>,
      invoke("research_list", { table: "searches" }) as Promise<any>,
      invoke("research_list", { table: "fields" }) as Promise<any>,
      invoke("research_list", { table: "reports" }) as Promise<any>,
      invoke("research_list", { table: "tags" }) as Promise<any>,
    ]);
    workspaces.value = w.rows;
    searches.value = s.rows;
    fields.value = f.rows;
    reports.value = r.rows;
    tags.value = t.rows;
  } catch (e) {
    props.onError(String(e));
  }
}

async function saveWorkspace() {
  notice.value = "";
  try {
    await invoke("research_workspace_save", {
      workspace: workspace.value.name,
      description: workspace.value.description,
    });
    notice.value = `Workspace “${workspace.value.name}” saved.`;
    await refresh();
  } catch (e) {
    props.onError(String(e));
  }
}

async function saveSearch() {
  notice.value = "";
  try {
    await invoke("research_search_save", {
      workspace: search.value.workspace,
      name: search.value.name,
      query: search.value.query,
      tag: search.value.tag,
      limit: Number(search.value.limit) || 1000,
    });
    notice.value = `Saved search “${search.value.name}” saved.`;
    await refresh();
  } catch (e) {
    props.onError(String(e));
  }
}

async function runSearch(row: any[]) {
  runName.value = `${row[0]} / ${row[1]}`;
  try {
    const response = (await invoke("research_results", {
      workspace: row[0],
      name: row[1],
    })) as { results: any[] };
    runResult.value = response.results;
  } catch (e) {
    props.onError(String(e));
  }
}

async function defineField() {
  notice.value = "";
  try {
    const choices = fieldDraft.value.choices
      .split(";")
      .map((c) => c.trim())
      .filter(Boolean);
    await invoke("research_field_define", {
      name: fieldDraft.value.name,
      kind: fieldDraft.value.kind,
      choices,
    });
    notice.value = `Field “${fieldDraft.value.name}” defined.`;
    await refresh();
  } catch (e) {
    props.onError(String(e));
  }
}

async function setMetadata() {
  notice.value = "";
  try {
    await invoke("research_metadata_set", {
      hash: metadata.value.hash.trim(),
      field: metadata.value.field,
      value: metadata.value.value,
    });
    notice.value = "Metadata saved.";
  } catch (e) {
    props.onError(String(e));
  }
}

async function applyRules() {
  notice.value = "";
  try {
    const response = (await invoke("research_apply_rules")) as { matches: number };
    notice.value = `${response.matches} rule matches rebuilt.`;
    await refresh();
  } catch (e) {
    props.onError(String(e));
  }
}

async function saveReport() {
  notice.value = "";
  try {
    const columns = reportDraft.value.columns
      .split(";")
      .map((c) => c.trim())
      .filter(Boolean);
    await invoke("research_report_save", {
      name: reportDraft.value.name,
      workspace: reportDraft.value.workspace,
      search: reportDraft.value.search,
      columns,
      groupBy: reportDraft.value.group,
    });
    notice.value = `Report “${reportDraft.value.name}” saved.`;
    await refresh();
  } catch (e) {
    props.onError(String(e));
  }
}

async function previewReport(name: string) {
  notice.value = "";
  try {
    preview.value = (await invoke("research_report_preview", { name })) as any;
    reportName.value = name;
  } catch (e) {
    props.onError(String(e));
  }
}

async function exportReport() {
  notice.value = "";
  if (!reportName.value) {
    notice.value = "Preview a report first.";
    return;
  }
  try {
    const target = await saveDialog({
      defaultPath: `${reportName.value}.csv`,
      filters: [{ name: "CSV", extensions: ["csv"] }],
    });
    if (!target) return;
    await invoke("research_report_export", { name: reportName.value, path: target });
    notice.value = `Exported to ${target}`;
  } catch (e) {
    props.onError(String(e));
  }
}

refresh();
</script>

<template>
  <section>
    <h2>Research</h2>
    <p class="meta">
      Research overlays are stored separately from original messages. They never modify archive data.
    </p>
    <p v-if="notice" class="notice">{{ notice }}</p>

    <h3>Workspaces</h3>
    <div class="row">
      <input v-model="workspace.name" placeholder="Workspace name" />
      <input v-model="workspace.description" placeholder="Description (optional)" />
      <button @click="saveWorkspace">Save</button>
    </div>
    <ul class="plain">
      <li v-for="w in workspaces" :key="w[0]">{{ w[0] }} — {{ w[1] }}</li>
    </ul>

    <h3>Saved searches</h3>
    <div class="row">
      <input v-model="search.workspace" placeholder="Workspace" />
      <input v-model="search.name" placeholder="Search name" />
      <input v-model="search.query" placeholder="FTS query (blank = all)" />
      <input v-model="search.tag" placeholder="Required tag (optional)" />
      <input v-model.number="search.limit" type="number" placeholder="Limit" class="narrow" />
      <button @click="saveSearch">Save</button>
    </div>
    <ul class="plain">
      <li v-for="s in searches" :key="s[0] + s[1]">
        <button class="link" @click="runSearch(s)">{{ s[0] }} / {{ s[1] }}</button>
        <span class="meta">{{ s[2] || "(all)" }} · limit {{ s[4] }}</span>
      </li>
    </ul>
    <div v-if="runResult.length">
      <h4>{{ runName }} — {{ runResult.length }} results</h4>
      <ul class="plain">
        <li v-for="r in runResult" :key="r.hash"><span class="meta">{{ r.date }}</span> {{ r.subject }}</li>
      </ul>
    </div>

    <h3>Tags and rules</h3>
    <p class="meta">{{ tags.length }} tag assignments. Select messages in Search to tag them.</p>
    <button @click="applyRules">Rebuild rule tags</button>

    <h3>Custom fields</h3>
    <div class="row">
      <input v-model="fieldDraft.name" placeholder="Field name" />
      <select v-model="fieldDraft.kind">
        <option>text</option>
        <option>number</option>
        <option>date</option>
        <option>choice</option>
        <option>boolean</option>
      </select>
      <input v-model="fieldDraft.choices" placeholder="Choices (semicolon separated)" />
      <button @click="defineField">Define</button>
    </div>
    <ul class="plain">
      <li v-for="f in fields" :key="f[0]">{{ f[0] }} — {{ f[1] }}</li>
    </ul>
    <div class="row">
      <input v-model="metadata.hash" placeholder="Message SHA-256" />
      <input v-model="metadata.field" placeholder="Field" />
      <input v-model="metadata.value" placeholder="Value" />
      <button @click="setMetadata">Set value</button>
    </div>

    <h3>Reports</h3>
    <div class="row">
      <input v-model="reportDraft.name" placeholder="Report name" />
      <input v-model="reportDraft.workspace" placeholder="Workspace" />
      <input v-model="reportDraft.search" placeholder="Saved search" />
      <input v-model="reportDraft.columns" placeholder="Columns" />
      <select v-model="reportDraft.group">
        <option value="">(no grouping)</option>
        <option value="sender">sender</option>
        <option value="year">year</option>
        <option value="tag">tag</option>
      </select>
      <button @click="saveReport">Save</button>
    </div>
    <ul class="plain">
      <li v-for="r in reports" :key="r[0]">
        <button class="link" @click="previewReport(r[0])">{{ r[0] }}</button>
        <span class="meta">{{ r[1] }} / {{ r[2] }}</span>
      </li>
    </ul>
    <div v-if="preview">
      <h4>{{ preview.name }}</h4>
      <table>
        <thead>
          <tr><th v-for="c in preview.columns" :key="c">{{ c }}</th></tr>
        </thead>
        <tbody>
          <tr v-for="(row, i) in preview.rows" :key="i">
            <td v-for="c in preview.columns" :key="c">{{ row[c] }}</td>
          </tr>
        </tbody>
      </table>
      <button @click="exportReport">Export CSV…</button>
    </div>
  </section>
</template>

<style scoped>
.row {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
  align-items: center;
  flex-wrap: wrap;
}
input,
select {
  padding: 6px;
  font-size: 13px;
  flex: 1;
  min-width: 120px;
}
.narrow {
  flex: 0 0 90px;
  min-width: 90px;
}
button {
  padding: 6px 14px;
}
.link {
  background: none;
  border: none;
  color: var(--hb-link);
  cursor: pointer;
  padding: 0;
  text-decoration: underline;
  font-size: 13px;
}
.plain {
  list-style: none;
  padding: 0;
  margin: 0 0 14px;
}
.plain li {
  padding: 3px 0;
  font-size: 13px;
}
.meta {
  color: var(--hb-text-secondary);
  font-size: 12px;
  margin-left: 8px;
}
.notice {
  color: var(--hb-success-text);
}
table {
  border-collapse: collapse;
  font-size: 12px;
  margin: 8px 0;
}
th,
td {
  border: 1px solid var(--hb-border);
  padding: 4px 8px;
  text-align: left;
}
</style>
