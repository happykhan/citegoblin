# External beta testing

CiteGoblin’s Google application is configured as **External → Testing**, requesting only `drive.file`. Before trying it, give the maintainer the email address of the Google account you will use. That account must be added to the test-user list. It also needs editing and commenting access to your chosen document.

## Install the beta package

The maintainer can provide a private ZIP containing the Python wheel, desktop OAuth client configuration and setup instructions. It contains no user login tokens. You need Python 3.11 or newer, Node.js and npm installed.

Unzip it, open a terminal in that folder, then on macOS or Linux run:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install "./citegoblin-0.4.0b1-py3-none-any.whl[google]"
citegoblin setup-formatter
citegoblin login --client-secrets oauth-client.json
```

On Windows, create the environment with `py -m venv .venv` and activate it with `.venv\Scripts\activate` in Command Prompt before running the remaining commands.

The browser opens Google’s sign-in, per-file consent screen and document picker. Choose the account on the beta test list. Select only the document you want to test and click **Insert**. Login tokens stay in your OS keychain.

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

## Testing limits

Only allowlisted Google accounts can sign in during Testing mode. Google limits the test list to 100 users, and refresh tokens for this scope normally expire after seven days. Sign in again if needed. A Workspace administrator may also block third-party apps.

No full-Drive or all-Documents permission is requested. During migration from the broad-access prototype, CiteGoblin revokes its earlier saved broad grant and asks you to select the files again. It never silently reuses a saved broader token.

If Google denies access to a document, check the account, test-user list, existing editing/commenting permissions and `connect` selection. Send the maintainer the error message, operating system and CiteGoblin version. Do not send tokens, OAuth callback URLs or private manuscript text.

## Maintainer: add testers later

Open [Google Cloud → CiteGoblin → Audience](https://console.cloud.google.com/auth/audience?project=citegoblin), confirm **External** and **Testing**, then choose **Add users**. Enter each tester’s Google-account email and save. Adding test users does not send invitation emails; distribute the beta package and these instructions separately.

See Google’s [testing rules](https://developers.google.com/identity/protocols/oauth2/production-readiness/overview) and [desktop per-file Picker flow](https://developers.google.com/workspace/drive/picker/guides/desktop-mobile-picker).
