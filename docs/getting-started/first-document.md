# Your first document

Use a separate test document for your first run. After [installation](install.md) and [Google sign-in](google-login.md), you need its document ID and tab ID.

For a complete example with Google Docs screenshots, follow the [cats walkthrough](cats-walkthrough.md).

## Find the IDs

In a URL such as:

```text
https://docs.google.com/document/d/DOCUMENT_ID/edit?tab=t.0
```

`DOCUMENT_ID` is the document ID and `t.0` is the tab. The `run` and `init` commands currently take the ID, not the full URL. Choose the intended tab explicitly.

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
citegoblin run DOCUMENT_ID --tab t.0 --workdir ./runs --dry-run
```

Apply them:

```sh
citegoblin run DOCUMENT_ID --tab t.0 --workdir ./runs
```

After verification, the citation and bibliography should be present and the comment resolved. If a command fails, its comment stays open with an error reply.

## Keep checking for new comments

```sh
citegoblin run DOCUMENT_ID --tab t.0 --workdir ./runs --watch 60
```

This checks roughly once a minute while the process is running. Stop with Ctrl-C. See [monitoring](../guides/monitoring.md) for request use and saved-plan behaviour.
