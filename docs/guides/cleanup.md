# Cleanup

The optional `cleanup` module checks scientific-name typography and refreshes managed citations and the bibliography. It formats approved Latin binomials as *Escherichia coli*: genus initial capital, species epithet lowercase, both italic, with small caps disabled. It does not change ordinary prose case or rename taxa.

See the [Google Docs walkthrough](../getting-started/cats-walkthrough.md#5-preview-and-apply-cleanup) for a before-and-after example using *Felis catus*.

Preview changes first, then apply the saved plan:

```sh
citegoblin cleanup plan DOCUMENT_ID --tab t.0 --output cleanup-plan.json
citegoblin cleanup apply cleanup-plan.json --journal cleanup-journal.json
```

By default, cleanup runs both checks. For a document without a CiteGoblin register, it runs the scientific-name check alone. Select a check explicitly with `--check names` or `--check citations`.

The citation check rebuilds managed citation text and the bibliography from the stored reference records and selected CSL style. This corrects inconsistent punctuation, spacing, numbering, ordering and style-required inline formatting within those fields. It does not guess which ordinary text is a citation, find new sources, rewrite article titles or fill missing source metadata. Citation-only cleanup requires an initialised register and the installed citation formatter.

Both checks appear in one saved plan and use one guarded apply operation. Name case changes preserve text lengths; citation replacements then run from the end of the document backwards. Verification checks the resulting citation mappings, bibliography, scientific-name text and italics, and text outside the authorised ranges. An interrupted or uncertain write is never replayed automatically.

The preview accepts a native document JSON file, document ID or full Google Docs URL. It performs one document read and no writes. Apply checks the saved revision and verifies both text and formatting afterwards.

The bundled starter catalogue contains 20 common bacterial, fungal, parasitic and model-organism binomials checked against NCBI Taxonomy on 23 November 2026. It retains historical synonyms as written: formatting does not silently update taxonomy. Names outside the catalogue are left alone. Extend it with a text file containing one approved full binomial per line:

```sh
citegoblin cleanup plan DOCUMENT_ID --tab t.0 --names approved-names.txt --output cleanup-plan.json
```

Add `--abbreviations` to format names such as *E. coli* only when an earlier full-name mention supplies unique genus context. Abbreviations are not expanded. Strain codes and surrounding whitespace remain unchanged. The catalogue is local; scanning makes no taxonomy API requests.

This module checks body and table-cell text. It skips hyperlinks, pending suggestions and managed citation/bibliography fields. It does not process headers, footers, footnotes or citation-source metadata. Cleanup runs only when explicitly requested, independently of citation polling. Case edits change individual letters, and the preview lists every proposed change and skipped recognised occurrence.

## Before and after in Google Docs

Before cleanup, the body contains `FELIS CATUS` in capitals and regular type:

[![Google Docs before cleanup, showing FELIS CATUS in capitals and regular type.](../assets/screenshots/cats-citation-result.jpg)](../assets/screenshots/cats-citation-result.jpg)

After adding `Felis catus` to the approved-name list, previewing and applying the plan, it becomes italic *Felis catus*:

[![Google Docs after cleanup, showing Felis catus in the body in binomial case and italics.](../assets/screenshots/cats-cleanup-result.jpg)](../assets/screenshots/cats-cleanup-result.jpg)

The citation and bibliography remain present. The [walkthrough](../getting-started/cats-walkthrough.md) includes the exact commands and earlier citation-comment steps.
