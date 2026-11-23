# Add citations with comments

The [Google Docs walkthrough](../getting-started/cats-walkthrough.md) shows the selection, command comments and generated reference in a real document.

Select the passage and add a comment containing exactly:

```text
@cite 10.1234/example
```

CiteGoblin places the citation at the end of that selection, before its final sentence punctuation. Select enough text to identify the location uniquely. If the selected wording occurs more than once, CiteGoblin reports the ambiguity and leaves that command unapplied.

Choose the document's [citation style](styles.md) with a separate `@style` comment.

## Choose where the bibliography goes

Select the complete “References” heading and add a comment containing `@bib` or `@references`. CiteGoblin inserts the bibliography in a new paragraph immediately after it, creating the reference register automatically if needed. A hidden named range tracks the generated list, and the location comment stays open. Keep one open bibliography-location comment per selected tab.

For an existing managed document, a location comment on the heading immediately before its bibliography adopts the current list. To move it elsewhere, resolve the old location comment yourself, select the new complete heading and add a new `@bib` or `@references` comment. The next run moves the managed bibliography; it does not copy it or overwrite unmarked text below the heading. The old heading is left in place.

Resolving the location comment does not delete or freeze the reference list: CiteGoblin continues tracking it through its hidden range. Add another location comment only when you want to specify or change its placement.

Regular comments are ignored. Apart from bibliography-location comments, once a command has updated the document and passed readback verification, CiteGoblin resolves its comment, preserving the thread. Successful commands are also recorded in document metadata, so a failed comment resolution can be retried without inserting the citation again.

Failed commands stay open with one reply beginning `CiteGoblin error [v1]:`. Reruns update that same reply when the error changes and do not post it again when unchanged. If a reply creation times out after reaching Google, the next run looks for the existing reply before creating one. Human replies are left untouched. Edit a failed command and run again. Edit an already successful citation command only if you intend to add another citation; editing a comment is not a reference-replacement operation.

You can also paste a complete APA-like author–year journal reference after `@cite`:

```text
@cite Derwing, T. M., Rossiter, M. J., & Munro, M. J. (2002). Teaching native speakers to listen to foreign-accented speech. Journal of Multilingual and Multicultural Development, 23(4), 245-259.
```

CiteGoblin searches Crossref programmatically and accepts one matching DOI only after checking title, author surnames and initials, year, journal, volume, issue (when supplied), and pages. It does not simply choose the first search hit. Zero matches, conflicting details or multiple matching DOIs leave the command open with one maintained error reply. This currently supports the author-initials, parenthesised-year, journal/volume/pages format above; other reference formats should use a DOI or PMID. GitHub and general webpages still require supplied reference metadata.

DOIs can also be supplied as DOI links or with a `DOI:` prefix. PubMed articles accept all these forms:

```text
@cite PMID: 42127953
@cite PMID:42127953
@cite https://pubmed.ncbi.nlm.nih.gov/42127953/
```

A newline after `@cite` is also accepted. PubMed identifiers are looked up through NCBI EFetch; article title, authors, publication date, journal, volume, issue, pages or article number, and DOI are converted into CSL metadata. Missing required metadata or mismatched identifiers produce an error rather than invented fields. DOI and PMID references for the same article are deduplicated using their shared identifiers.

For a reference already in the register, use `@cite ref:r0123456789abcdef`. For websites or reports without a DOI, provide their CSL-JSON metadata using `--references references.json`, then use `@cite url:https://example.org/report`. The file must be a JSON array of CSL records with titles and matching URLs. CiteGoblin does not guess authors or dates from webpages.
