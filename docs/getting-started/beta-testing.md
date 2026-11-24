# External beta testing

Sign in with a Google account that can edit and comment on the document you want to use.

## Install the beta package

The maintainer can provide a private ZIP containing the Python wheel, desktop OAuth client configuration and setup instructions. It contains no user login tokens. You need Python 3.11 or newer, Node.js and npm installed.

Unzip it, open a terminal in that folder, then on macOS or Linux run:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install "./citegoblin-0.4.0b7-py3-none-any.whl[google]"
citegoblin setup-formatter
citegoblin login --client-secrets oauth-client.json
```

On Windows, create the environment with `py -m venv .venv` and activate it with `.venv\Scripts\activate` in Command Prompt before running the remaining commands.

The browser opens Google’s sign-in, per-file consent screen and document picker. Choose the account you use to edit the document. Select only the document you want to test and click **Insert**. Login tokens stay in your OS keychain.

## Connect a document and run

For another document, or to select a specific link:

```sh
citegoblin connect "GOOGLE_DOC_URL"
```

Choose the displayed document in Google’s picker and click **Insert**. A pasted URL identifies a file; the picker authorises CiteGoblin to access it.

In Google Docs:

1. Write a References heading, select the entire heading and comment `@bib`.
2. Select a passage and comment `@cite` followed by its DOI or PMID.
3. Optionally add a separate `@style apa7` comment.

Then run:

```sh
citegoblin run "GOOGLE_DOC_URL" --dry-run
citegoblin run "GOOGLE_DOC_URL"
```

Replace `GOOGLE_DOC_URL` with the address copied from your browser, keeping the quotes. The first preview for a new document covers bibliography placement; the applying run verifies placement and then processes the remaining commands. Citation and style comments resolve after verification; the bibliography-location comment stays open.

Use a disposable example document first. The [cats walkthrough](cats-walkthrough.md) illustrates the comment commands and results. Local files are small and separated by document under `~/.citegoblin`; see [local storage](../guides/storage.md).

## If sign-in or document access fails

Check that the signed-in account can edit and comment on the document, then select it with `citegoblin connect`. If you use a work or school account, your organisation may restrict third-party apps. See [troubleshooting](../reference/troubleshooting.md).
