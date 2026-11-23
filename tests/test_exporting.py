import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import bibtexparser
import rispy

from citegoblin.cli import main
from citegoblin.exporting import export_references


def registry():
    article={'type':'article-journal','title':'<i>RNA</i> & {DNA}: 50% #1_case',
             'author':[{'family':'García','given':'María'},{'literal':'Research & Development Consortium'}],
             'issued':{'date-parts':[[2026,11,23]]},'container-title':'Synthetic Journal',
             'volume':'23','issue':'4','page':'245–59','DOI':'10.1234/test_a','URL':'https://example.org/a_b',
             'ISSN':['1234-5678'],'PMID':'12345678'}
    chapter={'type':'chapter','title':'Methods chapter','author':[{'family':'Smith','given':'Alex'}],
             'editor':[{'family':'Jones','given':'Ruth'}],'container-title':'Collected Methods',
             'publisher':'Example Press','publisher-place':'Oxford','issued':{'date-parts':[[2020]]},
             'page':'10-20','ISBN':'9780000000000'}
    web={'type':'webpage','title':'Undated methods page','URL':'https://example.org/methods',
         'author':[{'literal':'Example Organisation'}]}
    return {'records':{key:{'id':key,'csl':value} for key,value in [('rarticle',article),('rchapter',chapter),('rweb',web)]},
            'citations':[{'items':[{'id':'rarticle'}]},{'items':[{'id':'rarticle'},{'id':'rchapter'}]}],
            'bibliography':{'currentOrder':['rchapter','rarticle','rweb']}}


class ExportTests(unittest.TestCase):
    def test_bibtex_independent_parser_and_escaping(self):
        output=export_references(registry(),'bibtex')
        entries=bibtexparser.loads(output).entries
        self.assertEqual(len(entries),3)
        article=next(e for e in entries if e['ID']=='rarticle')
        self.assertEqual(article['ENTRYTYPE'],'article')
        self.assertEqual(article['pages'],'245--259')
        self.assertIn('García',article['author']);self.assertIn('{Research',article['author'])
        self.assertIn(r'\&',article['title']);self.assertIn(r'\%',article['title'])
        self.assertIn(r'\{DNA\}',article['title'])
        self.assertNotIn('<i>',article['title'])
        self.assertEqual(entries[0]['ID'],'rchapter')
        self.assertEqual(entries[0]['booktitle'],'Collected Methods')
        self.assertEqual(entries[0]['editor'],'Jones, Ruth')

    def test_ris_independent_roundtrip(self):
        entries=rispy.loads(export_references(registry(),'ris'))
        self.assertEqual(len(entries),3)
        article=next(e for e in entries if e['id']=='rarticle')
        self.assertEqual(article['type_of_reference'],'JOUR')
        self.assertEqual(article['authors'],['García, María','Research & Development Consortium,'])
        self.assertEqual(article['doi'],'10.1234/test_a')
        self.assertEqual(article['start_page'],'245');self.assertEqual(article['end_page'],'259')
        self.assertEqual(article['accession_number'],'12345678')
        self.assertIn('Research & Development',article['authors'][1])

    def test_endnote_tagged_fields_and_boundaries(self):
        output=export_references(registry(),'endnote')
        records=[r.splitlines() for r in output.strip().split('\n\n')]
        self.assertEqual(len(records),3)
        article=next(r for r in records if '%F rarticle'in r)
        for line in ['%0 Journal Article','%A García, María','%A Research & Development Consortium,',
                     '%R 10.1234/test_a','%M 12345678','%J Synthetic Journal','%P 245-259']:
            self.assertIn(line,article)
        chapter=records[0]
        self.assertIn('%0 Book Section',chapter);self.assertIn('%E Jones, Ruth',chapter)
        self.assertIn('%B Collected Methods',chapter)
        web=records[-1]
        self.assertIn('%0 Web Page',web);self.assertFalse(any(x.startswith('%D')for x in web))

    def test_cited_only_deduplicates_repeated_citations(self):
        for format_name in ('bibtex','ris','endnote'):
            output=export_references(registry(),format_name,cited_only=True)
            self.assertNotIn('Undated methods page',output)
            self.assertEqual(output.count('Methods chapter'),1)

    def test_multiline_values_cannot_inject_new_records(self):
        reg=registry();reg['records']['rarticle']['csl']['title']='Title\n%0 Book\nTY  - BOOK'
        output=export_references(reg,'endnote')
        self.assertEqual(sum(x.startswith('%0 ')for x in output.splitlines()),3)
        self.assertEqual(len(rispy.loads(export_references(reg,'ris'))),3)
        self.assertEqual(len(bibtexparser.loads(export_references(reg,'bibtex')).entries),3)

    def test_missing_metadata_does_not_become_an_invented_date_or_author(self):
        reg=registry();reg['records']={'rweb':reg['records']['rweb']};reg['citations']=[]
        bib=export_references(reg,'bibtex');self.assertNotIn('year =',bib)
        for fmt in ('bibtex','ris','endnote'):
            self.assertEqual(export_references({'records':{},'citations':[]},fmt),'')
        reg['records']['rweb']['csl']['title']=''
        with self.assertRaisesRegex(ValueError,'no title'):export_references(reg,'ris')

    def test_export_does_not_mutate_reference_metadata(self):
        reg=registry();before=copy.deepcopy(reg)
        for fmt in ('bibtex','ris','endnote'):export_references(reg,fmt)
        self.assertEqual(reg,before)

    def test_cli_exports_local_register_without_google_login(self):
        with tempfile.TemporaryDirectory()as root:
            source=Path(root)/'register.json';source.write_text(json.dumps(registry()))
            for fmt,suffix in [('bibtex','bib'),('ris','ris'),('endnote','enw')]:
                target=Path(root)/('references.'+suffix)
                with patch('sys.argv',['citegoblin','export',str(source),'--format',fmt,'--output',str(target)]),\
                        patch('citegoblin.google.Google',side_effect=AssertionError('Local export must not log in')):
                    main()
                self.assertTrue(target.stat().st_size>0)
            capture=io.StringIO()
            with patch('sys.argv',['citegoblin','export',str(source),'--format','ris','--output','-','--cited-only']),contextlib.redirect_stdout(capture):main()
            self.assertEqual(len(rispy.loads(capture.getvalue())),2)

    def test_unknown_formats_and_broken_source_mappings_fail(self):
        with self.assertRaises(ValueError):export_references(registry(),'unknown')
        reg=registry();del reg['records']['rarticle']
        with self.assertRaisesRegex(ValueError,'missing reference'):export_references(reg,'bibtex')


if __name__=='__main__':unittest.main()
