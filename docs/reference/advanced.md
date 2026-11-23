# Offline inspection and saved plans

Use native Docs API JSON obtained with `includeTabsContent=true` and a Drive comments JSON array:

```sh
citegoblin scan document.json --tab t.0 --output register.json
citegoblin format register.json --style author-year --output preview.json
citegoblin process-comments document.json comments.json --tab t.0 --output result.json
citegoblin apply result.json --journal /private/path/apply-journal.json
```

`process-comments` emits `{documentId, plan, report}`; `apply` accepts either that wrapper or a bare plan. Comment-driven plans carry their original command fingerprints so `apply` can perform the same verified resolution/error-reply behaviour. A command edited or resolved since planning is left alone during comment cleanup. Dry runs never resolve comments or post replies. Supply `--docx document.docx` if comment quotes are unavailable. Live runs fetch an export when needed. Export matching is exact; absent, stale or ambiguous anchors are errors.

`comments comments.json` lists DOI/PMID/URL candidates from ordinary comments for inspection. It does not turn them into commands automatically. Metadata lookup is available via `lookup DOI`, `lookup "PMID: 42127953"` or `lookup PUBMED_URL`. Metadata lookup needs internet access but no Google login.
