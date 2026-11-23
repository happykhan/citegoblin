# CLI commands

Run `citegoblin --help` for the full command list, or append `--help` to a command for its flags.

| Command | Purpose |
| --- | --- |
| `login --client-secrets FILE` | Configure a desktop OAuth client and sign in |
| `connect DOCUMENT [--tab TAB]` | Authorise a document with Google’s per-file picker and verify access |
| `auth-status` | Inspect saved authorisation without displaying tokens |
| `logout` | Remove local authorisation |
| `setup-formatter` | Install the pinned Node.js CSL formatter |
| `run DOCUMENT [--tab TAB] [--workdir DIR]` | Process bibliography-location, citation and style comments once |
| `run ... --dry-run` | Save a preview without document or comment writes |
| `run ... --watch SECONDS` | Repeat until stopped with Ctrl-C; minimum interval 30 seconds |
| `lookup SOURCE` | Resolve a DOI, PMID, PubMed URL or supported complete reference |
| `styles list` | List bundled and locally installed CSL styles |
| `styles install STYLE_ID` | Install an additional compatible in-text CSL style |
| `export SOURCE --format FORMAT --output FILE` | Export BibTeX, RIS or EndNote tagged text |
| `cleanup plan SOURCE --output FILE [--tab TAB]` | Preview cleanup within References only |
| `cleanup apply PLAN --journal FILE` | Apply a saved cleanup plan |
| `scan DOCUMENT_JSON --tab TAB --output FILE` | Extract the reference register from a native Docs snapshot |
| `format REGISTER_JSON --output FILE` | Format a register locally; optionally set `--style` |
| `plan DOCUMENT_JSON --tab TAB --output FILE` | Build a revision-guarded citation refresh plan |
| `process-comments DOCUMENT_JSON COMMENTS_JSON --tab TAB --output FILE` | Plan commands from saved document and comment snapshots |
| `apply PLAN --journal FILE` | Apply a saved citation plan and its comment feedback |
| `verify DOCUMENT_JSON PLAN` | Verify a document snapshot against a saved citation plan |
| `comments COMMENTS_JSON` | Extract DOI/PMID/URL candidates for inspection |


## Source types

`export` accepts a saved reference register, native Docs JSON, document ID or full Google Docs URL. A register file does not need `--tab`. Native document sources use an explicit or URL tab, or automatically select a single tab.

`cleanup plan` accepts native Docs JSON, a document ID or a full Docs URL. It requires a managed References list and only changes that list.

`run`, `init`, `cleanup plan` and live-document `export` accept full Google Docs URLs or document IDs. URL tab values are extracted automatically; an explicit `--tab` overrides them. Without either, a single tab is selected automatically and a document with multiple tabs is rejected as ambiguous. Keep full URLs in quotes. See [first document](../getting-started/first-document.md) for extracting an ID from its URL.

## Export formats

| `--format` | Output |
| --- | --- |
| `bibtex` | UTF-8 `.bib` |
| `ris` | UTF-8 `.ris` |
| `endnote` | UTF-8 EndNote Import tagged `.enw` |

Use `--cited-only` to exclude retained uncited records, or `--output -` for standard output.

## Saved files

Put run journals, exported document JSON and Google configuration files outside shared repositories. Journals prevent blindly replaying an interrupted write. See [saved plans](advanced.md) and [Google sign-in](../getting-started/google-login.md).

`cleanup plan --check names` checks names only; `--check bibliography` checks reference formatting only. The default is `--check all`.

`run` defaults to `~/.citegoblin/documents/DOCUMENT_ID/tabs/TAB_ID/`. `CITEGOBLIN_HOME` changes the base directory; `--workdir` selects an exact override. See [local storage](../guides/storage.md).
