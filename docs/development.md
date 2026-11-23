# Development

```sh
.venv/bin/pip install -e '.[google,test]'
.venv/bin/python -m unittest discover -s tests -v
```

Tests use synthetic documents only. Do not commit manuscript exports, comments, credentials or private run journals.

## Work on the documentation

The documentation uses [Zensical](https://zensical.org/docs/get-started/). From the repository root:

```sh
pip install -e '.[docs]'
zensical serve
```

Open the local address printed by Zensical. Build the static files with:

```sh
zensical build --clean --strict
```

Markdown pages live in `docs/`; navigation and site settings are in `zensical.toml`. GitHub Actions builds pull requests and deploys the main branch to GitHub Pages.

## Dependencies and licences

Project code: MIT. Bundled CSL styles and locale retain their upstream licence declarations; see [third-party notices](https://github.com/happykhan/citegoblin/blob/main/THIRD_PARTY.md).
