# Your first document

Use a separate test document for your first run. After [installation](install.md) and [Google sign-in](google-login.md), copy its full URL from your browser’s address bar. You do not need to extract an ID yourself.

For a complete example with Google Docs screenshots, follow the [cats walkthrough](cats-walkthrough.md).

## Copy the document URL

Open your document in Google Docs. Click the browser’s address bar and copy the complete address, including any `?tab=...` part. Paste that address inside quotes in the command:

```sh
citegoblin run "GOOGLE_DOC_URL" --dry-run
```

Replace `GOOGLE_DOC_URL` with your copied link. For example, a link has this shape:

```text
https://docs.google.com/document/d/EXAMPLE_DOCUMENT_ID/edit?tab=t.0
```

CiteGoblin extracts the document ID automatically. Links ending in `?usp=sharing` also work. Keep URLs in quotes so your shell does not interpret `&` or other URL characters.

If you prefer using the ID directly, it is the text **between `/d/` and the next `/`**. In the example above, that is `EXAMPLE_DOCUMENT_ID`. It is not the document title. Both forms work:

```sh
citegoblin run "GOOGLE_DOC_URL"
citegoblin run DOCUMENT_ID --tab t.0
```

A `tab` value in the URL selects that tab automatically. If the link has no tab value, CiteGoblin selects a single-tab document automatically. For a document with multiple tabs, open the intended tab in Google Docs and copy its updated URL, or supply `--tab TAB_ID`. An explicit `--tab` overrides the URL’s tab value. CiteGoblin refuses an ambiguous choice.

## Mark the bibliography location

Write “References” as its own paragraph or heading. Select the whole heading and add a comment containing:

```text
@bib
```

`@references` is an alias. CiteGoblin puts the bibliography in a new paragraph immediately after that heading. This comment stays open as a persistent location instruction. The hidden `CGPS_BIB_` range tracks the generated reference list, while `CGPS_DOC_` stores the register and the location comment's ID.

No `[[bibliography]]` placeholder or separate `init` command is needed. The first `run` creates the register and places the bibliography before processing citation and style commands. Existing manually typed citations are not automatically converted. Keep one open bibliography-location comment per selected tab.

## Add a citation comment

Select the passage you want to cite and add this comment:

```text
@cite 10.1093/bioinformatics/btp324
```

The citation goes at the end of the selected passage, before final sentence punctuation. Choose enough text to identify the location uniquely.

Preview the changes. On a new document, the first preview covers bibliography setup; applying the run performs that setup and then processes the other commands. Subsequent previews cover citation changes:

```sh
citegoblin run "GOOGLE_DOC_URL" --dry-run
```

Apply them:

```sh
citegoblin run "GOOGLE_DOC_URL"
```

After verification, the citation and bibliography should be present and the comment resolved. If a command fails, its comment stays open with an error reply.

## Keep checking for new comments

```sh
citegoblin run "GOOGLE_DOC_URL" --watch 60
```

This checks roughly once a minute while the process is running. Stop with Ctrl-C. See [monitoring](../guides/monitoring.md) for request use and saved-plan behaviour.
