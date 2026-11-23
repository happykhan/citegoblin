# Scientific-name case and italics

The optional `binomials` module formats approved Latin binomials as *Escherichia coli*: genus initial capital, species epithet lowercase, both italic, with small caps disabled. It does not change ordinary prose case or rename taxa.

Preview changes first, then apply the saved plan:

```sh
citegoblin binomials plan DOCUMENT_ID --tab t.0 --output names-plan.json
citegoblin binomials apply names-plan.json --journal names-journal.json
```

The preview accepts a native document JSON file, document ID or full Google Docs URL. It performs one document read and no writes. Apply checks the saved revision and verifies both text and formatting afterwards.

The bundled starter catalogue contains 20 common bacterial, fungal, parasitic and model-organism binomials checked against NCBI Taxonomy on 23 November 2026. It retains historical synonyms as written: formatting does not silently update taxonomy. Names outside the catalogue are left alone. Extend it with a text file containing one approved full binomial per line:

```sh
citegoblin binomials plan DOCUMENT_ID --tab t.0 --names approved-names.txt --output names-plan.json
```

Add `--abbreviations` to format names such as *E. coli* only when an earlier full-name mention supplies unique genus context. Abbreviations are not expanded. Strain codes and surrounding whitespace remain unchanged. The catalogue is local; scanning makes no taxonomy API requests.

This module checks body and table-cell text. It skips hyperlinks, pending suggestions and managed citation/bibliography fields. It does not process headers, footers, footnotes or citation-source metadata. It runs only when explicitly requested, independently of citation polling. Case edits change individual letters, and the preview lists every proposed change and skipped recognised occurrence.
