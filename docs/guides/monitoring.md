# Run once or monitor a document

Copy the full Google Docs URL from your browser’s address bar and use it in quotes. CiteGoblin extracts the document ID and the URL’s tab automatically. If there is no tab in the URL, a single tab is selected automatically; multiple tabs require the intended tab’s URL or an explicit `--tab`. Raw document IDs are also accepted. See [copy the document URL](../getting-started/first-document.md#copy-the-document-url).

For a new document, select its complete References heading and add an `@bib` or `@references` comment. The first run creates the hidden register and places the bibliography after that heading, then processes the remaining commands. The location comment stays open.

This does not convert existing typed citations. Documents using the earlier `CGPS_DOC_` register can be used directly; Zotero documents require a separate explicit migration.

Preview and process comments:

```sh
citegoblin run "GOOGLE_DOC_URL" --dry-run
citegoblin run "GOOGLE_DOC_URL"
```

For a new or moved bibliography, the first dry run previews placement only; the applying run verifies placement before planning citation and style changes. For an already placed bibliography, the preview covers citation and style updates.

The applying command reads the document afresh. Its latest plan and result are retained in one compressed local run record after completion; incomplete writes keep their recovery files. See [local storage](storage.md). A dry run does not reserve a revision. For an exact saved-plan approval workflow, use the offline commands below followed by `apply`.

Optional polling, started and stopped by the user:

```sh
citegoblin run "GOOGLE_DOC_URL" --watch 60
```

This checks every 60 seconds while the process is running. Stop with Ctrl-C. It installs no background service or schedule. Add another `@refresh` comment when a refresh is needed; editing or deleting managed fields by hand is not a supported citation-editing interface yet.

## API request use

After a location has been successfully bound, its unchanged comment is cached in the run folder and treated as idle when it is the only pending command. New citation commands still read the document and use its current range markers.

An idle poll reads the comments only; it does not fetch the document. For up to 100 comments this is one Google request. Larger comment histories require pagination. An unchanged invalid command with the same existing error reply also needs only that comments read and no writes.

Comment-list reads include complete replies. After an edit, one fresh paginated comment-list read checks all affected command fingerprints before feedback, rather than fetching each thread and its replies separately. The revision guards and post-write document verification remain in place. Each actual comment resolution or error-reply change still requires a write request.

`--watch 60` waits 60 seconds after each pass. Use `--watch 300` for less frequent polling. A run only processes explicit commands; it does not refresh every citation on each poll.
