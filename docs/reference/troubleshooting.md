# Troubleshooting

## Google sign-in needs a desktop OAuth client

An API key is not enough. CGPS users obtain the registered client configuration privately from the maintainer. Other installations need a Google Cloud desktop OAuth client with Docs and Drive APIs enabled. Follow [Google sign-in](../getting-started/google-login.md).

## Google returned HTTP 403

Check that both Google Docs API and Google Drive API are enabled in the OAuth client's project, the signed-in account can edit and comment on the document, and your organisation allows the application. The maintainer's registered app currently accepts CGPS accounts only.

## No supported operating-system keychain is available

Unlock or configure an OS keychain, or explicitly choose file storage:

```sh
citegoblin login --client-secrets client.json --token-file /private/path/token.json
```

Keep the token file private. File storage is not chosen automatically.

## Quote has multiple matches or the comment anchor is unavailable

CiteGoblin needs to locate the selected passage exactly. Select a longer, unique passage and add the command there. If Google does not expose the selected quote, CiteGoblin attempts to recover it from a DOCX export. Missing or ambiguous anchors remain errors.

## A pasted reference has no matching Crossref record

Check the supplied authors, year, title, journal, volume, issue and pages. The matcher does not choose the first approximate search hit. Supply the DOI or PMID when the pasted format or metadata cannot be matched uniquely.

## Style is not installed

Use `citegoblin styles list` to see available styles. Install another by its CSL style ID:

```sh
citegoblin styles install cell
```

Then use `@style cell`. Footnote/endnote styles and non-English locale files are not supported yet.

## Document changed or a previous run is incomplete

Do not replay an uncertain write. Inspect the live document and run again to make a fresh plan. A saved plan cannot be applied after its required document revision has changed.

## A name was not italicised

The scientific-name module only changes names in its approved catalogue. Add missing names through `--names approved-names.txt`. Abbreviations need `--abbreviations` and a unique earlier full-name mention. Managed references, hyperlinks and pending suggestions are skipped. See [scientific names](../guides/binomials.md).
