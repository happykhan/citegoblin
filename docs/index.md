# CiteGoblin

Manage citations in Google Docs by selecting text and leaving a comment. CiteGoblin looks up the reference, inserts the citation, updates the bibliography and resolves the comment after checking the result.

```text
@cite https://doi.org/10.1093/bioinformatics/btp324
```

Change the document's citation style with another comment:

```text
@style IEEE
```

## Start here

1. [Install the CLI](getting-started/install.md).
2. [Sign in with Google](getting-started/google-login.md).
3. [Prepare your first document](getting-started/first-document.md).

Google Docs editing and commenting access is required. The maintainer's Google application currently accepts CGPS accounts; users obtain its client configuration privately. You can also register your own Google application.

## What you can do

| Task | Guide |
| --- | --- |
| Cite a DOI, PMID or complete journal reference | [Citation comments](guides/citations.md) |
| Use IEEE, APA, Harvard, Vancouver and other CSL styles | [Citation styles](guides/styles.md) |
| Process a document once or check it periodically | [Monitoring](guides/monitoring.md) |
| Normalise case and italicise approved Latin binomials | [Scientific names](guides/binomials.md) |
| Export BibTeX, RIS or EndNote tagged files | [Export references](guides/exports.md) |

CiteGoblin uses Python, Google APIs and a local CSL formatter. It does not require Zotero or an AI service. Failed citation commands stay open with one error reply that is updated on later runs. Scientific-name formatting is a separate, opt-in command with a preview.

See the [verification and limits](reference/integrity.md) before using it on an existing manuscript. [Release notes and downloads](https://github.com/happykhan/citegoblin/releases) are on GitHub.
