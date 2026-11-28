# Document import

HB Continuum imports local historical documents into the same
source-independent catalog as email and Facebook records. Documents are
searchable, citeable and available to the Intelligence workspace.

Originals are **not copied, uploaded or modified**. The catalog stores the
file's SHA-256, path, size, modification time and extracted text. Verification
re-hashes the recorded path; if the file has moved or changed, the source is
reported as missing or altered rather than silently trusted.

## Email attachments

PDF and DOCX attachments on imported email messages use the same local
extractors as standalone documents. Their text is added to the message search
index without copying the attachment. If the optional package is absent or the
file cannot be read, the message still imports and the attachment's name and
MIME type remain searchable. Run `dispatch reindex` after installing an
optional extractor to retry messages imported by an earlier build.

## Supported formats

| Format | Extractor | Notes |
|---|---|---|
| Plain text (`.txt`) | built in | UTF-8 or UTF-16 with BOM |
| Markdown (`.md`, `.markdown`) | built in | text is indexed as written |
| CSV (`.csv`) | built in | indexed as text; no spreadsheet formulas are executed |
| JSON (`.json`) | built in | must parse; indexed as text |
| PDF (`.pdf`) | optional `pypdf` | per-page text and page references when a text layer exists |
| DOCX (`.docx`) | optional `python-docx` | paragraph and table text; no macros are executed |

When an optional package is absent, the preview says extraction is unavailable
and import reports a failure. The file is not indexed as empty. Scanned PDFs
without a text layer are reported as having no extractable text. OCR is not
implemented.

## Limits

- 50 MiB per file.
- 5,000,000 searchable characters per document; longer text is explicitly
  marked truncated in the stored metadata.
- At most 1,000 page references per PDF.
- Hidden files and symbolic links are skipped.
- No embedded macros, scripts or document instructions are executed.

## Behaviour

- **Idempotent:** a file whose SHA-256 is already in the catalog is skipped.
- **Revisions:** a changed file with the same relative label becomes a later
  revision, preserving the earlier record.
- **Provenance:** source path, hash, size, modification time, extractor and
  limitations are stored with the record. The original bytes are not copied.
- **Search:** documents participate in unified search (`document` source),
  the Intelligence workspace, collections, citations and the catalog
  source-independent search. The advanced Boolean builder's catalog scope
  includes documents.
- **Source management:** the `document` catalog source can be verified,
  disabled or removed through the existing Sources workflow. Removal deletes
  catalog records and source references, never the original files.
- **Import history:** every run records files seen, records new/existing and
  extraction failures.

## Commands

```sh
python3 dispatch.py documents preview ~/documents
python3 dispatch.py documents import ~/documents
```

The desktop **Import** workspace offers the same file/folder selection,
preview and cancellable background import, with per-file progress.

## Limitations

- Document pages are searchable as one record; the UI does not yet jump to a
  PDF page.
- Layout, images, formatting and embedded objects are not preserved.
- PDF/DOCX extraction was not exercised against a live optional package in the
  automated suite; only the unavailable/invalid-file paths are covered.
- Documents are not yet shown in the email-only Timeline view.
- Exact-byte deduplication does not merge semantically similar documents.
