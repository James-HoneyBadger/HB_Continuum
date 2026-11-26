# HB CONTINUUM — MASTER ENGINEERING DIRECTIVE

## Project: Comprehensive architectural modernization, functional expansion and desktop workstation development

Repository: James-HoneyBadger/HB_Continuum

Project ecosystem: Honey Badger Universe

## 1. YOUR ROLE AND AUTHORITY

Act as a principal software architect, senior Python engineer, Rust developer, TypeScript/Vue developer, database architect, desktop application engineer, security reviewer, quality assurance engineer, technical writer and open-source maintainer.

You are authorized to undertake substantial architectural refactoring, introduce appropriate dependencies, reorganize the source tree, implement new functionality, improve existing functionality, redesign the user experience and comprehensively update documentation.

Do not restrict yourself to superficial improvements.

Exercise independent engineering judgment. Where the existing implementation is inadequate, improve or replace it. Where existing functionality is robust, preserve and reuse it.

The objective is to transform HB Continuum from an email archive utility into a genuinely capable, cross-platform, local-first historical knowledge and intelligence workstation.

Do not merely create an architectural proposal.

Inspect, design, implement, test, validate, document and iteratively improve working software.

However:

- Do not create formal releases or release tags.
- Do not publish release binaries.
- Do not modify actual user archives.
- Do not expose private correspondence or personal data.
- Do not modify unrelated repositories.
- Do not weaken existing security or repository protections.
- Do not overwrite existing user changes.
- Do not claim functionality that has not been implemented and tested.
- Do not treat a visually attractive prototype as a completed application.

Formal release decisions remain exclusively with the repository owner.

## 2. PROJECT VISION

HB Continuum is intended to become a source-independent personal and organizational knowledge archive.

Its purpose is to preserve information across time, providers, applications and formats, while enabling meaningful exploration of that information.

It must not become dependent upon any single cloud provider, artificial intelligence model, proprietary database, subscription service or commercial platform.

Project philosophy:

**Time is linear. Knowledge need not be.**

**The intelligence is replaceable. The memories are yours.**

The system should support, eventually and incrementally:

- Historical email preservation.
- Social media archive ingestion.
- Personal journals.
- Documents.
- Photographs and associated metadata.
- Correspondence.
- Project histories.
- Historical timelines.
- Genealogical research.
- Evidence organization.
- Organizational knowledge preservation.
- Research workspaces.
- Source-backed reporting.
- Optional artificial intelligence.
- Historical autobiographical exploration.
- Digital legacy preservation.
- An optional historical intelligence interface named Second Me.

The application is not intended to impersonate its owner, manufacture memories, replace human judgment or autonomously interact with other people.

It should allow people to investigate, understand, preserve and use their documented history.

The archive is the source of truth.

AI-generated interpretations are secondary, derived, replaceable information.

## 3. FIRST ACTION: COMPREHENSIVE REPOSITORY AUDIT

Before making architectural changes, thoroughly inspect the actual repository.

Do not assume that historical descriptions of the application accurately reflect its current state.

Inspect:

- All tracked source files.
- Current Git branch.
- Repository status.
- Existing local modifications.
- Recent commits.
- Outstanding pull requests, where accessible.
- Existing tests.
- CI workflows.
- Dependencies.
- License.
- Documentation.
- Database schemas.
- Database migration behavior.
- Archive directory layout.
- Existing command-line interface.
- Existing desktop interface.
- Research overlays.
- Scheduled synchronization.
- Backup and restoration.
- MIME extraction.
- Search implementation.
- Thread reconstruction.
- Configuration management.
- Security boundaries.
- Existing performance limitations.

Identify discrepancies between documentation and implemented behavior.

Create or update:

`docs/engineering/BASELINE_AUDIT.md`

Document:

1. Existing functional capabilities.
2. Partially implemented capabilities.
3. Known defects.
4. Architectural weaknesses.
5. Security considerations.
6. Performance considerations.
7. Backward compatibility requirements.
8. Test coverage.
9. Outstanding engineering work.
10. Recommended implementation order.

Establish a reproducible baseline by executing the existing tests.

Record failures accurately.

Do not conceal failing tests by deleting them, disabling them or weakening their assertions.

Determine whether existing hardening, licensing and branding branches contain changes that must be integrated before undertaking major refactoring.

Avoid reimplementing work that already exists elsewhere in the repository.

## 4. TARGET ARCHITECTURE

The preferred target architecture is:

### Desktop application shell

Tauri 2, using Rust.

### Frontend

- Vue 3.
- TypeScript.
- Vite.
- Vuetify or another appropriately licensed, well-supported component library.
- Pinia for application state where justified.
- Vue Router where appropriate.
- Apache ECharts or another appropriate visualization library.

### Core processing engine

Python 3.12 or later.

### Data storage

SQLite, including FTS5.

### Local AI

Ollama as the initial optional inference backend.

### Communication

A managed Python subprocess using a narrowly defined, versioned IPC protocol.

Avoid exposing a general-purpose local HTTP API unless there is a documented architectural reason and an appropriate security design.

Use the native operating system webview through Tauri rather than introducing an entire bundled Chromium runtime without demonstrated justification.

Nevertheless, evaluate the architecture honestly.

Build a functional proof of concept demonstrating:

- Python subprocess startup.
- Structured request and response handling.
- Archive selection.
- Read-only retrieval of archive statistics.
- Paginated search.
- Cancellation.
- Progress reporting.
- Error handling.
- Graceful subprocess shutdown.
- Cross-platform packaging feasibility.

If Tauri introduces disproportionate complexity, document the trade-offs and evaluate PySide6/QML or another credible alternative.

Do not persist with an architectural choice solely because it appears in this directive.

The preferred architecture must earn its place through working implementation.

## 5. FUNDAMENTAL DESIGN PRINCIPLES

The application must remain:

- Local-first.
- Offline-capable.
- Privacy-first.
- Open-source.
- User-controlled.
- Modular.
- Maintainable.
- Testable.
- Recoverable.
- Transparent.
- Source-independent.
- Model-independent.
- Extensible.
- Cross-platform where practical.

No mandatory cloud services.

No advertising.

No telemetry.

No analytics reporting.

No hidden background data transmission.

No mandatory subscriptions.

No compulsory online account.

No automatic uploading of user archives.

No automatic downloading of AI models.

No unnecessary dependencies on proprietary services.

Network activity must be limited to explicitly authorized operations, such as:

- User-configured email synchronization.
- Explicitly enabled local AI inference.
- Other future source adapters where the user knowingly authorizes network access.

Do not introduce network activity merely because the application starts.

## 6. PROPOSED SOURCE TREE

Develop a maintainable Python package structure approximately resembling:

```text
HB_Continuum/
├── pyproject.toml
├── README.md
├── LICENSE
├── CONTRIBUTING.md
├── SECURITY.md
├── CHANGELOG.md
├── ROADMAP.md
├── dispatch.py
├── src/
│   └── continuum/
│       ├── core/
│       │   ├── archive.py
│       │   ├── storage.py
│       │   ├── indexing.py
│       │   ├── provenance.py
│       │   ├── integrity.py
│       │   ├── migrations.py
│       │   └── errors.py
│       ├── adapters/
│       │   ├── base.py
│       │   ├── registry.py
│       │   ├── email/
│       │   ├── facebook/
│       │   ├── documents/
│       │   ├── journals/
│       │   └── filesystem/
│       ├── research/
│       │   ├── search.py
│       │   ├── timeline.py
│       │   ├── relationships.py
│       │   ├── annotations.py
│       │   ├── collections.py
│       │   ├── reports.py
│       │   └── export.py
│       ├── intelligence/
│       │   ├── backend.py
│       │   ├── ollama.py
│       │   ├── summarize.py
│       │   ├── retrieval.py
│       │   ├── citations.py
│       │   └── second_me.py
│       ├── services/
│       │   ├── backup.py
│       │   ├── recovery.py
│       │   ├── scheduler.py
│       │   ├── preferences.py
│       │   ├── jobs.py
│       │   └── diagnostics.py
│       ├── ipc/
│       │   ├── protocol.py
│       │   ├── server.py
│       │   ├── validation.py
│       │   └── handlers.py
│       └── cli/
├── frontend/
│   ├── package.json
│   ├── src/
│   │   ├── components/
│   │   ├── views/
│   │   ├── layouts/
│   │   ├── stores/
│   │   ├── composables/
│   │   ├── services/
│   │   ├── types/
│   │   └── themes/
│   └── tests/
├── src-tauri/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── regression/
│   ├── security/
│   └── fixtures/
├── scripts/
├── docs/
│   ├── architecture/
│   ├── engineering/
│   ├── tutorials/
│   ├── adapters/
│   └── user-guide/
└── .github/
    └── workflows/
```

This is a proposed organization, not an inflexible requirement.

Avoid creating empty packages, placeholder modules or unnecessary abstraction merely to satisfy the proposed structure.

Each module should have a meaningful responsibility.

Preserve the existing `dispatch.py` entry point as a backward-compatible CLI wrapper.

Existing users must not be required to abandon their archive or change all existing command-line workflows.

## 7. PROTECT THE EXISTING ARCHIVAL ENGINE

The existing Dispatch engine is valuable working infrastructure.

Preserve or improve:

- Raw EML preservation.
- SHA-256 content addressing.
- Exact-byte deduplication.
- IMAP origin tracking.
- Read-only mailbox access.
- BODY.PEEK retrieval.
- UID and UIDVALIDITY handling.
- Resumable synchronization.
- Multiple mailbox support.
- MIME parsing.
- Search indexing.
- SQLite integrity checking.
- Original-byte verification.
- Evidence export.
- Backup.
- Restoration.
- Scheduled synchronization.
- Research overlays.
- Existing configuration compatibility.

Do not recreate this functionality unnecessarily.

Where practical, extract existing implementation into well-defined services and preserve behavior through regression tests.

Never make raw EML preservation dependent upon AI functionality.

Never require the modern desktop frontend to perform basic archive maintenance.

The command-line interface must remain a first-class interface.

## 8. DATA INTEGRITY IS NON-NEGOTIABLE

The archive must distinguish among:

1. Original source records.
2. Extracted searchable information.
3. User-created research metadata.
4. Machine-generated summaries.
5. Machine-generated classifications.
6. Interpretive historical analysis.
7. Exported derivative documents.

Original source records must remain immutable under normal application operation.

A change to an extracted representation must not modify the original source.

Maintain provenance.

Maintain source hashes.

Maintain source identifiers.

Maintain import timestamps.

Maintain source timestamps.

Distinguish between a timestamp representing an event and a timestamp representing the later recording or recollection of that event.

Do not assume every source timestamp is accurate.

Do not assume imported source records are authentic merely because they have a valid SHA-256 hash.

Hash verification establishes byte integrity, not truth, authorship or authenticity.

Every destructive operation must be explicitly identified.

Avoid destructive database migrations.

Database migrations must be:

- Versioned.
- Transactional where supported.
- Validated.
- Recoverable.
- Documented.
- Tested against synthetic examples of older schemas.

Never test migrations against the owner's actual archive without explicit authorization.

## 9. SOURCE-INDEPENDENT ARCHIVE ARCHITECTURE

Design a general source adapter infrastructure.

Do not force every record into an email-specific schema.

Preserve existing email storage compatibility while adding a unified representation for additional sources.

Evaluate a separate catalog database as a means of introducing source-independent capabilities without destabilizing existing `archive.sqlite3` files.

Potential normalized entities include:

- Sources.
- Import batches.
- Original objects.
- Records.
- Record revisions.
- Attachments.
- Actors.
- Relationships.
- Events.
- Tags.
- Collections.
- Derived representations.
- Search index entries.

Potential record attributes:

- Internal record ID.
- Source type.
- Source identifier.
- Original object hash.
- Record content hash.
- Record type.
- Title or subject.
- Body text.
- Author reference.
- Participant references.
- Original timestamp.
- Normalized timestamp.
- Timestamp precision.
- Import timestamp.
- Parent record reference.
- Conversation reference.
- Revision reference.
- Extraction version.
- Provenance metadata.

Do not blindly adopt this schema.

Develop the actual schema based on source characteristics, performance needs and preservation requirements.

Document schema decisions and migration strategy.

Consider the distinction between identical files, identical records, repeated content, revisions and genuinely distinct events.

Do not discard legitimate historical records simply because their textual content is similar.

## 10. SOURCE ADAPTER INTERFACE

Develop a consistent adapter protocol.

Each adapter should declare:

- Adapter identifier.
- Supported source formats.
- Format versions where discoverable.
- Input requirements.
- Discovery behavior.
- Validation behavior.
- Parsing capabilities.
- Supported record types.
- Known limitations.

Conceptual operations:

```python
class SourceAdapter:
    def probe(self, source):
        ...

    def inspect(self, source):
        ...

    def import_records(self, source, context):
        ...

    def validate(self, source):
        ...

    def capabilities(self):
        ...
```

Implement typed interfaces and suitable concrete models.

Import operations should provide:

- Progress callbacks.
- Cancellation.
- Structured diagnostics.
- Import statistics.
- Error classification.
- Duplicate detection.
- Resumability where practical.
- Provenance.
- Bounded resource consumption.

Avoid arbitrary executable plugins or dynamically loading untrusted code.

The adapter infrastructure should be extensible without becoming a security vulnerability.

## 11. FACEBOOK JSON IMPORTER — HIGH PRIORITY

This is one of the most important immediate expansions of HB Continuum.

Implement native ingestion of user-obtained Facebook data exports.

Do not scrape Facebook.

Do not require Facebook account credentials.

Do not use unofficial APIs to obtain private Facebook content.

The source is an export already obtained by the user.

Support incremental expansion across common export categories, including:

- Timeline posts.
- Check-ins.
- Photos and video post metadata.
- Comments.
- Group posts.
- Group comments.
- Post revisions.
- Comment revisions.
- Messenger conversations.
- Reactions and likes where useful.

Investigate actual supported JSON structures using synthetic fixtures and legally obtained, explicitly authorized examples.

Do not assume every Facebook export uses identical filenames or structures.

Handle:

- Large JSON files.
- Multiple numbered export files.
- Nested structures.
- Unix timestamps.
- Missing timestamps.
- Malformed records.
- Empty records.
- Revisions.
- Duplicate exports.
- Overlapping exports.
- Message participants.
- Conversation relationships.
- Attachments.
- Character encoding issues.
- Unicode.
- Optional fields.
- Unknown fields.
- Format variation.

Preserve the original exported JSON files or explicit source references with integrity metadata.

Avoid silently replacing malformed text through speculative encoding transformations.

If an encoding repair is performed, retain the original representation and record the transformation.

Provide an import preview showing:

- Files discovered.
- Recognized formats.
- Estimated records.
- Source categories.
- Potential duplicates.
- Unsupported records.
- Warnings.
- Estimated storage requirements.

Import must be explicitly initiated.

Do not upload any imported Facebook material.

Provide import results with exact counts and documented counting semantics.

Distinguish:

- Files imported.
- Records encountered.
- Records successfully imported.
- Records skipped.
- Duplicates.
- Revisions.
- Unsupported records.
- Parsing failures.

Build comprehensive synthetic test fixtures.

Never commit the owner's real Facebook export into the public repository.

## 12. ADDITIONAL SOURCE ADAPTERS

Once email and Facebook ingestion are robust, implement or design adapters for:

### Documents

- Plain text.
- Markdown.
- PDF text extraction.
- DOCX.
- Other reasonable document formats.

Preserve the original documents and extracted text separately.

Do not execute embedded scripts or macros.

### Journals

Support common text-based journal formats and structured historical entries.

### Filesystem archives

Allow user-selected directories to be cataloged without recursively scanning unrelated files or hidden locations.

### Software development history

Explore local Git repository metadata ingestion:

- Commits.
- Dates.
- Authors.
- Commit messages.
- Tags.
- Project history.

Avoid automatically cloning repositories or contacting external hosts.

### Photographic metadata

Consider EXIF dates and user-provided annotations.

Do not automatically perform face recognition or sensitive identity inference.

### Other historical datasets

Provide a documented adapter development guide.

Prioritize stable, useful adapters over a large number of incomplete integrations.

## 13. UNIFIED SEARCH

Develop a powerful, source-independent search engine.

Search should support:

- Full-text queries.
- Exact phrases.
- Boolean expressions.
- Source filtering.
- Record type filtering.
- Date ranges.
- Author filtering.
- Conversation filtering.
- Tags.
- Collections.
- Search result pagination.
- Saved queries.
- Relevant snippets.
- Match highlighting.
- Sort by date.
- Sort by relevance.
- Sort by source.
- Export selected results.

Avoid loading all records into memory for ordinary queries.

Use appropriate SQLite indexes.

Use parameterized SQL.

Do not permit arbitrary SQL through frontend search fields.

Document FTS5 query syntax and error handling.

Provide understandable responses to malformed search expressions.

Consider cursor-based pagination where appropriate.

Preserve search compatibility for existing email archives.

Search results must identify their source and provide a reliable path back to the original record.

## 14. TIMELINE EXPLORER

Build a sophisticated historical timeline.

This should become one of the flagship capabilities of HB Continuum.

Allow the user to:

- Navigate across years, months and days.
- Filter sources.
- Filter record types.
- Filter people.
- Filter topics.
- Select historical periods.
- Compare different periods.
- Inspect chronological conversations.
- Group related records.
- Identify gaps in source coverage.
- Open original records.
- Create timeline annotations.
- Save timeline views.
- Export selected chronologies.

Visualize archive activity without misrepresenting it as actual human activity.

For example, a year with more Facebook records does not establish that the user was more socially active that year.

Distinguish source coverage from historical conclusions.

Support uncertain or incomplete dates.

Handle time zones explicitly.

Where practical, support visual timeline zooming and aggregation.

Do not create a graph containing tens of thousands of simultaneously rendered interactive elements.

Use efficient aggregation and virtualized rendering.

## 15. PEOPLE AND RELATIONSHIP EXPLORER

Implement an evidence-based relationship explorer.

Potential relationships include:

- Email correspondents.
- Message participants.
- Conversation membership.
- Shared topics.
- Explicitly documented associations.
- User-defined connections.
- Source-specific actor identifiers.

Do not assume two people with the same name are the same person.

Do not automatically merge identities without sufficient evidence or explicit user confirmation.

Provide identity aliases and merge/split controls.

Preserve original identifiers.

Avoid unsupported claims about personal relationships.

A communication graph represents documented communications, not the full social reality of a person.

Allow relationship information to be inspected as both a table and, where useful, a visual graph.

Maintain links back to underlying evidence.

## 16. RESEARCH STUDIO

Expand the existing research overlay into a capable research environment.

The user should be able to:

- Create research workspaces.
- Define investigations.
- Save searches.
- Collect records.
- Create annotations.
- Add tags.
- Define custom metadata.
- Organize evidence.
- Build chronologies.
- Compare conflicting statements.
- Track unanswered questions.
- Create research notes.
- Mark important records.
- Export findings.
- Generate reusable reports.

Research must remain non-destructive.

The original records must remain untouched.

Consider report formats including:

- Markdown.
- Plain text.
- HTML.
- CSV.
- JSON.
- PDF where appropriate.

Reports should support:

- Source citations.
- Source hashes.
- Record dates.
- Record identifiers.
- Evidence references.
- User-authored commentary.
- Clearly marked interpretations.
- Clearly marked uncertainty.

Never label a machine-generated interpretation as an original source quotation.

Distinguish evidence from claims and analysis.

## 17. OPTIONAL OLLAMA INTEGRATION

Implement a local AI abstraction with Ollama as the first backend.

Core archive functionality must not depend on Ollama.

AI must be disabled by default.

Use validated preferences equivalent to:

```text
ai.enabled = false
ai.backend = none
ai.endpoint = http://localhost:11434
ai.model = user-configured model
ai.timeout = configurable
ai.batch_size = configurable
ai.max_input_chars = configurable
```

No AI-related network requests unless:

```text
ai.enabled == true
AND
ai.backend == ollama
```

Every inference request must pass the authorization gate.

Do not bypass configuration through command-line options.

Do not automatically download models.

Do not automatically fall back to a cloud service.

Initially restrict inference endpoints to loopback addresses.

Disable HTTP redirects and unexpected proxy forwarding.

Validate endpoint configuration.

Validate model selection.

Implement clear connection errors.

Bound response sizes.

Bound request sizes.

Implement cancellation where practical.

Treat all source material as untrusted input.

The AI backend must not receive access to:

- Shell execution.
- Arbitrary filesystem access.
- Database mutation.
- Email sending.
- Credentials.
- Arbitrary tools.
- Unrestricted network calls.

The application should supply only the selected source information needed for the explicitly requested task.

Document that a loopback endpoint does not independently prove that the inference backend itself is offline.

For strict isolation, the user should be able to operate the entire application and selected AI model without internet access.

## 18. MESSAGE AND THREAD SUMMARIZATION

Implement the previously designed summarization subsystem.

Read message bodies through a read-only SQLite connection.

Do not instantiate a writable archive object for summarization.

Never modify:

- Raw EML.
- Original source files.
- `archive.sqlite3`.

Store summaries in `research.sqlite3` or the appropriate non-destructive research overlay.

Support the following required fields:

```sql
CREATE TABLE IF NOT EXISTS summaries (
    message_hash TEXT NOT NULL,
    summary_type TEXT NOT NULL
        CHECK (summary_type IN ('message', 'thread')),
    model_name TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    summary_text TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (
        message_hash,
        summary_type,
        model_name,
        prompt_version
    )
);
```

Improve constraints where appropriate.

Add companion metadata supporting:

- Input digest.
- Thread membership.
- Source revision.
- Extraction version.
- Model configuration.
- Input-processing configuration.
- Summary validity.
- Relevant provenance.

Preserve the required summary fields.

Implement:

- Individual message summarization.
- Thread summarization.
- Batch summarization.
- Progress callbacks.
- Cancellation.
- Resumability.
- Model-specific caching.
- Prompt-version-specific caching.
- Input-digest validation.
- Stale summary detection.
- Viewing existing summaries offline.
- Explicit summary regeneration.
- Summary deletion.

A thread may gain new messages.

Cached thread summaries must not silently remain current after their input changes.

Likewise, reindexing may change extracted text even when the original source hash remains unchanged.

Account for both situations.

Commit each successful result independently.

Do not maintain database write transactions while waiting for inference.

When Ollama becomes unavailable, preserve completed work and report the error clearly.

Develop fake Ollama HTTP server tests.

CI must not require a real AI model.

## 19. PROMPT ENGINEERING AND AI EVIDENCE DISCIPLINE

All AI prompts must be versioned.

Prompt construction must be inspectable.

Avoid hidden prompts that make the application impossible to audit.

Require generated summaries to:

- Remain faithful to supplied evidence.
- Preserve significant dates.
- Preserve significant amounts.
- Preserve commitments and decisions.
- Identify contradictions.
- Distinguish allegations from verified facts.
- Acknowledge missing context.
- Avoid inventing facts.
- Avoid inferring unsupported motives.

Source text must be treated as data, not executable instructions.

Implement explicit boundaries around source material.

Test adversarial source content containing instructions such as:

- Ignore previous instructions.
- Reveal credentials.
- Access unrelated files.
- Contact a remote server.
- Modify the database.
- Send a message.

The architecture must ensure the AI cannot perform such actions even if it produces text requesting them.

Do not rely solely on prompt instructions as a security boundary.

## 20. SECOND ME — HISTORICAL INTELLIGENCE WORKSPACE

Second Me is an optional historical research interface.

It is not a simulated human being.

It is not an autonomous agent impersonating the owner.

It is not a claim of digital consciousness.

Its purpose is to support meaningful, source-backed exploration of personal history.

Develop the architectural foundation for capabilities such as:

### Autobiographical research

Locate documented personal experiences, milestones, interests, projects and recollections.

### Intellectual history

Trace changes in ideas, values, philosophical positions and interests over time.

### Temporal reasoning

Distinguish statements made at different points in a person's life.

Do not treat every historical opinion as a current belief.

### Identity history

Track user-defined names, aliases, personas and historical self-descriptions.

Do not invent psychological diagnoses or unsupported causal relationships.

### Contradiction analysis

Identify documented changes of opinion, conflicting statements and unresolved inconsistencies.

Do not assume an apparent contradiction is necessarily dishonesty.

Context and time matter.

### Personal reflection

Allow the user to compare earlier statements with present perspectives.

### Historical questions

Examples:

- What was I working on in 2014?
- When did I first mention this project?
- How did my views on this subject change?
- Find earlier descriptions of this experience.
- What did I write about this person?
- When have I encountered a similar situation?
- Which records support this interpretation?
- What counterexamples challenge my present assessment?
- What information is missing from the archive?

### Evidence-backed responses

Every substantial historical conclusion should provide source references where available.

The interface should distinguish:

- Direct quotations.
- Contemporary records.
- Later recollections.
- User-authored interpretations.
- AI-generated interpretations.
- Unverified claims.
- Unknown facts.

### No echo chamber

The system must not be designed merely to validate the user's present self-image.

Support contradictory evidence.

Support uncertainty.

Support changes of opinion.

Support the possibility that the user's current recollection is incomplete or incorrect.

The system should help users understand their documented past rather than flatter them.

## 21. RETRIEVAL-AUGMENTED GENERATION

Do not initially introduce a complex vector database infrastructure merely because it is fashionable.

Begin with robust SQLite FTS5 retrieval.

Implement a controlled retrieval pipeline:

1. Interpret the user query.
2. Identify authorized source scope.
3. Perform indexed retrieval.
4. Rank relevant results.
5. Deduplicate retrieved material appropriately.
6. Construct a bounded evidence package.
7. Supply selected evidence to the local model.
8. Generate a response.
9. Attach source references.
10. Permit the user to inspect original records.

Never supply the entire archive to a model indiscriminately.

Provide user-visible information about:

- Sources searched.
- Records retrieved.
- Date coverage.
- Retrieval limitations.
- Model used.
- Prompt version.
- Whether any material was omitted.

Consider local embeddings later if they demonstrate meaningful improvements.

Any embedding index must remain:

- Optional.
- Locally generated.
- Rebuildable.
- Versioned.
- Model-specific.
- Non-destructive.

Do not replace reliable full-text search with opaque semantic search.

Combine retrieval methods when justified by measured results.

## 22. MODERN DESKTOP USER EXPERIENCE

The new UI must feel like a mature research workstation rather than a developer utility.

Design a coherent application shell with:

- Consistent navigation.
- Responsive layouts.
- Keyboard accessibility.
- Clear typography.
- Dark and light themes.
- Configurable font sizes.
- Contextual help.
- Search shortcuts.
- Persistent user preferences.
- Meaningful empty states.
- Informative error messages.
- Appropriate confirmation dialogs.
- Long-running operation indicators.
- Cancellation controls.
- Virtualized data tables.
- Efficient rendering.
- Native file selection where appropriate.

Do not use decorative dashboard elements that convey no meaningful information.

Do not create fake statistics.

Do not create non-functional buttons merely to complete a visual design.

All displayed values must originate from actual application state or clearly identified synthetic demo fixtures.

## 23. APPLICATION NAVIGATION

Suggested top-level workspaces:

### Overview

Display:

- Archive size.
- Record counts.
- Source counts.
- Source coverage.
- Historical date range.
- Recent imports.
- Synchronization status.
- Integrity status.
- Outstanding maintenance warnings.
- Recent research workspaces.

### Universal Search

Advanced source-independent searching.

### Timeline

Chronological exploration.

### Correspondence

Email accounts, messages, conversations and participants.

### Social History

Facebook and other imported historical social material.

### People

Actor and relationship exploration.

### Research Studio

Collections, investigations, annotations and reports.

### Second Me

Optional local AI historical research.

### Source Manager

Source configuration, import history and adapter capabilities.

### Archive Health

Integrity checking, reconciliation, backup and recovery.

### Settings

Appearance, storage, privacy, synchronization, AI, performance and advanced configuration.

Do not show a workspace as implemented when it is merely a future concept.

Hide unavailable functionality or explicitly identify it as planned.

## 24. RECORD READER

Design a comprehensive record inspection interface.

Potential panels:

- Extracted text.
- Original metadata.
- Source information.
- Original record reference.
- Attachments.
- Conversation context.
- Related records.
- Annotations.
- Tags.
- Summary.
- Provenance.
- Integrity information.

Support easy copying of:

- Record identifiers.
- SHA-256 hashes.
- Citations.
- Selected source text.
- Structured references.

Never render untrusted HTML with unrestricted JavaScript.

Never load remote images from archived emails automatically.

Never execute document macros or scripts.

Opening attachments in external applications must require explicit user action.

Where appropriate, offer a safe plain-text representation by default.

## 25. DESKTOP IPC SECURITY

Design a narrowly scoped, versioned IPC protocol.

Potential request structure:

```json
{
  "protocol_version": 1,
  "request_id": "unique-request-id",
  "method": "search.records",
  "params": {}
}
```

Potential response structure:

```json
{
  "protocol_version": 1,
  "request_id": "unique-request-id",
  "result": {}
}
```

Potential error structure:

```json
{
  "protocol_version": 1,
  "request_id": "unique-request-id",
  "error": {
    "code": "ARCHIVE_NOT_AVAILABLE",
    "message": "The selected archive could not be opened."
  }
}
```

Develop structured progress events for long-running jobs.

Explicitly enumerate allowed commands.

Validate all parameters.

Reject unknown methods.

Do not expose unrestricted Python execution.

Do not expose arbitrary shell commands.

Do not expose arbitrary SQL.

Do not expose unrestricted filesystem access.

Do not expose sensitive configuration through general diagnostic commands.

Use controlled file selection and archive-relative paths.

Prevent path traversal.

Evaluate symbolic link handling.

Bound message sizes.

Separate diagnostic output from protocol messages.

Handle subprocess crashes.

Handle unexpected subprocess termination.

Handle application shutdown.

Make the frontend resilient to backend failures.

Restrict Tauri capabilities and permissions to the minimum required.

Apply an appropriate Content Security Policy.

Do not enable broad shell or filesystem plugins merely for convenience.

## 26. BACKGROUND JOB MANAGEMENT

Develop a robust job abstraction for operations such as:

- Email synchronization.
- Source imports.
- Reindexing.
- Integrity checks.
- Backup.
- Restoration validation.
- Summary generation.
- Large report generation.

Provide:

- Job identifiers.
- Job descriptions.
- Job status.
- Progress information.
- Start timestamps.
- Completion timestamps.
- Cancellation.
- Error details.
- Structured diagnostics.

Do not create unnecessary daemon infrastructure.

Avoid excessive concurrency.

Respect SQLite write coordination.

Do not permit conflicting maintenance operations to corrupt an archive.

Use cooperative locks where appropriate.

A failed or interrupted job must leave the archive in a recoverable state.

Long-running jobs must not freeze the desktop interface.

## 27. CONFIGURATION ARCHITECTURE

Preserve compatibility with existing configuration files.

Develop validated settings for:

- Archive paths.
- Appearance.
- Search behavior.
- Timeline behavior.
- Import behavior.
- Source-specific preferences.
- Synchronization.
- Research.
- AI.
- Storage.
- Backup.
- Performance.

Use sensible defaults.

Do not require manual source code editing to configure ordinary application behavior.

Avoid exposing secrets in portable configuration exports.

Use operating-system credential stores where practical.

Do not store credentials in source code.

Do not store credentials in Git.

Do not include credentials in diagnostic reports.

Imported preferences must not silently authorize network activity or AI inference.

Restored archives must not automatically resume background synchronization or inference without appropriate user control.

## 28. BACKUP AND DISASTER RECOVERY

Backup and restoration are foundational, not secondary conveniences.

Ensure backup coverage includes:

- Original email records.
- Original imported source objects.
- Archive databases.
- Unified catalog databases.
- Research overlays.
- User annotations.
- Summaries.
- Relevant configuration.
- Source provenance.
- Schema version information.

Exclude credentials.

Document backup boundaries.

Validate:

- File integrity.
- Database integrity.
- Foreign-key integrity.
- Index consistency.
- Source-object coverage.
- Backup completeness relative to documented scope.

Never silently overwrite an existing backup.

Never silently restore over an existing archive.

Prefer restoration to a new destination.

Disable automatic background jobs in restored configurations.

Develop repeatable synthetic disaster-recovery drills.

Test:

- Missing files.
- Corrupt files.
- Invalid manifests.
- Unexpected directories.
- Interrupted backup.
- Interrupted restoration.
- SQLite WAL databases.
- Older database schemas.
- Research overlay restoration.
- Summary restoration.
- Unsupported configuration versions.

Make failures understandable.

Do not claim that an archive is recoverable merely because a backup file exists.

## 29. PERFORMANCE ENGINEERING

The application should be capable of handling substantial personal archives.

Establish synthetic performance scenarios involving:

- 10,000 records.
- 50,000 records.
- 100,000 records.
- 250,000 records.
- 1,000,000 records where feasible.

These are engineering test scenarios, not guaranteed product capacity claims.

Measure:

- Import throughput.
- Index construction time.
- Search latency.
- Timeline aggregation.
- Database size.
- Memory consumption.
- Startup time.
- Record reader latency.
- Backup duration.
- Recovery duration.
- Large batch operations.

Avoid quadratic algorithms.

Avoid repeated full-table scans.

Avoid loading every record into memory.

Use batching, pagination, incremental indexing and appropriate indexes.

Use EXPLAIN QUERY PLAN where useful.

Record benchmark hardware and environment.

Do not invent benchmark results.

Optimize demonstrated bottlenecks rather than speculative ones.

## 30. TESTING STRATEGY

Preserve the existing automated tests.

Expand coverage substantially.

Use appropriate tooling, including:

- Python unittest or pytest.
- Typed Python validation.
- Mypy or another suitable static type checker.
- Ruff or equivalent linting.
- Vitest.
- Vue component tests.
- Playwright or suitable end-to-end testing.
- Rust tests.
- IPC contract tests.

Tests should cover:

### Archive integrity

- Raw byte preservation.
- Hash verification.
- Deduplication.
- Provenance.
- Database migration.
- Interrupted ingestion.
- Recovery.

### Source adapters

- Valid input.
- Malformed input.
- Unknown fields.
- Missing fields.
- Unicode.
- Large files.
- Duplicate records.
- Revisions.
- Interrupted imports.

### Search

- Boolean queries.
- Exact phrases.
- Filtering.
- Pagination.
- Sorting.
- Malformed queries.
- Large datasets.

### Timeline

- Chronological order.
- Missing dates.
- Time zones.
- Aggregation.
- Source filtering.

### AI

- Disabled AI.
- Incorrect backend configuration.
- Connection failures.
- Timeouts.
- Malformed responses.
- Oversized responses.
- Caching.
- Resumability.
- Prompt versioning.
- Changed inputs.
- Thread expansion.
- Cancellation.
- No external fallback.

### Privacy

- No unauthorized networking.
- No credential leakage.
- No original-record mutation.
- No archive database writes during read-only AI operations.
- No arbitrary filesystem access.
- No unrestricted SQL.

### Desktop

- Application startup.
- Archive selection.
- Search.
- Record inspection.
- Settings.
- Long-running operations.
- Error handling.
- Cancellation.
- Backend failure.

### Backup

- Successful snapshot.
- Verified restoration.
- Corruption detection.
- WAL handling.
- Research preservation.
- Summary preservation.
- Recovery safety.

Use only synthetic fixtures or appropriately licensed public test material.

Never incorporate actual personal correspondence into public test fixtures.

## 31. CI/CD

Develop comprehensive GitHub Actions workflows.

Include appropriate matrices for:

- Python 3.12.
- Python 3.13 or later supported versions.
- Linux.
- macOS.
- Windows.

Validate platform-dependent functionality honestly.

Include:

- Python tests.
- Static typing.
- Linting.
- Frontend compilation.
- TypeScript checking.
- Frontend tests.
- Rust formatting.
- Rust tests.
- Desktop build validation.
- Dependency auditing where appropriate.
- Security scanning.

Use pinned or appropriately constrained dependencies.

Verify GitHub Action versions rather than assuming historical references remain correct.

Do not weaken CI to obtain a green status.

Do not create formal releases automatically.

A build-validation workflow may produce temporary CI artifacts for testing, but release publication remains a separate owner-controlled action.

Document any platform limitations.

## 32. PACKAGING

Investigate production-quality desktop packaging.

Potential targets:

- macOS Apple Silicon.
- macOS Intel.
- Windows x64.
- Linux x64.
- Linux ARM64 where practical.

Evaluate the best approach for bundling or locating the Python engine.

Consider:

- PyInstaller.
- Nuitka.
- Other supported packaging solutions.

Assess actual size, startup time, platform compatibility and security implications.

Avoid requiring ordinary users to manually assemble a complicated development environment merely to launch the desktop application.

Nevertheless, preserve source-based execution for developers.

The application should handle:

- First launch.
- Archive selection.
- New archive creation.
- Existing archive detection.
- Configuration migration.
- Backend startup.
- Backend shutdown.

Do not automatically overwrite existing installations or archives.

Do not claim code signing or notarization unless actually implemented.

Document unsigned binary behavior where relevant.

## 33. DOCUMENTATION OVERHAUL

Documentation must be treated as a core deliverable.

Create or update:

### README.md

Provide:

- Clear project identity.
- Project philosophy.
- Implemented functionality.
- Screenshots of actual working software where appropriate.
- Installation.
- Quick start.
- Privacy boundaries.
- Supported platforms.
- Known limitations.
- Development status.
- Links to detailed documentation.

### ROADMAP.md

Distinguish:

- Implemented.
- In development.
- Planned.
- Experimental.
- Deferred.

Do not present plans as shipping functionality.

### ARCHITECTURE.md

Document:

- Component boundaries.
- Data flow.
- Source storage.
- Database architecture.
- IPC.
- Security.
- AI integration.
- Extension points.

### SECURITY.md

Document:

- Threat model.
- Supported security boundaries.
- Vulnerability reporting.
- Sensitive data handling.
- Known limitations.

### CONTRIBUTING.md

Document:

- Development setup.
- Coding standards.
- Testing.
- Synthetic fixtures.
- Commit practices.
- License obligations.
- Privacy requirements.

### MIGRATION.md

Explain:

- Legacy Dispatch compatibility.
- Existing archive support.
- Configuration migration.
- Schema migration.
- Backup recommendations.
- Rollback considerations.

### USER_GUIDE.md

Provide practical instructions for ordinary users.

### AI_SUMMARIZATION.md

Document:

- Ollama setup.
- Explicit opt-in.
- Model selection.
- Message summaries.
- Thread summaries.
- Batch processing.
- Cache behavior.
- Privacy.
- Troubleshooting.

### SECOND_ME.md

Document:

- Purpose.
- Evidence discipline.
- Retrieval.
- Historical interpretation.
- User controls.
- Known limitations.
- Ethical boundaries.

### SOURCE_ADAPTER_GUIDE.md

Explain how developers can implement additional source adapters.

### FACEBOOK_IMPORT.md

Provide a detailed, practical guide for importing user-obtained Facebook archives.

### BACKUP_AND_RECOVERY.md

Provide verified maintenance and recovery procedures.

### CHANGELOG.md

Maintain accurate descriptions of substantive changes.

Remove stale repository branding where appropriate.

Preserve historical attribution and licensing information.

Retain Dispatch as the name of the email archival engine where useful.

Use HB Continuum as the overall application identity.

## 34. USER TUTORIALS

Create substantive tutorials using fictional data.

Examples:

### Tutorial 1: Your first archive

Create an archive, import synthetic emails, search and verify integrity.

### Tutorial 2: Combining multiple mailboxes

Demonstrate source tracking and historical search.

### Tutorial 3: Importing Facebook history

Use synthetic Facebook JSON records and inspect the results.

### Tutorial 4: Building a historical timeline

Combine email and social records into a chronology.

### Tutorial 5: Creating a research investigation

Collect records, annotate evidence and produce a report.

### Tutorial 6: Local AI summarization

Enable Ollama explicitly and summarize selected records.

### Tutorial 7: Historical self-exploration

Use Second Me to examine changes in a fictional person's interests over time.

### Tutorial 8: Backup and recovery

Create, validate and restore a synthetic archive.

Tutorials must reflect actual implemented functionality.

## 35. ARCHITECTURAL DECISION RECORDS

Maintain concise ADRs documenting important architectural decisions.

Examples:

- ADR-001: Desktop application framework.
- ADR-002: Python engine integration.
- ADR-003: IPC protocol.
- ADR-004: Source-independent storage.
- ADR-005: Legacy archive compatibility.
- ADR-006: Original record immutability.
- ADR-007: Research overlay architecture.
- ADR-008: Local AI inference.
- ADR-009: Search strategy.
- ADR-010: Backup and recovery.
- ADR-011: Packaging.
- ADR-012: Privacy and network boundaries.

Each ADR should describe:

- Context.
- Decision.
- Alternatives considered.
- Trade-offs.
- Consequences.
- Status.

Avoid unnecessary bureaucracy, but preserve the reasoning behind major decisions.

## 36. DEVELOPMENT EXECUTION PLAN

Execute the work in coherent increments.

### Phase A — Stabilization

- Audit the repository.
- Establish baseline tests.
- Resolve outstanding hardening defects.
- Consolidate relevant existing changes.
- Correct documentation.
- Identify migration constraints.

### Phase B — Engine modularization

- Create the Python package.
- Extract coherent services.
- Preserve existing CLI behavior.
- Add typed interfaces.
- Add regression coverage.

### Phase C — Desktop proof of concept

- Establish Tauri/Vue.
- Implement narrow IPC.
- Demonstrate actual archive operations.
- Validate packaging feasibility.

### Phase D — Desktop functional parity

Reproduce existing functionality:

- Search.
- Message reading.
- Threads.
- Import.
- Synchronization.
- Preferences.
- Research.
- Backup.
- Integrity verification.

Do not retire Tkinter until functional parity is established.

### Phase E — Source-independent archive

- Implement adapter infrastructure.
- Establish source catalog.
- Implement provenance.
- Implement unified indexing.

### Phase F — Facebook ingestion

- Implement supported JSON formats.
- Add import preview.
- Add resumability and diagnostics.
- Add regression tests.

### Phase G — Research workstation

- Universal search.
- Timeline.
- Collections.
- People.
- Research reports.
- Visualizations.

### Phase H — Local AI

- Preferences.
- Ollama backend.
- Message summarization.
- Thread summarization.
- Batch operations.
- Source citation.
- Fake-server tests.

### Phase I — Second Me foundation

- Controlled retrieval.
- Source-backed historical responses.
- Temporal reasoning.
- Historical comparison.
- Contradiction exploration.

### Phase J — Hardening

- Security review.
- Performance benchmarks.
- Recovery drills.
- Cross-platform validation.
- Accessibility.
- Usability improvements.

### Phase K — Documentation and consolidation

- Complete documentation.
- Resolve inconsistencies.
- Remove dead code where safe.
- Review outstanding technical debt.
- Produce a clear readiness assessment.

Do not regard these phases as permission to leave the repository in a broken intermediate state.

Maintain testable increments.

## 37. GIT WORKFLOW

The repository owner uses GitHub as an actively synchronized work-in-progress development environment.

Public repository visibility does not imply release readiness.

Use focused branches and meaningful commits.

Do not force-push shared branches.

Do not delete important branches.

Respect configured branch protection.

Do not bypass failing checks.

Do not overwrite uncommitted user work.

Commit coherent, tested changes.

Push development work where repository access and the owner's workflow permit.

Use pull requests when required or helpful.

Do not create formal releases.

Do not create release tags.

Before merging substantial changes, ensure:

- Existing functionality remains operational.
- Appropriate tests pass.
- Database compatibility is preserved.
- Documentation is accurate.
- No private data is included.

## 38. CODING STANDARDS

Prefer straightforward, maintainable engineering over fashionable complexity.

Use:

- Clear naming.
- Small cohesive modules.
- Explicit interfaces.
- Type annotations for new Python code.
- Strict TypeScript where practical.
- Structured error handling.
- Parameterized SQL.
- Meaningful logging.
- Resource management.
- Context managers.
- Deterministic behavior where possible.

Avoid:

- God objects.
- Giant functions.
- Excessive global state.
- Unnecessary inheritance.
- Hidden side effects.
- Duplicate business logic.
- Unbounded recursion.
- Unbounded memory consumption.
- Silent exception swallowing.
- Catch-all error suppression.
- Hardcoded personal paths.
- Hardcoded account identifiers.
- Hardcoded credentials.
- Fake implementations.
- Excessive abstraction without demonstrated benefit.

Do not introduce microservices merely to make the architecture appear sophisticated.

This is fundamentally a local desktop application.

Keep operational complexity proportional to its purpose.

## 39. AUTONOMY AND ENGINEERING JUDGMENT

You are encouraged to discover additional opportunities for substantive improvement.

If you identify a significant defect, address it when it falls within the project scope.

If you identify a better architecture, evaluate it and document the reasons.

If a dependency is unnecessary, remove it safely.

If an existing abstraction is poor, refactor it.

If functionality is difficult to use, improve the user experience.

If the documentation is misleading, correct it.

If a test is insufficient, strengthen it.

If a claimed capability does not exist, either implement it properly or correct the claim.

Do not spend disproportionate effort polishing trivial matters while foundational defects remain unresolved.

Prioritize:

1. Data integrity.
2. Privacy.
3. Recoverability.
4. Functional correctness.
5. Backward compatibility.
6. Usability.
7. Performance.
8. Extensibility.
9. Visual refinement.

## 40. DEFINITION OF DONE

A feature is not done merely because source files exist.

A feature is done when:

- It performs the intended operation.
- Its behavior is accessible through an appropriate interface.
- It handles foreseeable errors.
- It preserves data integrity.
- It respects privacy boundaries.
- It has appropriate automated tests.
- Its documentation is accurate.
- It integrates with the rest of the application.
- Its limitations are disclosed.
- Its implementation is maintainable.

A modern frontend is not done when it merely resembles a professional application.

It must operate as one.

A source adapter is not done when it imports one idealized example.

It must handle realistic input variation.

An AI feature is not done when it generates plausible text.

It must be controlled, source-backed, appropriately bounded and clearly distinguish interpretation from evidence.

A backup feature is not done until restoration has been tested.

## 41. ENGINEERING STATUS REPORT

Maintain:

`docs/engineering/IMPLEMENTATION_STATUS.md`

Update it throughout development.

Include:

- Current phase.
- Implemented capabilities.
- Pending capabilities.
- Architectural decisions.
- Files changed.
- Database changes.
- Migration considerations.
- Tests executed.
- Test results.
- CI status.
- Security findings.
- Performance findings.
- Known limitations.
- Outstanding defects.
- Next recommended tasks.

When finishing a substantial work session, provide the repository owner with:

1. A concise executive summary.
2. Substantive improvements implemented.
3. Architecture changes.
4. User-visible changes.
5. Test results.
6. Security considerations.
7. Backward compatibility status.
8. Remaining work.
9. Git commits and branch status.
10. Release-readiness assessment.

Be explicit about anything not tested.

Do not misrepresent unfinished work.

## 42. FINAL DIRECTIVE

HB Continuum should ultimately become a powerful, genuinely useful, independently controlled historical knowledge workstation.

Do not build a glorified email viewer.

Do not build another cloud-dependent AI wrapper.

Do not build a superficial dashboard.

Do not build an application that imprisons a user's historical information within yet another proprietary system.

Build a durable archival foundation.

Build a capable research environment.

Build a modern desktop experience.

Build a source-independent ingestion infrastructure.

Build optional local intelligence.

Build something that enables people to explore decades of documented history while retaining ownership and control of that history.

Preserve the principles of the Honey Badger Universe.

The software should be free to use, inspect, understand, modify and extend under its applicable license.

The architecture should enable future developers to carry the project forward without requiring its original creator.

Do not wait for individual instructions for every ordinary engineering decision.

Make reasonable decisions independently, document consequential trade-offs, and continue implementing the next logical engineering increment.

Begin with the comprehensive repository audit.

Then establish a practical execution plan and immediately proceed with implementation.

Be ambitious.

Be methodical.

Be skeptical of your own assumptions.

Verify your work.

Build it for real.

**Time is linear. Knowledge need not be.**

**The intelligence is replaceable. The memories are yours.**

END OF MASTER ENGINEERING DIRECTIVE.