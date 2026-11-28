<script setup lang="ts">
import { onMounted, ref } from "vue";
import { invoke } from "@tauri-apps/api/core";
import { save } from "@tauri-apps/plugin-dialog";
import { useEngineJob } from "../composables/useEngineJob";

const props = defineProps<{ onError: (message: string) => void; onChanged: () => void }>();

interface Evidence {
  evidence_id: string;
  source: string;
  source_type: string;
  id: string;
  kind: string;
  title: string;
  actor: string;
  date: string;
  source_key: string;
  source_location: string;
  excerpt: string;
  complete: boolean;
  characters: number;
}

interface Claim {
  text: string;
  evidence: string[];
  kind: string;
}

interface CitationRecord {
  evidence_id: string;
  source: string;
  id: string;
  title: string;
  date: string;
  source_location: string;
}

interface ResearchResult {
  request: Record<string, any>;
  queries: string[];
  evidence: Evidence[];
  context: {
    characters: number;
    budget: number;
    per_record_chars: number;
    omitted: number;
    truncated: boolean;
  };
  retrieval: { missing_records?: number; collection_filtered?: boolean };
  model: { enabled: boolean; name: string; used: boolean };
  answer: string | null;
  claims: Claim[];
  citations: string[];
  citation_records?: CitationRecord[];
  invalid_citations: string[];
  uncited_claims: string[];
  insufficient: boolean;
  missing: string[];
  contradictions: string[];
  limitations: string[];
  grounded: boolean;
  warning: string | null;
  error: string | null;
  cancelled: boolean;
}

interface ConversationSummary {
  id: number;
  workspace: string;
  title: string;
  created_at: string;
  updated_at: string;
  turns: number;
}

interface Turn {
  id: number;
  role: "user" | "assistant";
  content: string;
  request: any;
  answer: ResearchResult | null;
  model_name: string | null;
  created_at: string;
}

interface Conversation extends Omit<ConversationSummary, "turns"> {
  turns: Turn[];
}

interface Collection {
  id: number;
  workspace: string;
  name: string;
}

const status = ref<any>(null);
const modelStatus = ref<any>(null);
const conversations = ref<ConversationSummary[]>([]);
const collections = ref<Collection[]>([]);
const selectedId = ref<number | null>(null);
const conversation = ref<Conversation | null>(null);
const result = ref<ResearchResult | null>(null);
const detail = ref<any>(null);
const notice = ref("");

const question = ref("");
const sourceEmail = ref(true);
const sourceFacebook = ref(true);
const sourceDocument = ref(true);
const fromDate = ref("");
const toDate = ref("");
const peopleText = ref("");
const topicsText = ref("");
const collectionId = ref<number | null>(null);
const depth = ref(40);
const contextBudget = ref(40000);
const perRecord = ref(2000);
const model = ref("");

const askJob = useEngineJob();
const modelJob = useEngineJob();
const busy = askJob.busy;
const checking = modelJob.busy;

function splitList(value: string): string[] | undefined {
  const items = value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  return items.length ? items : undefined;
}

function evidenceFor(evidenceId: string): Evidence | undefined {
  return result.value?.evidence.find((item) => item.evidence_id === evidenceId);
}

async function loadStatus() {
  try {
    status.value = (await invoke("intelligence_status")) as any;
    if (!model.value) model.value = status.value.model || "";
  } catch (e) {
    props.onError(String(e));
  }
}

async function loadCollections() {
  try {
    const response = (await invoke("collections_list")) as { collections: Collection[] };
    collections.value = response.collections;
  } catch (e) {
    props.onError(String(e));
  }
}

async function loadConversations() {
  try {
    const response = (await invoke("conversation_list")) as {
      conversations: ConversationSummary[];
    };
    conversations.value = response.conversations;
  } catch (e) {
    props.onError(String(e));
  }
}

async function selectConversation(id: number) {
  notice.value = "";
  detail.value = null;
  try {
    selectedId.value = id;
    const loaded = (await invoke("conversation_get", { conversationId: id })) as Conversation;
    conversation.value = loaded;
    const lastAssistant = [...loaded.turns].reverse().find((turn) => turn.role === "assistant");
    result.value = (lastAssistant?.answer as ResearchResult | null) ?? null;
  } catch (e) {
    props.onError(String(e));
  }
}

async function newConversation() {
  try {
    const created = (await invoke("conversation_create", {
      workspace: "General",
      title: "Untitled research",
    })) as Conversation;
    await loadConversations();
    await selectConversation(created.id);
  } catch (e) {
    props.onError(String(e));
  }
}

async function deleteConversation() {
  if (selectedId.value === null) return;
  try {
    await invoke("conversation_delete", { conversationId: selectedId.value });
    selectedId.value = null;
    conversation.value = null;
    result.value = null;
    detail.value = null;
    await loadConversations();
  } catch (e) {
    props.onError(String(e));
  }
}

async function refreshConversation() {
  if (selectedId.value === null) return;
  const loaded = (await invoke("conversation_get", {
    conversationId: selectedId.value,
  })) as Conversation;
  conversation.value = loaded;
}

async function ensureConversation(): Promise<number | null> {
  if (selectedId.value !== null) return selectedId.value;
  try {
    const title = question.value.trim().slice(0, 80) || "Untitled research";
    const created = (await invoke("conversation_create", {
      workspace: "General",
      title,
    })) as Conversation;
    selectedId.value = created.id;
    conversation.value = created;
    await loadConversations();
    return created.id;
  } catch (e) {
    props.onError(String(e));
    return null;
  }
}

async function ask() {
  notice.value = "";
  if (!question.value.trim()) {
    notice.value = "Enter a research question.";
    return;
  }
  const sources = [
    sourceEmail.value ? "email" : null,
    sourceFacebook.value ? "facebook" : null,
    sourceDocument.value ? "document" : null,
  ].filter((value): value is string => value !== null);
  if (!sources.length) {
    notice.value = "Choose at least one source.";
    return;
  }
  const conversationId = await ensureConversation();
  if (conversationId === null) return;
  const after = fromDate.value
    ? Math.floor(new Date(`${fromDate.value}T00:00:00Z`).getTime() / 1000)
    : undefined;
  const before = toDate.value
    ? Math.floor(new Date(`${toDate.value}T00:00:00Z`).getTime() / 1000) + 86400
    : undefined;
  const request = {
    question: question.value.trim(),
    sources,
    after,
    before,
    people: splitList(peopleText.value),
    topics: splitList(topicsText.value),
    depth: depth.value,
    context_budget: contextBudget.value,
    per_record_chars: perRecord.value,
    model: model.value.trim() || undefined,
    conversation_id: conversationId,
    scope: collectionId.value ? "collection" : "archive",
    collection_id: collectionId.value ?? undefined,
  };
  try {
    const outcome = await askJob.start("intelligence_ask", { request });
    if (outcome.event === "job_error") {
      props.onError(String(outcome.message || "Research failed"));
      return;
    }
    const research = outcome.result as ResearchResult;
    if (research.cancelled) {
      notice.value = "Research cancelled. The retrieved evidence from this attempt was not saved.";
      return;
    }
    result.value = research;
    await refreshConversation();
    await loadConversations();
    props.onChanged();
  } catch (e) {
    props.onError(String(e));
  }
}

async function checkModels() {
  modelStatus.value = null;
  try {
    const outcome = await modelJob.start("intelligence_models");
    if (outcome.event === "job_error") {
      props.onError(String(outcome.message || "Could not query Ollama"));
      return;
    }
    modelStatus.value = outcome.result;
  } catch (e) {
    props.onError(String(e));
  }
}

async function inspect(item: Evidence) {
  try {
    detail.value =
      item.source === "email"
        ? await invoke("message", { hash: item.id })
        : await invoke("record", { recordId: item.id });
  } catch (e) {
    props.onError(String(e));
  }
}

function inspectCitation(evidenceId: string) {
  const item = evidenceFor(evidenceId);
  if (item) void inspect(item);
}

async function exportConversation() {
  if (selectedId.value === null) return;
  try {
    const destination = await save({
      title: "Export research conversation",
      defaultPath: `research-conversation-${selectedId.value}.json`,
      filters: [{ name: "JSON", extensions: ["json"] }],
    });
    if (!destination || Array.isArray(destination)) return;
    const response = (await invoke("conversation_export", {
      conversationId: selectedId.value,
      path: destination,
    })) as { path: string; turns: number };
    notice.value = `Exported ${response.turns} turn(s) to ${response.path}`;
  } catch (e) {
    props.onError(String(e));
  }
}

async function saveAnswerToJournal() {
  if (!result.value?.answer) {
    notice.value = "There is no grounded answer to save.";
    return;
  }
  const citations = result.value.citations.join(", ") || "none";
  const limitations = result.value.limitations.length
    ? result.value.limitations.join("; ")
    : "none recorded";
  const body =
    `${result.value.answer}\n\n` +
    `Evidence identifiers: ${citations}\n` +
    `Model: ${result.value.model.name || "none"}\n` +
    `Generated: ${new Date().toISOString()}\n` +
    `Limitations: ${limitations}\n\n` +
    `This is a derived research note, not preserved evidence.`;
  try {
    await invoke("journal_save", {
      entryId: null,
      title: question.value.trim().slice(0, 200) || "Research answer",
      body,
      eventDate: null,
    });
    notice.value = "Saved the answer as a journal entry.";
    props.onChanged();
  } catch (e) {
    props.onError(String(e));
  }
}

onMounted(() => {
  void loadStatus();
  void loadConversations();
  void loadCollections();
});
</script>

<template>
  <section>
    <h2>Intelligence</h2>
    <p class="meta">
      Ask a question about your documented history. Retrieval always works; local Ollama inference is optional.
      Answers are derived interpretation and every citation must resolve to supplied evidence.
    </p>
    <p v-if="status" class="status">
      Local AI: <strong>{{ status.enabled ? "enabled" : "disabled" }}</strong>
      · {{ status.endpoint }} · model {{ status.model }}
      <button type="button" :disabled="checking" @click="checkModels">
        {{ checking ? "Checking…" : "Check model" }}
      </button>
      <span v-if="modelStatus" class="meta">
        {{ modelStatus.reachable ? "reachable" : "unreachable" }}
        <template v-if="modelStatus.models?.length"> · {{ modelStatus.models.join(", ") }}</template>
        <template v-if="modelStatus.error"> · {{ modelStatus.error }}</template>
      </span>
    </p>

    <div class="intelligence">
      <aside class="conversations">
        <div class="row">
          <h3>Conversations</h3>
          <button type="button" @click="newConversation">New</button>
        </div>
        <ul>
          <li v-for="item in conversations" :key="item.id">
            <button
              type="button"
              :class="{ active: selectedId === item.id }"
              @click="selectConversation(item.id)"
            >
              <span class="title">{{ item.title }}</span>
              <span class="meta">{{ item.turns }} turns · {{ item.workspace }}</span>
            </button>
          </li>
        </ul>
        <p v-if="!conversations.length" class="meta">No research conversations yet.</p>
      </aside>

      <div class="workspace">
        <form class="question" @submit.prevent="ask">
          <textarea
            v-model="question"
            rows="3"
            placeholder="What did I write about the silver invoice, and how did that change?"
          />
          <div class="row">
            <button type="submit" :disabled="busy">{{ busy ? "Researching…" : "Ask" }}</button>
            <button v-if="busy" type="button" @click="askJob.cancel()">Cancel</button>
            <button type="button" :disabled="!selectedId" @click="exportConversation">
              Export conversation
            </button>
            <button type="button" :disabled="!selectedId" @click="deleteConversation">
              Delete conversation
            </button>
          </div>
        </form>

        <div class="filters">
          <label class="check"><input v-model="sourceEmail" type="checkbox" /> Email</label>
          <label class="check"><input v-model="sourceFacebook" type="checkbox" /> Facebook</label>
          <label class="check"><input v-model="sourceDocument" type="checkbox" /> Documents</label>
          <label class="range">From <input v-model="fromDate" type="date" /></label>
          <label class="range">To <input v-model="toDate" type="date" /></label>
          <label class="range">
            Depth
            <input v-model.number="depth" type="number" min="5" max="200" />
          </label>
          <label class="range">
            Context chars
            <input v-model.number="contextBudget" type="number" min="2000" max="200000" step="1000" />
          </label>
          <label class="range">
            Per record
            <input v-model.number="perRecord" type="number" min="200" max="10000" step="100" />
          </label>
          <label class="range">
            Model
            <input v-model="model" placeholder="Ollama model" />
          </label>
        </div>
        <div class="filters">
          <label class="grow">
            People or organizations (comma separated)
            <input v-model="peopleText" placeholder="alice@example.invalid" />
          </label>
          <label class="grow">
            Topics (comma separated)
            <input v-model="topicsText" placeholder="silver invoice, refund" />
          </label>
          <label class="range">
            Collection scope
            <select v-model="collectionId">
              <option :value="null">Whole archive</option>
              <option v-for="collection in collections" :key="collection.id" :value="collection.id">
                {{ collection.workspace }} / {{ collection.name }}
              </option>
            </select>
          </label>
        </div>

        <p v-if="notice" class="notice">{{ notice }}</p>

        <section v-if="result" class="result">
          <div v-if="result.error" class="warning">{{ result.error }}</div>
          <div v-if="result.warning" class="warning">{{ result.warning }}</div>
          <div v-if="result.insufficient" class="warning">
            The archive does not contain enough evidence for this question in the selected scope.
          </div>

          <div v-if="result.answer" class="answer">
            <h3>Answer</h3>
            <pre>{{ result.answer }}</pre>
            <p class="meta">
              Grounded: {{ result.grounded ? "yes" : "no" }}
              · model used: {{ result.model.used ? result.model.name : "no" }}
              · evidence supplied: {{ result.evidence.length }}
              · context: {{ result.context.characters }}/{{ result.context.budget }} chars
              <span v-if="result.context.omitted"> · {{ result.context.omitted }} record(s) omitted</span>
              <span v-if="result.context.truncated"> · excerpts truncated</span>
              <span v-if="result.retrieval.missing_records">
                · {{ result.retrieval.missing_records }} source record(s) unavailable
              </span>
            </p>
            <button type="button" @click="saveAnswerToJournal">Save answer to journal</button>
          </div>

          <div v-if="result.claims.length" class="claims">
            <h3>Claims and evidence</h3>
            <ul>
              <li v-for="(claim, index) in result.claims" :key="index">
                <span class="kind">{{ claim.kind }}</span>
                {{ claim.text }}
                <button
                  v-for="id in claim.evidence"
                  :key="id"
                  type="button"
                  class="citation"
                  @click="inspectCitation(id)"
                >
                  {{ id }}
                </button>
                <span v-if="!claim.evidence.length" class="warning">no accepted citation</span>
              </li>
            </ul>
          </div>

          <div v-if="result.invalid_citations.length" class="warning">
            Rejected citations (not supplied as evidence):
            {{ result.invalid_citations.join(", ") }}
          </div>
          <div v-if="result.uncited_claims.length" class="warning">
            Claims without accepted evidence: {{ result.uncited_claims.join(" · ") }}
          </div>
          <ul v-if="result.contradictions.length" class="notes">
            <li v-for="item in result.contradictions" :key="item">Contradiction: {{ item }}</li>
          </ul>
          <ul v-if="result.missing.length" class="notes">
            <li v-for="item in result.missing" :key="item">Missing: {{ item }}</li>
          </ul>
          <ul v-if="result.limitations.length" class="notes">
            <li v-for="item in result.limitations" :key="item">Limitation: {{ item }}</li>
          </ul>

          <details v-if="result.queries.length" class="queries">
            <summary>Retrieval queries ({{ result.queries.length }})</summary>
            <ul>
              <li v-for="query in result.queries" :key="query"><code>{{ query }}</code></li>
            </ul>
          </details>

          <h3>Evidence supplied ({{ result.evidence.length }})</h3>
          <ul class="evidence">
            <li v-for="item in result.evidence" :key="item.evidence_id">
              <div class="row">
                <strong>{{ item.evidence_id }}</strong>
                <span class="badge">{{ item.source }}</span>
                <span>{{ item.title }}</span>
                <span class="meta">{{ item.actor }} {{ item.date }}</span>
                <button type="button" @click="inspect(item)">Open record</button>
              </div>
              <p class="meta">
                {{ item.kind }} · {{ item.source_location }} ·
                {{ item.complete ? "complete record" : `excerpt of ${item.characters} characters` }}
              </p>
              <pre class="excerpt">{{ item.excerpt }}</pre>
            </li>
          </ul>
        </section>

        <section v-if="conversation?.turns.length" class="transcript">
          <h3>Conversation history</h3>
          <ul>
            <li v-for="turn in conversation.turns" :key="turn.id">
              <span class="badge">{{ turn.role }}</span>
              <span class="meta">{{ turn.created_at }} {{ turn.model_name || "" }}</span>
              <pre>{{ turn.content }}</pre>
            </li>
          </ul>
        </section>

        <section v-if="detail" class="detail">
          <h3>{{ detail.subject || detail.source_key || detail.record_kind }}</h3>
          <p class="meta">{{ detail.sender || detail.actor }} {{ detail.date || detail.occurred_at }}</p>
          <div v-if="detail.attachments?.length" class="attachments">
            <h4>Attachments (stored metadata)</h4>
            <ul>
              <li v-for="(attachment, index) in detail.attachments" :key="index">
                {{ attachment.filename || attachment.name || attachment.title || attachment.uri }}
                <span v-if="attachment.mime"> · {{ attachment.mime }}</span>
              </li>
            </ul>
          </div>
          <pre>{{ detail.body }}</pre>
        </section>
      </div>
    </div>
  </section>
</template>

<style scoped>
.intelligence {
  display: flex;
  gap: 16px;
  align-items: flex-start;
}
.conversations {
  width: 260px;
  flex-shrink: 0;
}
.conversations ul,
.evidence,
.transcript ul,
.claims ul,
.queries ul,
.notes {
  list-style: none;
  margin: 0;
  padding: 0;
}
.conversations li {
  margin-bottom: 4px;
}
.conversations button {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 2px;
  text-align: left;
  padding: 6px 8px;
  background: transparent;
  border: 1px solid transparent;
  cursor: pointer;
}
.conversations button.active {
  border-color: var(--hb-border-strong);
  background: var(--hb-panel-alt);
}
.title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.workspace {
  flex: 1;
  min-width: 0;
}
.question textarea {
  width: 100%;
  padding: 8px;
  font-family: var(--hb-font);
  border: 1px solid var(--hb-border-strong);
  background: var(--hb-workspace);
  resize: vertical;
}
.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: flex-end;
  margin: 10px 0;
}
.grow {
  flex: 1;
  min-width: 220px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 12px;
}
.range {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--hb-text-secondary);
}
.range input,
.range select,
.grow input {
  padding: 4px 6px;
  border: 1px solid var(--hb-border);
  background: var(--hb-workspace);
}
.row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.status {
  color: var(--hb-text-secondary);
  font-size: 12px;
}
.answer pre,
.excerpt,
.detail pre,
.transcript pre {
  white-space: pre-wrap;
  background: var(--hb-panel-alt);
  padding: 10px;
  margin: 6px 0;
}
.excerpt {
  max-height: 180px;
  overflow: auto;
}
.result,
.transcript,
.detail {
  margin-top: 18px;
}
.evidence li,
.transcript li,
.claims li {
  border-top: 1px solid var(--hb-border);
  padding: 8px 0;
}
.badge,
.kind {
  display: inline-block;
  padding: 1px 6px;
  margin-right: 6px;
  border: 1px solid var(--hb-border);
  border-radius: var(--hb-radius);
  font-size: 11px;
  text-transform: uppercase;
  color: var(--hb-text-secondary);
}
.citation {
  margin-left: 4px;
  padding: 0 5px;
  border: 1px solid var(--hb-border);
  background: var(--hb-panel-alt);
  color: var(--hb-link);
  cursor: pointer;
}
.warning {
  color: var(--hb-warning-text);
  border-left: 3px solid var(--hb-warning);
  padding: 6px 10px;
  margin: 8px 0;
}
.notice {
  color: var(--hb-success-text);
}
.meta {
  color: var(--hb-text-secondary);
  font-size: 12px;
}
</style>
