# Citation styles

A comment anywhere can set the document style:

```text
@style author-year
```

Bundled styles (names are case-insensitive):

| Comment | Style |
| --- | --- |
| `@style IEEE` | IEEE Reference Guide |
| `@style APA` | APA 7th edition |
| `@style Chicago` | Chicago 18th edition, author–date |
| `@style MLA` | MLA 9th edition, in-text |
| `@style Nature` | Nature, including superscript citation numbers |
| `@style author-year` or `@style Harvard` | Elsevier Harvard |
| `@style Vancouver` | NLM citation-sequence |

`@refresh` recalculates all managed citations and the bibliography. Native Google Docs inline formatting preserves CSL italics, bold, small caps and superscripts.

```sh
citegoblin styles list
citegoblin styles install cell
```

Additional in-text journal styles can be installed by their [Zotero CSL style ID](https://www.zotero.org/styles), then selected using `@style cell`, for example. Installations use a pinned snapshot of the official CSL repository, resolve dependent styles through their parent, and retain the source licences. Install the same additional style on each computer processing the document. Footnote/endnote styles and non-English locale files are not supported yet.
