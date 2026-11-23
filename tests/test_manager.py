import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from citegoblin.commands import parse, fingerprint, anchor_quote
from citegoblin.document import Document, encode, decode, units
from citegoblin.formatting import format_registry
from citegoblin.google import apply
from citegoblin.planning import add_citation, build_plan, verify
from citegoblin.references import normal_doi, record
from citegoblin.runner import commands_plan


def fixture(text='A finding 😀 [42].\nExisting references\n'):
    resource={'documentId':'synthetic-document','revisionId':'revision-1','tabs':[
        {'tabProperties':{'tabId':'t.test'},'documentTab':{'body':{'content':[]},'namedRanges':{}}}]}
    tab=resource['tabs'][0]['documentTab']; pos=1
    for line in text.splitlines(keepends=True):
        end=pos+units(line)
        tab['body']['content'].append({'startIndex':pos,'endIndex':end,'paragraph':{'elements':[
            {'startIndex':pos,'endIndex':end,'textRun':{'content':line,'textStyle':{'fontSize':{'magnitude':11,'unit':'PT'}}}}]}})
        pos=end
    start=1+units(text[:text.index('Existing references')]);ran={'startIndex':start,'endIndex':start+units('Existing references'),'tabId':'t.test'}
    markers=encode('CGPS_DOC_',{'schema':'cgps-citations/1','style':'elsevier-harvard','locale':'en-GB','numbering':'author-year'}, {'startIndex':0,'endIndex':1,'tabId':'t.test'})+encode('CGPS_BIB_',{'currentOrder':[]},ran)
    for index, req in enumerate(markers):
        mark=req['createNamedRange'];tab['namedRanges'][mark['name']]={'namedRanges':[{'namedRangeId':str(index),'ranges':[mark['range']]}]}
    return resource


def source(name='Smith',year=2022,doi='10.1234/example'):
    return {'type':'article-journal','title':'Synthetic article','DOI':doi,'author':[{'family':name,'given':'Alex'}],
            'issued':{'date-parts':[[year]]},'container-title':'Test Journal','volume':'1','page':'1–4'}


def comment(content='@cite 10.1234/example',quote='A finding 😀 [42].',key='comment-1'):
    return {'id':key,'content':content,'anchor':'synthetic-anchor','quotedFileContent':{'value':quote,'mimeType':'text/plain'}}


class ManagerTests(unittest.TestCase):
    def test_utf16_marker_roundtrip_and_capacity(self):
        payload={'name':'😀é'*500};prefix='CGPS_DOC_'
        requests=encode(prefix,payload,{'startIndex':0,'endIndex':1})
        names=[r['createNamedRange']['name'] for r in requests]
        self.assertTrue(all(units(n)<=255 for n in names))
        self.assertEqual(decode(names,prefix),payload)
        with self.assertRaises(ValueError):decode(names[1:],prefix)
        with self.assertRaises(ValueError):decode(names+[names[0]],prefix)

    def test_exact_location_utf16_and_ambiguity(self):
        doc=Document(fixture(),'t.test');ran=doc.locate('😀 [42]')
        self.assertEqual(doc.text(ran)[0],'😀 [42]')
        with self.assertRaises(ValueError):doc.locate('')
        with self.assertRaises(ValueError):Document(fixture('Repeat. Repeat.\nExisting references\n'),'t.test').locate('Repeat.')

    def test_command_language(self):
        self.assertEqual(parse(comment('@style author-year'))['style'],'elsevier-harvard')
        self.assertEqual(parse(comment('@style vancouver'))['style'],'nlm-citation-sequence')
        self.assertEqual(parse(comment('@refresh'))['kind'],'refresh')
        self.assertIsNone(parse(comment('Please rewrite the whole document')))
        with self.assertRaises(ValueError):parse(comment('@style invent-a-style'))
        with self.assertRaises(ValueError):parse(comment('@cite 10.1234/example and rewrite everything'))
        self.assertEqual(normal_doi('https://doi.org/10.1234/EXAMPLE'),'10.1234/example')

    def test_quote_is_not_an_instruction(self):
        self.assertEqual(anchor_quote({'quotedFileContent':{'value':'<b>Selected &amp; quoted</b>','mimeType':'text/html'}}),'Selected & quoted')
        with self.assertRaises(ValueError):anchor_quote(comment(quote=''))

    def test_idempotence_and_failed_anchor_leaves_no_record(self):
        doc=Document(fixture(),'t.test')
        plan,report=commands_plan(doc,[comment()],lookup=lambda _:source())
        self.assertEqual(len(plan['newCitationIds']),1)
        self.assertEqual(report['errors'],[])
        self.assertIn('(Smith, 2022)',list(plan['expected']['citations'].values())[0])
        self.assertIn('[42]',doc.unchanged_text([])[0])
        saved=doc.registry();saved['processedCommands']={'comment-1':fingerprint(comment())}
        with patch.object(doc,'registry',return_value=saved):
            unchanged,report=commands_plan(doc,[comment()],lookup=lambda _:self.fail('lookup repeated'))
        self.assertIsNone(unchanged)
        plan,report=commands_plan(doc,[comment(quote='Not in the document'),comment('@style vancouver',key='style')],lookup=lambda _:self.fail('lookup before anchor'))
        self.assertEqual(len(report['errors']),1)
        self.assertEqual(plan['expected']['references'],[])

    def test_grouping_and_deduplication(self):
        doc=Document(fixture(),'t.test');reg=doc.registry();r=record(source());reg['records'][r['id']]=r
        one=add_citation(doc,reg,'A finding 😀 [42].',[{'id':r['id']}])
        two=add_citation(doc,reg,'A finding 😀 [42].',[{'id':r['id']}])
        self.assertEqual(one,two);self.assertEqual(len(reg['citations'][0]['items']),1)
        self.assertEqual(record(source(),reg['records'])['id'],r['id'])

    def test_real_csl_styles(self):
        doc=Document(fixture(),'t.test');reg=doc.registry();r=record(source());reg['records'][r['id']]=r
        add_citation(doc,reg,'A finding 😀 [42].',[{'id':r['id']}])
        author_year=format_registry(reg)
        self.assertEqual(author_year['citations'][0]['text'],'(Smith, 2022)')
        reg['style']='nlm-citation-sequence';numeric=format_registry(reg)
        self.assertNotEqual(numeric['citations'][0]['text'],author_year['citations'][0]['text'])
        self.assertEqual(numeric['order'],[r['id']])

    def test_plan_persistence_and_empty_verification(self):
        resource=fixture();doc=Document(resource,'t.test');plan=build_plan(doc,doc.registry())
        # Applying an empty register refresh replaces existing reference text with an empty bibliography.
        self.assertTrue(plan['batches'])
        self.assertEqual(plan['revisionId'],'revision-1')
        self.assertEqual(plan['expected']['tables'],0)
        self.assertIn('recordHashes',plan['expected'])
        # A no-change plan is directly verifiable against its starting document.
        fake=lambda reg:{'citations':[],'bibliography':'Existing references','order':[]}
        same=build_plan(doc,doc.registry(),formatter=fake)
        self.assertTrue(verify(doc,same)['verified'])
        altered=copy.deepcopy(resource)
        altered['tabs'][0]['documentTab']['body']['content'][0]['paragraph']['elements'][0]['textRun']['content']='B finding 😀 [42].\n'
        with self.assertRaisesRegex(ValueError,'outside authorised'):verify(Document(altered,'t.test'),same)

    def test_concurrent_and_uncertain_writes_refused(self):
        class Client:
            def document(self,key):return dict(fixture(),revisionId='revision-2')
            def batch(self,*args):raise AssertionError('Must not write')
        doc=Document(fixture(),'t.test');plan=build_plan(doc,doc.registry())
        with tempfile.TemporaryDirectory()as directory:
            journal=Path(directory)/'journal.json'
            with self.assertRaisesRegex(ValueError,'Document changed'):apply(Client(),plan,journal)
            self.assertFalse(journal.exists())
            from citegoblin.planning import digest
            journal.write_text(json.dumps({'planHash':digest(plan),'complete':False,'inflight':0}))
            with self.assertRaisesRegex(ValueError,'incomplete'):apply(Client(),plan,journal)

    def test_pending_suggestions_block_insertion(self):
        data=fixture();data['tabs'][0]['documentTab']['body']['content'][0]['paragraph']['elements'][0]['textRun']['suggestedInsertionIds']=['suggestion']
        plan,report=commands_plan(Document(data,'t.test'),[comment()],lookup=lambda _:source())
        self.assertIsNone(plan);self.assertIn('pending suggestion',report['errors'][0]['error'])


if __name__=='__main__':unittest.main()
