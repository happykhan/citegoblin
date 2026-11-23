# Local storage

The shared Google Doc is the authoritative citation store. Its hidden named ranges contain the reference records, citation-to-reference mappings, bibliography location and processed-command ledger. Collaborators do not need to share a local folder for citations to remain connected to the document.

CiteGoblin also keeps a small local cache, separated by document ID and tab ID:

```text
~/.citegoblin/
  documents/
    DOCUMENT_ID/
      tabs/
        TAB_ID/
          references.json
          bibliography-anchor.json
          last-run.json.gz
          preview.json.gz
```

The files are created as needed:

| File | Contents |
| --- | --- |
| `references.json` | Original reference metadata plus corrected-field overrides, citation item IDs, bibliography order, selected style and enabled reference-cleanup rules; no manuscript body or positional ranges |
| `bibliography-anchor.json` | The persistent location comment's ID and fingerprint, used to avoid document reads during idle polling |
| `last-run.json.gz` | One compressed latest run: its edit plan, command report and result; replaced on the next completed pass |
| `preview.json.gz` | One compressed dry-run preview; replaced by the next preview |

JSON is compact rather than pretty-printed. An unchanged reference cache is not rewritten. Idle passes write no run files. CiteGoblin does not automatically save PDFs, whole-document snapshots or the DOCX exports used temporarily to recover comment anchors. Edit plans can contain selected passages, comment text and reference metadata, so the local files should remain private.

After a successful write, its temporary plan, result and completed journal are cleared. **Incomplete, uncertain or unreadable write journals and their associated plans are retained** for inspection. These recovery files are intentionally not subject to automatic size limits. Explicitly saved offline plans and cleanup journals are not pruned.

The cats walkthrough used 2,903 bytes across its three local files after a verified refresh with one reference. This is an illustrative measurement, not a size cap: storage grows with reference metadata, the latest plan and any interrupted writes.

## Use the default folder

No work-folder argument is needed:

```sh
citegoblin run "GOOGLE_DOC_URL"
citegoblin run "GOOGLE_DOC_URL" --watch 60
```

To choose another base location while retaining document/tab separation, set `CITEGOBLIN_HOME`. For a specific run, `--workdir /your/folder` uses exactly that folder instead. Keep different documents' overrides separate.

The cache can be exported without accessing Google:

```sh
citegoblin export ~/.citegoblin/documents/DOCUMENT_ID/tabs/TAB_ID/references.json \
  --format bibtex --output references.bib
```

To inspect a compressed preview:

```sh
python3 -m gzip -d -c ~/.citegoblin/documents/DOCUMENT_ID/tabs/TAB_ID/preview.json.gz
```

The local cache is not used to overwrite the Google Doc. Removing an ordinary cache causes it to be rebuilt on a later document read; it does not remove shared citations. Inspect incomplete journals before removing recovery files.

Google login tokens remain in the operating system's keychain. OAuth client configuration and installed styles continue to use the platform's CiteGoblin configuration folder; they are separate from per-document citation data. See [Google sign-in](../getting-started/google-login.md).
