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

Failed commands stay open with one reply beginning `CiteGoblin error [v1]:`. Each error includes a Help link to the relevant guide page. Reruns update that same reply when the error changes and do not post it again when unchanged. If a reply creation times out after reaching Google, the next run looks for the existing reply before creating one. Human replies are left untouched. Edit a failed command and run again. Edit an already successful citation command only if you intend to add another citation; editing a comment is not a reference-replacement operation.

## Paste a journal reference

Paste one full journal article reference after `@cite`. CiteGoblin accepts the journal reference layouts used by APA, Chicago author–date, Harvard, IEEE, MLA, Nature and Vancouver. The pasted style can differ from your document’s citation style.

For example, a Vancouver reference:

```text
@cite Derwing TM, Rossiter MJ, Munro MJ. Teaching native speakers to listen to foreign-accented speech. Journal of Multilingual and Multicultural Development. 2002;23(4):245–59.
```

Include the authors, article title, journal, year, volume and pages or article number. CiteGoblin checks these details against Crossref, including the issue and DOI when supplied. It adds the citation only when one DOI matches. If the entry is incomplete, the format is unsupported or there is no unique match, use a DOI or PMID. For an author–year fragment such as `(Derwing et al., 2002)`, use the DOI or PMID directly.

DOIs can also be supplied as DOI links or with a `DOI:` prefix. PubMed articles accept all these forms:

```text
@cite PMID: 42127953
@cite PMID:42127953
@cite https://pubmed.ncbi.nlm.nih.gov/42127953/
```

A newline after `@cite` is also accepted. PubMed identifiers are looked up through NCBI EFetch; article title, authors, publication date, journal, volume, issue, pages or article number, and DOI are converted into CSL metadata. Missing required metadata or mismatched identifiers produce an error rather than invented fields. DOI and PMID references for the same article are deduplicated using their shared identifiers.

For a reference already in the register, use `@cite ref:r0123456789abcdef`. For websites or reports without a DOI, provide their CSL-JSON metadata using `--references references.json`, then use `@cite url:https://example.org/report`. The file must be a JSON array of CSL records with titles and matching URLs. CiteGoblin does not guess authors or dates from webpages.


## Manual edits to References

CiteGoblin tracks the text it last generated in the managed References list. If you edit that text in Google Docs, a later run that would rewrite the list pauses before changing inline citations or references. Cleanup uses the same check. On an older document, CiteGoblin compares the list with what it can generate from the stored records and current style.

Keep a copy of any edits you want to retain. To resume, restore the generated text or add a comment containing `@refresh replace-references` and run CiteGoblin. That command replaces the edited list with a freshly generated one. It applies once and resolves after verification.
