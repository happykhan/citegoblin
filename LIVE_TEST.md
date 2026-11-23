# Live integration verification

Passed on 23 November 2026 against a separate, disposable Google Doc about BWA, Bowtie 2 and Minimap2. The WHO manuscript was not used or changed.

## Actual path tested

1. Registered a separate internal CiteGoblin Google Cloud project and desktop OAuth client; enabled Docs and Drive APIs.
2. Used `citegoblin login` for real browser consent and stored tokens in macOS Keychain.
3. Created native, text-selected citation comments in the Google Docs editor.
4. Initialised the citation register with the installed CLI.
5. Ran a dry run followed by the actual command processor.
6. Verified native document content and metadata after each change, then inspected the rendered document in the browser.

## Results

- Four initial citations generated three reference records. DOI and PMID inputs for Bowtie 2 shared one record.
- All citations appeared before their sentence's full stop.
- Supported DOI URLs, `PMID: 22388286`, and a PubMed URL on a new line after `@cite`.
- Invalid input remained open with one error reply.
- An unchanged rerun inserted no new citation and posted no duplicate error reply.
- Changing the invalid input to a different error updated the same reply ID.
- Correcting the command inserted a fifth citation, retained three references, and resolved the original thread.
- Switching to Vancouver and back to author–year updated citations and bibliography and resolved the style commands.
- Seven successful command threads were resolved and remained present; none was deleted.
- Ordinary `[42]` and Unicode text remained unchanged.
- A new client reused saved authorisation without another browser sign-in.
- Expiring the saved access token triggered a real Google refresh, updated the keychain and restored document access without another sign-in.
- All 41 automated tests passed after this run.

## Scope

The registered application is currently internal to the CGPS organisation. This verifies the macOS desktop OAuth workflow; external account onboarding, other operating-system keychains, cross-author comment resolution and production-scale documents have not been live-tested in this run. Footnotes and multi-paragraph citation selections remain unsupported as documented in the README.

Document exports, comment transcripts, run journals, screenshots and all credentials are kept outside the public repository. The report intentionally omits private document IDs and OAuth credentials.

## Full-reference lookup follow-up

Also passed on 23 November 2026 using a user-authored native comment containing the complete Derwing, Rossiter and Munro (2002) reference, with no DOI supplied. CiteGoblin searched Crossref, checked all supplied bibliographic fields, found DOI `10.1080/01434630208666468`, inserted `(Derwing et al., 2002)`, refreshed the bibliography and resolved the original comment. A second run added no duplicate citation or reference. The expanded automated suite passed all 49 tests. Unsupported `@style IEEE` remained open with a maintained error reply.


## CSL style expansion

IEEE, Nature and APA styles passed live verification in the disposable document. Nature citation numbers retained native superscript formatting; APA bibliography italics were preserved. Switching back to IEEE cleared the superscripts. The original user-authored `@style IEEE` command completed and was resolved. Seven styles are bundled, with additional compatible in-text styles installable from the pinned official CSL repository. The expanded suite passes 70 automated tests.


## Scientific-name formatting

The opt-in binomial module passed live preview, guarded apply and readback verification on the disposable document. Four names were normalised and italicised: all-caps *Escherichia coli*, title-case *Staphylococcus aureus*, mixed-case *Candida albicans*, and context-supported *E. coli*. Ordinary title-case text, `ST131`, all six existing citations and four reference records remained intact. A second pass proposed zero changes. The expanded automated suite passes 82 tests.
