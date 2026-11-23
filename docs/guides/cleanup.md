# Cleanup in References

`cleanup` works only on CiteGoblin’s generated **References** list. It corrects scientific-name case and italics within reference text and can rebuild the bibliography in the selected citation style. Body text, body formatting and in-text citations stay unchanged.

Preview and apply:

```sh
citegoblin cleanup plan "GOOGLE_DOC_URL" --output cleanup-plan.json
citegoblin cleanup apply cleanup-plan.json --journal cleanup-journal.json
```

The preview identifies its scope as **References only** and lists names that need a case or typography change. For example, a reference title containing `FELIS CATUS` becomes *Felis catus*: genus initial capital, species epithet lowercase, both words italic, small caps disabled. An already correctly cased but non-italic name also receives italics.

## Checks

The default `--check all` applies scientific-name rules and rebuilds the References list using the stored reference metadata and selected CSL style. Use `--check names` to clean names within the existing list while retaining its current layout, or `--check bibliography` to rebuild reference formatting with any previously enabled scientific-name rules.

The document must already have a managed References list. Select the complete References heading, add an `@bib` or `@references` comment and run CiteGoblin first. Cleanup uses that hidden bibliography range; it does not infer a region from an ordinary heading.

Cleanup settings are saved with the document. Later citation updates, bibliography refreshes and explicit style changes apply those rules to the generated reference text again, so the scientific-name italics survive regeneration. Stored source metadata is retained as supplied; the rules affect the rendered References list.

## Approved scientific names

The bundled catalogue contains 21 approved binomials, including *Felis catus*, checked against NCBI Taxonomy on 23 November 2026. Names retain their identity; cleanup does not update taxonomy. Extend the list with a text file containing one full binomial per line:

```sh
citegoblin cleanup plan "GOOGLE_DOC_URL" \
  --names approved-names.txt --output cleanup-plan.json
```

Add `--abbreviations` to format a name such as *E. coli* only when an earlier full-name mention in the same reference supplies unique genus context. Abbreviations are not expanded. Other title wording, strain codes, whitespace and URLs are preserved. The name catalogue is local; scanning makes no taxonomy API requests.

## Before and after in Google Docs

Before cleanup, *Felis catus* appears in regular type within the reference title:

[![Google Docs before cleanup: Felis catus is not italicised in the reference title.](../assets/screenshots/cats-citation-result.jpg)](../assets/screenshots/cats-citation-result.jpg)

After cleanup, the name is italicised **inside References**. The body remains exactly as written:

[![Google Docs after cleanup: Felis catus is italicised in the reference title; the uppercase body example and in-text citation are unchanged.](../assets/screenshots/cats-cleanup-result.jpg)](../assets/screenshots/cats-cleanup-result.jpg)

The [walkthrough](../getting-started/cats-walkthrough.md#5-preview-and-apply-cleanup) includes the comment commands and cleanup steps.

## Verification

Every plan is guarded by the document revision. Before writing, cleanup checks that its text and formatting requests are confined to the managed bibliography. Readback verifies reference text and styles, source mappings, stored cleanup rules, and unchanged body text and formatting. References containing pending suggestions must be reviewed first.

Generate a new plan with this version. Earlier cleanup plans that targeted body text are rejected. An interrupted or uncertain write is retained for inspection and is never replayed automatically.
