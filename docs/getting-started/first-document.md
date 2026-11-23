# Your first document

Use a separate test document for your first run. After [installation](install.md) and [Google sign-in](google-login.md), you need its document ID and tab ID.

## Find the IDs

In a URL such as:

```text
https://docs.google.com/document/d/DOCUMENT_ID/edit?tab=t.0
```

`DOCUMENT_ID` is the document ID and `t.0` is the tab. The `run` and `init` commands currently take the ID, not the full URL. Choose the intended tab explicitly.

## Initialise the reference register

Put this placeholder in its own paragraph where the bibliography belongs:

```text
[[bibliography]]
```

Then run:

```sh
citegoblin init DOCUMENT_ID --tab t.0 --workdir ./runs
```

This creates the hidden reference register. Existing manually typed citations are not automatically converted. A document already managed by CiteGoblin does not need initialising again.

## Add a citation comment

Select the passage you want to cite and add this comment:

```text
@cite 10.1093/bioinformatics/btp324
```

The citation goes at the end of the selected passage, before final sentence punctuation. Choose enough text to identify the location uniquely.

Preview the changes:

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
