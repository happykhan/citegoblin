# CiteGoblin

A comment-driven citation manager for Google Docs. Choose the source, select the text it belongs to, and leave a command. Run CiteGoblin to insert citations and rebuild the bibliography.

Python handles document changes; a pinned JavaScript CSL engine and Zotero-compatible CSL style files handle formatting. No AI or Zotero installation is required. Google sign-in opens the browser once; document processing uses the APIs.

## In the document

Select the passage and add a comment containing exactly:

```text
@cite 10.1234/example
```

CiteGoblin places the citation at the end of that selection, before its final sentence punctuation. Select enough text to identify the location uniquely. If the selected wording occurs more than once, CiteGoblin reports the ambiguity and leaves that command unapplied.

A comment anywhere can set the document style:

```text
@style author-year
```

Bundled styles (names are case-insensitive):

| Comment | Style |
| --- | --- |
| `@style IEEE` | IEEE Reference Guide |
| `@style APA` | APA 7th edition |
| `@style Chicago` | Chicago 18th edition, author–date |
| `@style MLA` | MLA 9th edition, in-text |
| `@style Nature` | Nature, including superscript citation numbers |
| `@style author-year` or `@style Harvard` | Elsevier Harvard |
| `@style Vancouver` | NLM citation-sequence |

`@refresh` recalculates all managed citations and the bibliography. Native Google Docs inline formatting preserves CSL italics, bold, small caps and superscripts.

```sh
citegoblin styles list
citegoblin styles install cell
```

Additional in-text journal styles can be installed by their [Zotero CSL style ID](https://www.zotero.org/styles), then selected using `@style cell`, for example. Installations use a pinned snapshot of the official CSL repository, resolve dependent styles through their parent, and retain the source licences. Install the same additional style on each computer processing the document. Footnote/endnote styles and non-English locale files are not supported yet.

Regular comments are ignored. Once a command has updated the document and passed readback verification, CiteGoblin resolves its comment, preserving the thread. Successful commands are also recorded in document metadata, so a failed comment resolution can be retried without inserting the citation again.

Failed commands stay open with one reply beginning `CiteGoblin error [v1]:`. Reruns update that same reply when the error changes and do not post it again when unchanged. If a reply creation times out after reaching Google, the next run looks for the existing reply before creating one. Human replies are left untouched. Edit a failed command and run again. Edit an already successful citation command only if you intend to add another citation; editing a comment is not a reference-replacement operation.

You can also paste a complete APA-like author–year journal reference after `@cite`:

```text
@cite Derwing, T. M., Rossiter, M. J., & Munro, M. J. (2002). Teaching native speakers to listen to foreign-accented speech. Journal of Multilingual and Multicultural Development, 23(4), 245-259.
```

CiteGoblin searches Crossref programmatically and accepts one matching DOI only after checking title, author surnames and initials, year, journal, volume, issue (when supplied), and pages. It does not simply choose the first search hit. Zero matches, conflicting details or multiple matching DOIs leave the command open with one maintained error reply. This currently supports the author-initials, parenthesised-year, journal/volume/pages format above; other reference formats should use a DOI or PMID. GitHub and general webpages still require supplied reference metadata.

DOIs can also be supplied as DOI links or with a `DOI:` prefix. PubMed articles accept all these forms:

```text
@cite PMID: 42127953
@cite PMID:42127953
@cite https://pubmed.ncbi.nlm.nih.gov/42127953/
```

A newline after `@cite` is also accepted. PubMed identifiers are looked up through NCBI EFetch; article title, authors, publication date, journal, volume, issue, pages or article number, and DOI are converted into CSL metadata. Missing required metadata or mismatched identifiers produce an error rather than invented fields. DOI and PMID references for the same article are deduplicated using their shared identifiers.

For a reference already in the register, use `@cite ref:r0123456789abcdef`. For websites or reports without a DOI, provide their CSL-JSON metadata using `--references references.json`, then use `@cite url:https://example.org/report`. The file must be a JSON array of CSL records with titles and matching URLs. CiteGoblin does not guess authors or dates from webpages.

## Install

Requires Python 3.11+, Git, Node.js and npm. The commands below are for macOS/Linux; on Windows activate the environment with `.venv\Scripts\activate` instead.

```sh
git clone https://github.com/happykhan/citegoblin.git
cd citegoblin
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[google]'
citegoblin setup-formatter
```

### Setup: sign in with Google

An API key cannot authorise edits to a private Google Doc. CiteGoblin uses desktop OAuth: Google opens in your browser, you choose your account and approve access, and CiteGoblin saves the authorisation for later runs. Google passwords never pass through CiteGoblin.

**CGPS users:** obtain CiteGoblin's desktop OAuth client JSON privately from the maintainer, then run the login command below. You do not need to create your own Google Cloud project. The registered application currently accepts CGPS accounts only. No credentials or user tokens are included in this public repository.

**Maintainers or self-hosted installations:** application registration is a one-time step:

1. Create a Google Cloud project and enable **Google Docs API** and **Google Drive API**.
2. Configure the OAuth consent screen for CiteGoblin. Use your organisation's internal app if appropriate, or add authorised test users while developing an external app.
3. Create an OAuth client with application type **Desktop app**, then download its JSON configuration. This is an OAuth client configuration, not an API key or a service-account key.
4. Run:

```sh
citegoblin login --client-secrets /path/to/downloaded-client.json
```

The browser opens Google's account chooser and consent page. Authorise using the account that has editing and commenting access to the document. The callback returns to a temporary local listener on `127.0.0.1`; no public server, browser automation or copied verification code is required.

Once a desktop client is configured, the first `run`, `init` or `apply` automatically opens sign-in in an interactive terminal if no usable authorisation exists. Later runs reuse it and refresh expired access tokens automatically. Revoked permissions trigger sign-in again; temporary network failures produce an error without needlessly starting a new login. Non-interactive runs never start a browser: run `login` once in a terminal first.

The OAuth client is configured once per installation. For a distributed release, the maintainer can supply a registered desktop client configuration so each user only needs to sign in. A public client configuration is not a user's token; never distribute access tokens, refresh tokens or service-account keys. Google consent/publishing and organisation policies still apply. See [Google's desktop OAuth guide](https://developers.google.com/identity/protocols/oauth2/native-app).

### Saved authorisation

Tokens are stored in the operating system's keychain by default: macOS Keychain, Windows Credential Manager or a supported Linux secret store. Plaintext fallback is never automatic. If no supported keychain is available, explicitly choose private file storage:

```sh
citegoblin login --client-secrets /path/to/downloaded-client.json --token-file /private/path/token.json
```

That choice is remembered locally. On POSIX systems the token file is written with owner-only permissions. Do not share or commit it. `CITEGOBLIN_TOKEN_FILE` can override the path; `CITEGOBLIN_CLIENT_CONFIG` can point to a preconfigured desktop client JSON.

```sh
citegoblin auth-status
citegoblin logout
```

`auth-status` never displays tokens. `logout` removes the local token; it does not revoke Google's grant or stop an already-running process. Access can also be revoked in your Google Account's connected-app settings.

Comment replies and resolution require writable Drive access, so the requested scopes are `documents` and `drive`. CiteGoblin resolves successful command threads regardless of who wrote them. It never deletes comments or replies. Failed commands remain open with one maintained error reply. See [Google comment resolution](https://developers.google.com/workspace/drive/api/guides/manage-comments#resolve_a_comment).

For servers, existing Application Default Credentials remain available explicitly: set `CITEGOBLIN_AUTH=adc`, or set `GOOGLE_APPLICATION_CREDENTIALS` to an approved credentials file. These modes do not launch browser sign-in. A service account must have document editing and commenting access.

## Run on demand

The document ID is the part between `/d/` and `/edit` in its URL. Supply the intended tab explicitly, for example `t.0`.

For a new document, put `[[bibliography]]` in a paragraph where the reference list belongs, then initialise its hidden register:

```sh
citegoblin init DOCUMENT_ID --tab t.0 --workdir /private/path/citation-runs --dry-run
citegoblin init DOCUMENT_ID --tab t.0 --workdir /private/path/citation-runs
```

Initialisation does not convert existing typed citations. Documents using the earlier `CGPS_DOC_` register can be used directly; Zotero documents require a separate explicit migration.

Preview and process comments:

```sh
citegoblin run DOCUMENT_ID --tab t.0 --workdir /private/path/citation-runs --dry-run
citegoblin run DOCUMENT_ID --tab t.0 --workdir /private/path/citation-runs
```

The second command reads the document afresh and saves the plan actually applied. A dry run does not reserve a revision. For an exact saved-plan approval workflow, use the offline commands below followed by `apply`.

Optional polling, started and stopped by the user:

```sh
citegoblin run DOCUMENT_ID --tab t.0 --workdir /private/path/citation-runs --watch 60
```

This checks every 60 seconds while the process is running. Stop with Ctrl-C. It installs no background service or schedule. Add another `@refresh` comment when a refresh is needed; editing or deleting managed fields by hand is not a supported citation-editing interface yet.

## Offline inspection and planning

Use native Docs API JSON obtained with `includeTabsContent=true` and a Drive comments JSON array:

```sh
citegoblin scan document.json --tab t.0 --output register.json
citegoblin format register.json --style author-year --output preview.json
citegoblin process-comments document.json comments.json --tab t.0 --output result.json
citegoblin apply result.json --journal /private/path/apply-journal.json
```

`process-comments` emits `{documentId, plan, report}`; `apply` accepts either that wrapper or a bare plan. Comment-driven plans carry their original command fingerprints so `apply` can perform the same verified resolution/error-reply behaviour. A command edited or resolved since planning is left alone during comment cleanup. Dry runs never resolve comments or post replies. Supply `--docx document.docx` if comment quotes are unavailable. Live runs fetch an export when needed. Export matching is exact; absent, stale or ambiguous anchors are errors.

`comments comments.json` lists DOI/PMID/URL candidates from ordinary comments for inspection. It does not turn them into commands automatically. Metadata lookup is available via `lookup DOI`, `lookup "PMID: 42127953"` or `lookup PUBMED_URL`. Metadata lookup needs internet access but no Google login.

## Export references

Export directly from a managed Google document (ID or full Docs URL):

```sh
citegoblin export DOCUMENT_ID --tab t.0 --format bibtex --output references.bib
citegoblin export DOCUMENT_ID --tab t.0 --format ris --output references.ris
citegoblin export DOCUMENT_ID --tab t.0 --format endnote --output references.enw
```

Or export offline from the JSON register produced by `scan`:

```sh
citegoblin export register.json --format bibtex --output references.bib
```

Native Docs API JSON is also accepted, with an explicit `--tab`. Local-file exports need no Google login. Live exports read the document without changing its content or comments.

Formats:

- `bibtex`: UTF-8 `.bib`, with stable reference IDs as citation keys, escaped TeX special characters and protected title capitalisation.
- `ris`: UTF-8 `.ris`, with repeated author/editor tags, DOI, URL, PMID, journal and publication fields.
- `endnote`: UTF-8 EndNote Import tagged text (`.enw`), using `%0`, `%A`, `%T` and related fields. In EndNote, select the **EndNote Import** filter when importing this file.

All reference records are exported once, in bibliography order where available, including retained uncited records. Add `--cited-only` to include only sources used by managed citations. Use `--output -` to write to standard output. Missing authors or publication dates are left unset. These are bibliographic interchange files; citation positions and comment-processing history stay in the document register.

## API request use

An idle poll reads the comments only; it does not fetch the document. For up to 100 comments this is one Google request. Larger comment histories require pagination. An unchanged invalid command with the same existing error reply also needs only that comments read and no writes.

Comment-list reads include complete replies. After an edit, one fresh paginated comment-list read checks all affected command fingerprints before feedback, rather than fetching each thread and its replies separately. The revision guards and post-write document verification remain in place. Each actual comment resolution or error-reply change still requires a write request.

`--watch 60` waits 60 seconds after each pass. Use `--watch 300` for less frequent polling. A run only processes explicit commands; it does not refresh every citation on each poll.

## Integrity and limits

- Reference IDs and citation source mappings live in hidden Google Docs named ranges, not in bracket-number patterns. Ordinary `[42]` text is untouched.
- Uses UTF-16 document offsets, including non-BMP characters.
- Each write is guarded by the document revision. Concurrent changes stop the operation rather than being overwritten.
- Citation replacement and its metadata stay in the same atomic API batch. A large refresh can span several batches; the entire refresh is not a single transaction.
- An interrupted or uncertain write leaves a journal and cannot be replayed blindly. Inspect live state and make a fresh plan.
- Readback checks citation text, source mappings, reference metadata, bibliography, other body text, and table/image counts. It is not a visual layout check.
- Pending suggestions affecting citation text or a selected passage block changes by default. The explicit override is for separately reviewed cases.
- Body and table-cell text are supported. Footnote, header and footer citations are not supported. Multi-paragraph selections are not supported.
- DOI lookup uses Crossref. Non-Crossref DOIs require supplied CSL metadata. Metadata is not proof that a paper supports a claim.
- Uncited register records are retained in the bibliography for compatibility with earlier documents. Removing references and changing an existing citation's sources need a future explicit interface.
- Live-tested on 23 November 2026 against a disposable Google Doc using CiteGoblin’s own desktop OAuth client: citation insertion, bibliography/style refresh, comment resolution, error-reply updates, login reuse and token refresh passed. See [LIVE_TEST.md](LIVE_TEST.md). The registered test application currently permits CGPS organisation accounts only; external distribution requires separate Google audience/publishing configuration.

## Tests

```sh
.venv/bin/pip install -e '.[google,test]'
.venv/bin/python -m unittest discover -s tests -v
```

Tests use synthetic documents only. Do not commit manuscript exports, comments, credentials or private run journals.

## Dependencies and licences

Project code: MIT. Bundled CSL styles and locale retain their upstream licence declarations; see [THIRD_PARTY.md](THIRD_PARTY.md).
