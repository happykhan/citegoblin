import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from citegoblin.binomials import build_binomial_plan,load_names,verify_binomials,apply_binomials
from citegoblin.document import Document,units
from test_manager import fixture

NAMES=['Escherichia coli','Staphylococcus aureus','Candida albicans']


def after_document(resource,plan):
    result=copy.deepcopy(resource)
    for paragraph in result['tabs'][0]['documentTab']['body']['content']:
        if 'paragraph'not in paragraph:continue
        run=paragraph['paragraph']['elements'][0];text=run['textRun']['content'];position=run['startIndex'];runs=[]
        for char in text:
            style=copy.deepcopy(run['textRun']['textStyle'])
            for change in plan['changes']:
                ran=change['range']
                if ran['startIndex']<=position<ran['endIndex']:
                    offset=position-ran['startIndex']
                    raw=change['after'].encode('utf-16-le')[offset*2:(offset+units(char))*2]
                    char=raw.decode('utf-16-le');style.update(italic=True,smallCaps=False)
            runs.append({'startIndex':position,'endIndex':position+units(char),'textRun':{'content':char,'textStyle':style}})
            position+=units(char)
        paragraph['paragraph']['elements']=runs
    return Document(result,'t.test')


class BinomialTests(unittest.TestCase):
    def test_case_and_italics_only_for_approved_names(self):
        data=fixture('😀 ESCHERICHIA COLI and Staphylococcus Aureus. Normal Title Case remains.\n[[bibliography]]\n')
        plan=build_binomial_plan(Document(data,'t.test'),NAMES)
        self.assertEqual([c['after']for c in plan['changes']],['Escherichia coli','Staphylococcus aureus'])
        self.assertEqual(plan['changes'][0]['range']['startIndex'],4)
        self.assertTrue(verify_binomials(after_document(data,plan),plan)['verified'])

    def test_normal_case_still_gets_italics_and_small_caps_cleared(self):
        data=fixture('Escherichia coli\n[[bibliography]]\n')
        data['tabs'][0]['documentTab']['body']['content'][0]['paragraph']['elements'][0]['textRun']['textStyle']['smallCaps']=True
        plan=build_binomial_plan(Document(data,'t.test'),NAMES)
        self.assertEqual(plan['changes'][0]['before'],plan['changes'][0]['after'])
        self.assertEqual(len(plan['batches'][0]),1)
        self.assertEqual(plan['batches'][0][0]['updateTextStyle']['textStyle'],{'italic':True,'smallCaps':False})

    def test_correctly_formatted_names_are_idempotent(self):
        data=fixture('Escherichia coli\n[[bibliography]]\n');plan=build_binomial_plan(Document(data,'t.test'),NAMES)
        again=build_binomial_plan(after_document(data,plan),NAMES)
        self.assertEqual(again['changes'],[]);self.assertEqual(again['batches'],[])

    def test_suggestions_links_and_generated_reference_text_are_skipped(self):
        for flag in ['suggestedInsertionIds','suggestedDeletionIds','link']:
            data=fixture('ESCHERICHIA COLI\n[[bibliography]]\n')
            tr=data['tabs'][0]['documentTab']['body']['content'][0]['paragraph']['elements'][0]['textRun']
            if flag=='link':tr['textStyle']['link']={'url':'https://example.org'}
            else:tr[flag]=['suggestion']
            plan=build_binomial_plan(Document(data,'t.test'),NAMES)
            self.assertEqual(plan['changes'],[],flag);self.assertEqual(len(plan['skipped']),1)
        data=fixture('Unchanged.\n[[bibliography]]\n')
        data['tabs'][0]['documentTab']['body']['content'][1]['paragraph']['elements'][0]['textRun']['content']='ESCHERICHIA COLI\n'
        plan=build_binomial_plan(Document(data,'t.test'),NAMES)
        self.assertEqual(plan['changes'],[]);self.assertIn('bibliography',plan['skipped'][0]['reason'])

    def test_abbreviations_require_prior_full_name_and_unique_context(self):
        text='E. COLI before context. ESCHERICHIA COLI. e. COLI after context.\n[[bibliography]]\n'
        plan=build_binomial_plan(Document(fixture(text),'t.test'),NAMES,abbreviations=True)
        self.assertEqual([c['after']for c in plan['changes']],['Escherichia coli','E. coli'])
        self.assertEqual(len(plan['skipped']),1)
        ambiguous=NAMES+['Entamoeba coli']
        plan=build_binomial_plan(Document(fixture('Escherichia coli. Entamoeba coli. E. coli.\n[[bibliography]]\n'),'t.test'),ambiguous,abbreviations=True)
        self.assertIn('unique',plan['skipped'][0]['reason'])

    def test_space_and_strain_designations_are_preserved(self):
        plan=build_binomial_plan(Document(fixture('escherichia\u00a0COLI ST131; Candida ALBICANS strain ABC.\n[[bibliography]]\n'),'t.test'),NAMES)
        self.assertEqual([c['after']for c in plan['changes']],['Escherichia\u00a0coli','Candida albicans'])
        self.assertFalse(any('ST131'in c['before']for c in plan['changes']))

    def test_catalogue_and_custom_names_do_not_need_a_network(self):
        self.assertIn('Escherichia coli',load_names())
        with tempfile.TemporaryDirectory()as root:
            path=Path(root)/'names.txt';path.write_text('# approved\nBacillus subtilis\n')
            self.assertIn('Bacillus subtilis',load_names(path))
            path.write_text('Not a binomial')
            with self.assertRaises(ValueError):load_names(path)

    def test_case_changes_are_individual_letters_in_descending_order(self):
        plan=build_binomial_plan(Document(fixture('ESCHERICHIA COLI\n[[bibliography]]\n'),'t.test'),NAMES)
        deletes=[r['deleteContentRange']['range']for batch in plan['batches']for r in batch if 'deleteContentRange'in r]
        self.assertTrue(all(r['endIndex']-r['startIndex']==1 for r in deletes))
        self.assertEqual([r['startIndex']for r in deletes],sorted((r['startIndex']for r in deletes),reverse=True))

    def test_readback_detects_other_text_changes_or_missing_italics(self):
        data=fixture('ESCHERICHIA COLI. Other text.\n[[bibliography]]\n');plan=build_binomial_plan(Document(data,'t.test'),NAMES)
        after=after_document(data,plan)
        after.runs[-2]['textRun']['content']='X'
        with self.assertRaises(ValueError):verify_binomials(after,plan)
        after=after_document(data,plan);after.runs[0]['textRun']['textStyle']['italic']=False
        with self.assertRaises(ValueError):verify_binomials(after,plan)

    def test_table_cell_names_are_included(self):
        paragraph={'startIndex':4,'endIndex':21,'paragraph':{'elements':[{'startIndex':4,'endIndex':21,'textRun':{'content':'ESCHERICHIA COLI\n','textStyle':{}}}]}}
        data={'documentId':'table-test','revisionId':'revision','tabs':[{'tabProperties':{'tabId':'t.test'},'documentTab':{'body':{'content':[{'startIndex':1,'endIndex':24,'table':{'tableRows':[{'tableCells':[{'content':[paragraph]}]}]}}]}}}]}
        plan=build_binomial_plan(Document(data,'t.test'),NAMES)
        self.assertEqual(plan['tables'],1);self.assertEqual(plan['changes'][0]['after'],'Escherichia coli')

    def test_pending_style_suggestions_are_preserved(self):
        data=fixture('ESCHERICHIA COLI\n[[bibliography]]\n')
        data['tabs'][0]['documentTab']['body']['content'][0]['paragraph']['elements'][0]['textRun']['suggestedTextStyleChanges']={'suggestion':{'textStyle':{'italic':False}}}
        plan=build_binomial_plan(Document(data,'t.test'),NAMES)
        self.assertEqual(plan['changes'],[])
        self.assertEqual(plan['skipped'][0]['reason'],'pending suggestion')

    def test_stale_document_is_not_modified(self):
        data=fixture('ESCHERICHIA COLI\n[[bibliography]]\n');plan=build_binomial_plan(Document(data,'t.test'),NAMES)
        class Client:
            def document(self,key):return dict(data,revisionId='changed')
            def batch(self,*args):raise AssertionError('Must not write a stale plan')
        with tempfile.TemporaryDirectory()as root:
            with self.assertRaisesRegex(ValueError,'Document changed'):apply_binomials(Client(),plan,Path(root)/'journal.json')


if __name__=='__main__':unittest.main()
