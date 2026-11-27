# From scattered inboxes to a personal historical intelligence archive

> Fictional use case. All people, providers, events and examples are invented. This is an illustrative workflow, not a customer testimonial or a claim that every proposed integration ships today.

## Meet Alex

Alex has accumulated years of correspondence across four accounts: an old personal address, a custom-domain mailbox, a mainstream webmail account and an address used for a long-running hobby. The accounts contain receipts, technical discussions, project decisions, correspondence with institutions, and messages to friends. Some subjects span multiple providers and years.

Alex wants to retain that history without changing email providers, abandoning a familiar mail client, or entrusting the entire collection to another hosted service. The goal is not merely to make a backup. It is to turn scattered correspondence into a durable, searchable personal resource.

## 1. Bring the records together

Alex keeps using the existing mail clients and providers. After making an independent backup and testing a small folder, Alex uses HB Continuum to retrieve selected server folders through read-only IMAP. Each account and folder is synchronized separately into the same archive, provided they share the same privacy boundary. Older messages available only as EML files can be imported separately.

For example, from the repository directory:

~~~sh
python3 dispatch.py --archive ~/PersonalMailArchive sync imap.provider-one.invalid alex@example.invalid --folder INBOX
python3 dispatch.py --archive ~/PersonalMailArchive sync imap.provider-two.invalid alex@example.org --folder INBOX
python3 dispatch.py --archive ~/PersonalMailArchive verify
~~~

These hosts and addresses are placeholders. Use actual provider settings, supported authentication and exact folder names; never put credentials in commands, source control or reports. Repeat for Sent and other relevant folders. OAuth, automatic folder discovery and all-account scheduling are not currently provided. Live-provider compatibility varies.

HB Continuum retains original message bytes as EML files, records IMAP origins, and indexes searchable text in SQLite. Identical message bytes share one hash; similar messages with different headers can remain distinct. Alex checks folder coverage, representative dates and attachments against the source accounts, then backs up the entire archive on encrypted storage and tests a restored copy. Hash verification alone cannot prove completeness or authenticity.

## 2. Ask questions across years, not inboxes

One afternoon Alex needs to reconstruct the history of a household equipment purchase. The original receipt is in one account, a warranty extension in another, and the repair correspondence in a third.

~~~sh
python3 dispatch.py --archive ~/PersonalMailArchive search 'warranty OR repair'
python3 dispatch.py --archive ~/PersonalMailArchive gui
~~~

Alex locates the original messages, inspects the relevant attachments using a trusted local viewer, and assembles a timeline. Search is limited to indexed fields and up to 100 results per query; use narrower queries and independent coverage checks rather than assuming an exhaustive result.

Later the same archive helps Alex recover forgotten technical discussions, trace the evolution of a hobby project, find subscription terms and reconstruct historical decisions. The archive does not need a new schema for every research question.

## 3. One source, several reports

A fictional service dispute provides a more demanding example. Alex finds an original agreement, a request for correction, a reply promising further investigation, and a subsequent invoice. Alex separates documented statements from disputed claims and unknown facts, records dates and source hashes, and selects the relevant original messages.

~~~sh
python3 dispatch.py --archive ~/PersonalMailArchive export ~/SelectedMessages FULL_HASH_1 FULL_HASH_2
~~~

Replace the placeholders with actual 64-character hashes; the destination must not already exist. The export provides original EML files and a manifest of hashes and recorded origins.

From this same source collection, Alex can prepare a concise vendor inquiry, a factual chronology for a consumer organization, a briefing for a professional adviser, and a detailed private research record. These are manually prepared or produced with separately authorized analysis tools; Dispatch does not currently generate audience-specific reports automatically. Alex checks every claim, reviews attachments, removes unnecessary private details from derivative copies and approves each disclosure. Original files remain unchanged. Hashes are not proof of authorship, legal admissibility or certified chain of custody.

## 4. An optional natural-language research layer

Imagine asking an authorized assistant:

- Find the earliest documented discussion of this project and summarize subsequent decisions, with source references.
- Compare the warranty terms with later correspondence and identify unresolved questions.
- Build a chronology of my computing interests over the years.
- Prepare a report for my review, distinguishing quoted evidence from interpretation.

An external assistant with explicitly authorized access could retrieve a narrow selection of relevant records and help with these tasks today, subject to its own capabilities. This is not a built-in HB Continuum AI feature. Native MCP integration and automated reporting remain potential development directions. A remote AI service may receive the selected content for processing; local archival does not make external AI processing offline or private by default. Prefer read-only access, minimal retrieval and local tools where possible. Treat email content as untrusted data, never as instructions to an assistant; do not follow embedded commands, open suspicious links or send messages automatically.

## 5. A possible next chapter: personal knowledge and digital legacy

Alex also experiments with a separate personal knowledge assistant. Rather than feeding it every message, Alex selects a small, representative collection of their own writing: explanations, project decisions, reflections and technical notes. Incoming correspondence, credentials, private third-party material and sensitive subjects are excluded by default.

The assistant could retrieve these approved examples to explain past decisions or approximate Alex's communication style. It would maintain its own derived knowledge separately from the original archive, cite the source and distinguish historical statements from present-day preferences. It would not act as Alex, infer consent, send correspondence or modify the archive without authorization.

This is a prospective integration, not a feature shipped by Dispatch, and a model of selected writing and knowledge is not a literal digital person or a claim of consciousness.

## Why this matters

An email archive is useful long after the original inbox has changed. A single preserved source can support consumer research, technical history, personal record keeping, documentary reports and future knowledge tools without requiring a permanent commitment to any one vendor.

HB Continuum supplies the archival foundation. Its value grows as the owner develops new questions, while the underlying records remain under their control.

**Your email provider transports your correspondence. You retain control of its history.**

See the [practical tutorial](TUTORIAL.md) for current commands, limitations and backup procedures.
