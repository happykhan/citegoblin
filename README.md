# CiteGoblin

Manage Google Docs citations through comments. Select a passage, leave an `@cite` command, and run the CLI. CiteGoblin looks up the reference, inserts the citation, updates the bibliography and resolves the comment after verification.

**[Documentation](https://happykhan.github.io/citegoblin/)** · **[Releases](https://github.com/happykhan/citegoblin/releases)**

```text
@cite https://doi.org/10.1093/bioinformatics/btp324
@cite PMID:22388286
@style IEEE
```

Supports DOI/PMID inputs, checked matching for complete author–year journal references, seven bundled CSL styles, additional compatible journal styles, and BibTeX/RIS/EndNote tagged exports. The [cleanup module](https://happykhan.github.io/citegoblin/guides/cleanup/) normalises scientific-name case and italics and rebuilds managed citations and the bibliography, with a preview before applying changes.

## Install

Requires Python 3.11+, Git, Node.js and npm. On macOS/Linux:

```sh
git clone https://github.com/happykhan/citegoblin.git
cd citegoblin
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[google]'
citegoblin setup-formatter
```

On Windows, activate with `.venv\Scripts\activate` instead.

## Sign in and start

CGPS users obtain the desktop OAuth client configuration privately from the maintainer. Other installations can register their own Google application. The maintainer's application currently accepts CGPS accounts only.

```sh
citegoblin login --client-secrets /path/to/client.json
```

Select the complete “References” heading in Google Docs and add a comment containing `@bib` (or `@references`). Add your `@cite` comments, then process the intended tab:

```sh
citegoblin run "GOOGLE_DOC_URL" --dry-run
citegoblin run "GOOGLE_DOC_URL"
```

The bibliography goes below the heading. Its location comment stays open; successful citation and style comments are resolved. No placeholder or separate initialisation is needed.

Replace `GOOGLE_DOC_URL` with the full address copied from your browser, keeping the quotes. The ID and URL tab are extracted automatically; a document with only one tab needs no tab setting. Raw document IDs and explicit `--tab` values also work.

Add `--watch 60` to check periodically. See the [first-document guide](https://happykhan.github.io/citegoblin/getting-started/first-document/) for document IDs, shared documents and comment selection.

Local citation caches are kept separately under `~/.citegoblin/documents/DOCUMENT_ID/tabs/TAB_ID/`. The Google Doc remains the shared citation store. See [local storage](https://happykhan.github.io/citegoblin/guides/storage/).

## Development

```sh
pip install -e '.[google,test,docs]'
citegoblin setup-formatter
python -m unittest discover -s tests -v
zensical serve
```

Build the docs with `zensical build --clean`. The documentation lives in `docs/`; GitHub Actions deploys main-branch changes to GitHub Pages. See [LIVE_TEST.md](LIVE_TEST.md) for live verification and [THIRD_PARTY.md](THIRD_PARTY.md) for dependency licences.

No user tokens, OAuth client configuration, manuscript exports or private document IDs are included in this repository.
