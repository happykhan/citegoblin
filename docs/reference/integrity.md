# Verification and limitations

- Reference IDs and citation source mappings live in hidden Google Docs named ranges, not in bracket-number patterns. Ordinary `[42]` text is untouched.
- Uses UTF-16 document offsets, including non-BMP characters.
- Each write is guarded by the document revision. Concurrent changes stop the operation rather than being overwritten.
- Citation replacement and its metadata stay in the same atomic API batch. A large refresh can span several batches; the entire refresh is not a single transaction.
- An interrupted or uncertain write leaves a journal and cannot be replayed blindly. Inspect live state and make a fresh plan.
- Readback checks citation text, source mappings, reference metadata, bibliography, other body text, and table/image counts. It is not a visual layout check.
- Pending suggestions affecting citation text or a selected passage block changes by default. The explicit override is for separately reviewed cases.
- Body and table-cell text are supported. Footnote, header and footer citations are not supported. Multi-paragraph selections are not supported.
- DOI lookup uses Crossref. Non-Crossref DOIs require supplied CSL metadata. Metadata is not proof that a paper supports a claim.
- Uncited register records are retained in the bibliography for compatibility with earlier documents. Removing references and changing an existing citation's sources need a future explicit interface.
- Live-tested on 23 November 2026 against a disposable Google Doc using CiteGoblin’s own desktop OAuth client: citation insertion, bibliography/style refresh, comment resolution, error-reply updates, login reuse and token refresh passed. See [live verification report](https://github.com/happykhan/citegoblin/blob/main/LIVE_TEST.md). The registered test application currently permits CGPS organisation accounts only; external distribution requires separate Google audience/publishing configuration.
