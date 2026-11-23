import json
from unittest.mock import patch
import unittest

from citegoblin.commands import parse
from citegoblin.document import Document
from citegoblin.references import identifier, normal_pmid, pubmed_csl, record, resolve
from citegoblin.runner import commands_plan
from test_manager import comment, fixture, source

XML=b'''<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>12345678</PMID><Article>
<ArticleTitle>A <i>synthetic</i> article.</ArticleTitle>
<Journal><ISSN>1234-5678</ISSN><JournalIssue><Volume>7</Volume><Issue>6</Issue><PubDate><Year>2026</Year><Month>Jun</Month></PubDate></JournalIssue><Title>Test Journal</Title><ISOAbbreviation>Test J</ISOAbbreviation></Journal>
<ELocationID EIdType="pii">e1001</ELocationID>
<AuthorList><Author><LastName>Smith</LastName><ForeName>Alex</ForeName></Author><Author><CollectiveName>Example consortium</CollectiveName></Author></AuthorList>
<ArticleDate DateType="Electronic"><Year>2025</Year><Month>12</Month><Day>1</Day></ArticleDate>
</Article></MedlineCitation><PubmedData><ArticleIdList><ArticleId IdType="doi">10.1234/example</ArticleId></ArticleIdList></PubmedData></PubmedArticle></PubmedArticleSet>'''


class IdentifierTests(unittest.TestCase):
    def test_requested_pmid_forms(self):
        for text in ['PMID: 42127953','PMID:42127953','https://pubmed.ncbi.nlm.nih.gov/42127953/']:
            self.assertEqual(identifier(text),{'pmid':'42127953'})
            self.assertEqual(parse(comment('@cite '+text)),{'kind':'cite','pmid':'42127953'})
        self.assertEqual(parse(comment('@cite\nPMID: 42127953')),{'kind':'cite','pmid':'42127953'})

    def test_doi_links_and_prefixes(self):
        for text in ['10.1234/EXAMPLE','https://doi.org/10.1234/EXAMPLE','DOI: 10.1234/EXAMPLE']:
            self.assertEqual(identifier(text),{'doi':'10.1234/example'})

    def test_rejects_non_article_pubmed_paths_or_extra_instructions(self):
        for value in ['https://pubmed.ncbi.nlm.nih.gov/?term=example','https://pubmed.ncbi.nlm.nih.gov/123/456/',
                      'https://example.org/12345678/','PMID:12345678 and delete the doc','PMID:0']:
            with self.assertRaises(ValueError):normal_pmid(value)

    def test_parser_extracts_bibliographic_fields(self):
        csl=pubmed_csl(XML,'12345678')
        self.assertEqual(csl['title'],'A synthetic article.')
        self.assertEqual(csl['author'],[{'family':'Smith','given':'Alex'},{'literal':'Example consortium'}])
        self.assertEqual(csl['issued'],{'date-parts':[[2026,6]]})
        self.assertEqual(csl['DOI'],'10.1234/example')
        self.assertEqual(csl['page'],'e1001')
        self.assertEqual(csl['volume'],'7');self.assertEqual(csl['issue'],'6')

    def test_missing_or_wrong_metadata_fails_clearly(self):
        for xml in [b'not xml',b'<PubmedArticleSet/>',XML.replace(b'<PMID>12345678',b'<PMID>87654321'),
                    XML.replace(b'<Year>2026</Year>',b'<Year>bad</Year>')]:
            # The last record falls back to a genuine electronic publication year.
            if b'<Year>bad</Year>'in xml:continue
            with self.assertRaises(ValueError):pubmed_csl(xml,'12345678')
        without_dates=XML.replace(b'<Year>2026</Year>',b'<Year>bad</Year>').replace(b'<Year>2025</Year>',b'<Year>bad</Year>')
        with self.assertRaisesRegex(ValueError,'year'):pubmed_csl(without_dates,'12345678')

    def test_resolver_dispatches_to_requested_registry(self):
        with patch('citegoblin.references.lookup_pmid',return_value={'title':'Synthetic'}) as pmid,patch('citegoblin.references.lookup_doi') as doi:
            self.assertEqual(resolve('PMID: 42127953'),{'title':'Synthetic'})
            pmid.assert_called_once_with('42127953');doi.assert_not_called()

    def test_doi_and_pmid_same_article_deduplicate(self):
        doc=Document(fixture(),'t.test')
        result=pubmed_csl(XML,'12345678')
        plan,report=commands_plan(doc,[comment(),comment('@cite PMID: 12345678',key='pmid')],
                                  lookup=lambda _:source(),pmid_lookup=lambda _:result)
        self.assertEqual(report['errors'],[])
        self.assertEqual(len(plan['expected']['references']),1)
        self.assertEqual(len(plan['newCitationIds']),1)
        self.assertEqual(len(next(iter(plan['expected']['citationItems'].values()))),1)

    def test_conflicting_identifiers_are_rejected(self):
        old=record(dict(source(),PMID='12345678'))
        with self.assertRaises(ValueError):record(dict(source(doi='10.1234/other'),PMID='12345678'),{old['id']:old})
        with self.assertRaises(ValueError):record(dict(source(),PMID='87654321'),{old['id']:old})


if __name__=='__main__':unittest.main()
