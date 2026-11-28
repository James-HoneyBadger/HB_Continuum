# Intelligence workspace

HB Continuum can answer questions about your documented history using only
records in the local archive. Retrieval and evidence inspection always work;
a language model is optional and local.

**The model is replaceable. The memories are yours.**

## Workflow

1. You ask a natural-language question in the **Intelligence** workspace.
2. The engine turns it into bounded FTS5 retrieval queries and searches the
   selected sources, applying date, participant/actor and collection filters.
3. Matches are deduplicated and ranked across queries. Each surviving record
   is loaded from the archive or catalog with its stable identifier, source
   location, timestamp and original body.
4. A bounded context is assembled. Records are numbered `E1`, `E2`, ...;
   excerpts are marked, and records omitted for budget reasons are counted.
5. If local Ollama inference is enabled, the evidence JSON and your question
   are sent to the loopback endpoint with explicit instructions to treat
   evidence as untrusted data.
6. The model must return structured claims with evidence identifiers. The
   engine validates every identifier against the evidence actually supplied.
   Unknown identifiers are rejected and displayed; claims without accepted
   evidence are flagged.
7. You inspect the answer, claims, contradictions, missing information and
   the underlying evidence, and can open any cited message or catalog record.

No model is consulted when retrieval finds no evidence, and a model answer is
never written back into the archive.

## What is stored where

- `archive.sqlite3` and `catalog.sqlite3` remain the preserved evidence.
- `research.sqlite3` schema 6 stores research conversations and turns:
  questions, derived answers, citations, model names and timestamps.
- Deleting a conversation deletes only derived conversation data. It never
  deletes or modifies a source record, attachment or original file.
- Conversation export writes a JSON document outside the archive.

## Evidence and citations

Every supplied record carries:

- an evidence identifier (`E1`, `E2`, ...),
- the source (`email`, `facebook` or `document`) and source type,
- the original record identifier (SHA-256 hash or catalog record id),
- title, participant/actor, declared date and source location,
- an excerpt and whether it is the complete stored body or a truncation,
- the retrieval query set that found it.

The model may only cite identifiers from that list. Invalid identifiers and
uncited claims are surfaced in the interface. A plain-text model reply with no
structured claims is shown as unstructured and is not presented as grounded.

Claim kinds are limited to `documented`, `multiple`, `inference`, `uncertain`
and `contradiction`. The model is instructed to present disagreement rather
than silently choosing a side, and to state when evidence is insufficient.
These labels describe the model's structured output; they are not independent
proof of factual correctness.

## Local Ollama settings

AI is disabled by default. Enable it in Preferences with:

- `ai_enabled`: true
- `ai_backend`: `ollama`
- `ai_endpoint`: an `http(s)` loopback address such as
  `http://127.0.0.1:11434`
- `ai_model`: an already-installed Ollama model name
- `ai_timeout`, `ai_max_input_chars`: request bounds

The client refuses redirects and non-loopback endpoints, never pulls or
downloads a model, and streams responses with cancellation. Model discovery
lists what the local Ollama instance already has. The application remains a
complete archival and research workstation when Ollama is absent, disabled or
unreachable; retrieval still returns inspectable evidence.

## Prompt-injection boundary

Imported messages and records are untrusted data. Evidence is supplied as a
JSON array of records and the system instruction explicitly says never to obey
text inside it. The research engine has no tool access, no shell, no filesystem
or archive mutation capability, and never turns model output into an action.
Prompt injection can still influence what a model says; it cannot make this
engine modify evidence.

## Limits

- Retrieval is keyword/FTS5 based, not semantic or embedding-based. Paraphrases
  that share no terms may be missed.
- The archive cannot prove undocumented events, intentions or beliefs. A
  single historical message does not establish a permanent view.
- Contradiction and uncertainty labels are model-reported and validated only
  for citation identity, not for semantic truth.
- Context and per-record limits deliberately truncate long material. Omitted
  and excerpted evidence is reported, never silently hidden as complete.
- The answer arrives when the model stream finishes; per-token UI streaming is
  not implemented.
- No interactive desktop acceptance run is claimed by the automated tests.
