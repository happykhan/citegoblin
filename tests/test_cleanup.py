import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from citegoblin.cleanup import build_cleanup_plan,verify_cleanup,apply_cleanup,_case_preview
from citegoblin.document import Document
from test_manager import fixture
from test_binomials import after_document

NAMES=['Escherichia coli']

class CleanupTests(unittest.TestCase):
    def test_combined_plan_uses_cleaned_prose_for_citation_verification(self):
        document=Document(fixture('ESCHERICHIA COLI.\n[[bibliography]]\n'),'t.test')
        plan=build_cleanup_plan(document,NAMES)
        self.assertEqual(plan['checks'],['scientific-names','citations-and-bibliography'])
        preview=_case_preview(document,plan['changes'])
        self.assertIn('Escherichia coli',preview.runs[0]['textRun']['content'])
        self.assertIn('ESCHERICHIA COLI',document.runs[0]['textRun']['content'])
        from citegoblin.planning import digest
        excluded=[preview.registry()['bibliography']['range']]
        self.assertEqual(plan['citationPlan']['expected']['unchangedTextHash'],digest(preview.unchanged_text(excluded)))
        self.assertEqual(plan['batches'],plan['namesPlan']['batches']+plan['citationPlan']['batches'])

    def test_names_only_keeps_verification_and_idempotence(self):
        resource=fixture('ESCHERICHIA COLI.\n[[bibliography]]\n')
        plan=build_cleanup_plan(Document(resource,'t.test'),NAMES,check='names')
        updated=after_document(resource,plan['namesPlan'])
        self.assertTrue(verify_cleanup(updated,plan)['verified'])
        self.assertEqual(build_cleanup_plan(updated,NAMES,check='names')['batches'],[])
        broken=Document(resource,'t.test')
        with self.assertRaises(ValueError):verify_cleanup(broken,plan)

    def test_unregistered_document_still_cleans_names(self):
        resource=fixture('ESCHERICHIA COLI.\n[[bibliography]]\n')
        resource['tabs'][0]['documentTab']['namedRanges']={}
        document=Document(resource,'t.test')
        plan=build_cleanup_plan(document,NAMES)
        self.assertEqual(plan['checks'],['scientific-names'])
        with self.assertRaises(ValueError):build_cleanup_plan(document,NAMES,check='citations')

    def test_citations_only_skips_names(self):
        plan=build_cleanup_plan(Document(fixture(),'t.test'),NAMES,check='citations')
        self.assertEqual(plan['changes'],[])
        self.assertIsNone(plan['namesPlan'])
        self.assertEqual(plan['checks'],['citations-and-bibliography'])

    def test_name_positions_shift_after_bibliography_replacement(self):
        document=Document(fixture('Before.\n[[bibliography]]\nESCHERICHIA COLI.\n'),'t.test')
        plan=build_cleanup_plan(document,NAMES)
        delta=len(plan['citationPlan']['expected']['bibliography'])-len('[[bibliography]]')
        self.assertEqual(plan['finalNames'][0]['range']['startIndex'],plan['changes'][0]['range']['startIndex']+delta)

    def test_stale_and_tampered_plan_never_write(self):
        document=Document(fixture(),'t.test');plan=build_cleanup_plan(document,NAMES)
        client=unittest.mock.Mock();client.document.return_value=dict(document.raw,revisionId='different')
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError,'Document changed'):
                apply_cleanup(client,plan,Path(root)/'journal.json')
            client.batch.assert_not_called()
            plan['batchHashes']=['invalid']
            with self.assertRaisesRegex(ValueError,'hashes'):
                apply_cleanup(client,plan,Path(root)/'journal.json')
            client.batch.assert_not_called()
