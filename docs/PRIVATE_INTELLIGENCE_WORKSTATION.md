# Building your private intelligence workstation

## Design principle

**Independent by design. Interoperable by choice. Intelligent when desired.**

Dispatch and Continuum can operate independently. Neither requires Ollama, a companion application, a central account or cloud inference. Continuum includes its own Dispatch-derived ingestion engine. Connecting applications is an explicit user choice, not a requirement.

## Choose your setup

- Standalone Dispatch: acquire and preserve email, search and export locally.
- Standalone Continuum: ingest and research email and supported historical sources using its own engine.
- Connected workflow: transfer preserved EML files from Dispatch into a separate Continuum archive; use Continuum as the research workstation.
- Optional local AI: share one Ollama server across compatible applications.

## Safe connection tutorial

1. Install Python and the desired application from its repository. Follow its README for platform prerequisites.
2. Choose an archive outside either source checkout. For example, on macOS/Linux: `~/HB_Mail_Archive`. On Windows use an explicit absolute path.
3. Stop synchronization jobs before making a full backup of the Dispatch archive, including raw EML, databases and configuration. Verify the backup and test restoration.
4. Prefer a separate Continuum archive initially. From the Continuum checkout, import a small selection of copied EML files:

   ```sh
   python3 dispatch.py --archive ~/HB_Continuum_Archive import /path/to/sample.eml
   python3 dispatch.py --archive ~/HB_Continuum_Archive search invoice
   python3 dispatch.py --archive ~/HB_Continuum_Archive gui
   ```

   Raw EML import preserves message bytes but does not reproduce mailbox provenance or research overlays. Keep the original Dispatch archive.
5. For an existing archive migration, work on a verified copy first. Consult [migration instructions](MIGRATION.md) and [archive hardening](ARCHIVE_HARDENING.md). Run `python3 dispatch.py --archive /path/to/copy migrate --dry-run`, then migrate and verify on the copy. Do not point an older Dispatch writer at the migrated schema; concurrent cross-version operation has not been validated. Use one supported writer per archive.
6. Install Ollama from https://ollama.com/download if AI is desired. Start it, then run:

   ```sh
   ollama pull qwen3.5:9b
   ollama list
   ```

   Select a smaller model if memory is constrained. In Continuum Configuration Center > AI, enable AI, choose Ollama, set the endpoint to `http://localhost:11434` and model to `qwen3.5:9b`. Start with one message or thread, not the entire archive. See [AI summarization](AI_SUMMARIZATION.md).
7. Verify AI summaries against original records; they are derived text, not evidence. Keep AI disabled if unwanted. Local endpoints are not a guarantee of offline inference; choose a downloaded local model and restrict network access if needed.

## Optional ecosystem connections

These are proposed adapters unless explicitly described as existing. No project should depend on Continuum to operate.

| Project | Potential contribution | Boundary |
| --- | --- | --- |
| HB Briefing | Existing cited report exports (Markdown/JSON); proposed ingestion as dated snapshots | Preserve publisher, URL, publication date and retrieval date; distinguish reporting from inference |
| HB PDF Studio | Proposed document/text exports | Preserve original PDF hash, page references and extraction limitations |
| HB SunRise / honey-ledger | Proposed opt-in financial event exports | Redact account identifiers; no credentials or automatic transaction writes |
| Time Warp Universe | Its observed drawing/compiler tools are not a calendar feed; optionally preserve exported programs or project artifacts | Record original files and versions; no assumed calendar integration |
| Git repositories | Proposed commit/release history adapter | Preserve commit IDs and timestamps; exclude secrets and private repositories by default |

Use versioned, documented export formats, stable source IDs, explicit consent, read-only ingestion and reversible derived indexes. Never silently send private material to cloud providers. Future cross-source question answering should retrieve bounded, cited evidence; it is not an existing whole-archive AI feature.

Local by default. Cloud by choice. Open by design. Owned by you.
