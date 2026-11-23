# Export references

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
