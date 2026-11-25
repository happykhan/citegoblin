import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from citegoblin.bibliography import placement_plan,apply_placement,verify_placement
from citegoblin.commands import parse
from citegoblin.comment_sync import sync_feedback
from citegoblin.document import Document,encode,units
from citegoblin.planning import digest
from citegoblin.runner import commands_plan
from test_manager import fixture,comment


def plain_document(text):
    resource=fixture(text+'\nExisting references\n')
    resource['tabs'][0]['documentTab']['namedRanges']={}
    return Document(resource,'t.test')


def after_placement(plan):
    # Test readback against independently constructed text/markers, not an API mock replay.
    resource=fixture('Before.\nReferences\n\u200b\nAfter.\nExisting references\n')
    tab=resource['tabs'][0]['documentTab'];tab['namedRanges']={}
    markers=encode('CGPS_DOC_',plan['config'],{'startIndex':0,'endIndex':1,'tabId':'t.test'})+encode('CGPS_BIB_',{'currentOrder':[], 'renderedTextHash':digest(plan['bibliography'])},plan['range'])
    for i,request in enumerate(markers):
        mark=request['createNamedRange'];tab['namedRanges'][mark['name']]={'namedRanges':[{'namedRangeId':str(i),'ranges':[mark['range']]}]}
    return Document(resource,'t.test')


class BibliographyTests(unittest.TestCase):
    def test_both_commands_and_malformed_input(self):
        for command in ('@bib','@references'):
            self.assertEqual(parse(comment(command)),{'kind':'bibliography'})
        with self.assertRaises(ValueError):parse(comment('@bib here extra'))

    def test_new_location_preserves_heading_and_following_text(self):
        doc=plain_document('Before.\nReferences\nAfter.')
        plan=placement_plan(doc,comment('@bib','References'))
        insertion=next(r['insertText']for r in plan['requests'] if 'insertText'in r)
        self.assertEqual(insertion['text'],'\n\u200b')
        self.assertEqual(plan['range']['startIndex'],1+units('Before.\nReferences\n'))
        self.assertTrue(verify_placement(after_placement(plan),plan)['verified'])
        self.assertIsNone(placement_plan(after_placement(plan),comment('@bib','References')))

    def test_existing_bibliography_is_adopted_without_text_edits(self):
        doc=Document(fixture('Before.\nReferences\nExisting references\n'),'t.test')
        plan=placement_plan(doc,comment('@references','References'))
        self.assertFalse(any('insertText'in r or 'deleteContentRange'in r for r in plan['requests']))
        self.assertEqual(plan['range'],doc.registry()['bibliography']['range'])

    def test_move_keeps_old_bibliography_and_deletes_only_its_range(self):
        doc=Document(fixture('Old.\nExisting references\nNew references\nAfter.\n'),'t.test')
        plan=placement_plan(doc,comment('@bib','New references'))
        deleted=[r['deleteContentRange']['range']for r in plan['requests']if 'deleteContentRange'in r]
        self.assertEqual(deleted,[doc.registry()['bibliography']['range']])
        inserted=next(r['insertText']['text']for r in plan['requests']if 'insertText'in r)
        self.assertEqual(inserted,'\nExisting references')
        self.assertEqual(plan['bibliography'],'Existing references')

    def test_partial_ambiguous_or_suggested_heading_is_rejected(self):
        for text,quote in [('Long References heading','References'),('References\nReferences','References')]:
            with self.assertRaises(ValueError):placement_plan(plain_document(text),comment('@bib',quote))
        doc=plain_document('References')
        doc.runs[0]['textRun']['suggestedInsertionIds']=['pending']
        with self.assertRaises(ValueError):placement_plan(doc,comment('@bib','References'))

    def test_persistent_comment_is_never_resolved(self):
        client=Mock()
        result=sync_feedback(client,'doc',[dict(comment('@bib'),_repliesComplete=True,replies=[])],{'alreadyProcessed':[{'commentId':'comment-1','keepOpen':True}],'errors':[]},verified=True)
        self.assertEqual(result['resolved'],[]);client.comments.assert_not_called();client.resolve_comment.assert_not_called()

    def test_processed_bib_report_stays_open(self):
        plan=placement_plan(plain_document('Before.\nReferences\nAfter.'),comment('@bib','References'))
        changes,report=commands_plan(after_placement(plan),[comment('@bib','References')])
        self.assertIsNone(changes)
        self.assertTrue(report['alreadyProcessed'][0]['keepOpen'])

    def test_stale_plan_and_uncertain_retry_do_not_write(self):
        doc=plain_document('References');plan=placement_plan(doc,comment('@bib','References'))
        client=Mock();client.document.return_value=dict(doc.raw,revisionId='changed')
        with tempfile.TemporaryDirectory()as root:
            journal=Path(root)/'journal.json'
            with self.assertRaisesRegex(ValueError,'Document changed'):apply_placement(client,plan,journal)
            client.batch.assert_not_called()
            journal.write_text('{}')
            with self.assertRaisesRegex(ValueError,'already attempted'):apply_placement(client,plan,journal)
            client.batch.assert_not_called()

    def test_unrelated_text_change_fails_readback(self):
        plan=placement_plan(plain_document('Before.\nReferences\nAfter.'),comment('@bib','References'))
        doc=after_placement(plan);doc.runs[0]['textRun']['content']='ALTERED\n'
        with self.assertRaises(ValueError):verify_placement(doc,plan)

    def test_cached_standing_comment_needs_one_comments_read(self):
        import json
        from citegoblin.live import run_once
        from citegoblin.commands import fingerprint
        item=comment('@bib','References');client=Mock();client.comments.return_value=[item]
        with tempfile.TemporaryDirectory()as root:
            (Path(root)/'bibliography-anchor.json').write_text(json.dumps({'documentId':'doc','tabId':'t.test','commentId':item['id'],'fingerprint':fingerprint(item)}))
            self.assertTrue(run_once(client,'doc','t.test',root)['idle'])
        client.document.assert_not_called();client.comments.assert_called_once()

    def test_successful_persistent_comment_updates_old_error_without_resolving(self):
        from test_comment_sync import FakeGoogle
        from citegoblin.comment_sync import ERROR_PREFIX
        item=comment('@bib');client=FakeGoogle([item]);client.threads[item['id']]=[{'id':'reply','author':{'me':True},'content':ERROR_PREFIX+'Old error'}]
        result=sync_feedback(client,'doc',[item],{'alreadyProcessed':[{'commentId':item['id'],'keepOpen':True}],'errors':[]},verified=True)
        self.assertEqual(client.calls,[('update',item['id'])]);self.assertEqual(result['keptOpen'],[item['id']])

    def test_text_verification_uses_native_positions_across_structure_gaps(self):
        from citegoblin.planning import digest
        doc=plain_document('Before.\nReferences\nAfter.')
        raw=copy.deepcopy(doc.raw)
        for paragraph in raw['tabs'][0]['documentTab']['body']['content'][1:]:
            paragraph['startIndex']+=10;paragraph['endIndex']+=10
            for run in paragraph['paragraph']['elements']:
                run['startIndex']+=10;run['endIndex']+=10
        plan=placement_plan(Document(raw,'t.test'),comment('@bib','References'))
        self.assertEqual(plan['expectedTextHash'],digest('Before.\nReferences\n\u200b\nAfter.\nExisting references\n'))

    def test_empty_bibliography_refresh_keeps_a_nonempty_hidden_range(self):
        from citegoblin.planning import build_plan
        doc=Document(fixture(),'t.test');plan=build_plan(doc,doc.registry())
        self.assertEqual(plan['expected']['bibliography'],'\u200b')
        self.assertFalse(any(r.get('insertText',{}).get('text')==''for batch in plan['batches']for r in batch))
