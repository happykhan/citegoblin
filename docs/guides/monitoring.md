# Run once or monitor a document

The document ID is the part between `/d/` and `/edit` in its URL. Supply the intended tab explicitly, for example `t.0`.

For a new document, put `[[bibliography]]` in a paragraph where the reference list belongs, then initialise its hidden register:

```sh
citegoblin init DOCUMENT_ID --tab t.0 --workdir /private/path/citation-runs --dry-run
citegoblin init DOCUMENT_ID --tab t.0 --workdir /private/path/citation-runs
```

Initialisation does not convert existing typed citations. Documents using the earlier `CGPS_DOC_` register can be used directly; Zotero documents require a separate explicit migration.

Preview and process comments:

```sh
citegoblin run DOCUMENT_ID --tab t.0 --workdir /private/path/citation-runs --dry-run
citegoblin run DOCUMENT_ID --tab t.0 --workdir /private/path/citation-runs
```

The second command reads the document afresh and saves the plan actually applied. A dry run does not reserve a revision. For an exact saved-plan approval workflow, use the offline commands below followed by `apply`.

Optional polling, started and stopped by the user:

```sh
citegoblin run DOCUMENT_ID --tab t.0 --workdir /private/path/citation-runs --watch 60
```

This checks every 60 seconds while the process is running. Stop with Ctrl-C. It installs no background service or schedule. Add another `@refresh` comment when a refresh is needed; editing or deleting managed fields by hand is not a supported citation-editing interface yet.

## API request use

An idle poll reads the comments only; it does not fetch the document. For up to 100 comments this is one Google request. Larger comment histories require pagination. An unchanged invalid command with the same existing error reply also needs only that comments read and no writes.

Comment-list reads include complete replies. After an edit, one fresh paginated comment-list read checks all affected command fingerprints before feedback, rather than fetching each thread and its replies separately. The revision guards and post-write document verification remain in place. Each actual comment resolution or error-reply change still requires a write request.

`--watch 60` waits 60 seconds after each pass. Use `--watch 300` for less frequent polling. A run only processes explicit commands; it does not refresh every citation on each poll.
