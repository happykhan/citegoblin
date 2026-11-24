# Citation styles

A comment anywhere can set the document style:

```text
@style author-year
```

## Compare the seven bundled styles

Each row shows how CiteGoblin cites the same journal article in the text and formats its entry in References. Style commands are case-insensitive.

| Style command | In-text citation | Reference list entry |
| --- | --- | --- |
| `@style IEEE` | [1] | [1] T. M. Derwing, M. J. Rossiter, and M. J. Munro, ‘Teaching Native Speakers to Listen to Foreign-accented Speech’, *Journal of Multilingual and Multicultural Development*, vol. 23, no. 4, pp. 245–259, Sep. 2002, doi: 10.1080/01434630208666468. |
| `@style APA` (7th ed.) | (Derwing et al., 2002) | Derwing, T. M., Rossiter, M. J., & Munro, M. J. (2002). Teaching Native Speakers to Listen to Foreign-accented Speech. *Journal of Multilingual and Multicultural Development*, *23*(4), 245–259. https://doi.org/10.1080/01434630208666468 |
| `@style Chicago` (18th ed., author–date) | (Derwing et al. 2002) | Derwing, Tracey M., Marian J. Rossiter, and Murray J. Munro. 2002. ‘Teaching Native Speakers to Listen to Foreign-Accented Speech’. *Journal of Multilingual and Multicultural Development* 23 (4): 245–59. https://doi.org/10.1080/01434630208666468. |
| `@style MLA` (9th ed.) | (Derwing et al.) | Derwing, Tracey M., et al. ‘Teaching Native Speakers to Listen to Foreign-Accented Speech’. *Journal of Multilingual and Multicultural Development*, vol. 23, no. 4, Sept. 2002, pp. 245–59, https://doi.org/10.1080/01434630208666468. |
| `@style Nature` | <sup>1</sup> | 1. Derwing, T. M., Rossiter, M. J. & Munro, M. J. Teaching Native Speakers to Listen to Foreign-accented Speech. *Journal of Multilingual and Multicultural Development* **23**, 245–259 (2002). |
| `@style Harvard` (Elsevier Harvard) | (Derwing et al., 2002) | Derwing, T.M., Rossiter, M.J., Munro, M.J., 2002. Teaching Native Speakers to Listen to Foreign-accented Speech. Journal of Multilingual and Multicultural Development 23, 245–259. https://doi.org/10.1080/01434630208666468 |
| `@style Vancouver` (NLM citation-sequence) | (1) | 1. Derwing TM, Rossiter MJ, Munro MJ. Teaching Native Speakers to Listen to Foreign-accented Speech. Journal of Multilingual and Multicultural Development. 2002 Sep;23(4):245–59. doi:10.1080/01434630208666468 |

`@style author-year` also selects Elsevier Harvard.

You can paste a complete journal reference in any of these seven styles after `@cite`, regardless of the style selected for your document. CiteGoblin adds a citation only when it finds a unique Crossref match. If it can't verify a match, use a DOI or PMID. See [how to paste a reference](citations.md#paste-a-journal-reference).

`@refresh` recalculates all managed citations and the bibliography. Native Google Docs inline formatting preserves CSL italics, bold, small caps and superscripts.

```sh
citegoblin styles list
citegoblin styles install cell
```

Additional in-text journal styles can be installed by their [Zotero CSL style ID](https://www.zotero.org/styles), then selected using `@style cell`, for example. Installations use a pinned snapshot of the official CSL repository, resolve dependent styles through their parent, and retain the source licences. Install the same additional style on each computer processing the document. Footnote/endnote styles and non-English locale files are not supported yet.
