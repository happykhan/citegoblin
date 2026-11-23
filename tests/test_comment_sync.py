import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from citegoblin.comment_sync import ERROR_PREFIX, sync_feedback, upsert_error
from citegoblin.commands import fingerprint
from citegoblin.document import Document, encode
from citegoblin.live import apply_with_feedback, run_once
from citegoblin.runner import commands_plan
from test_manager import comment, fixture, source


class FakeGoogle:
    def __init__(self, comments=None):
        self.rows = {c['id']: copy.deepcopy(dict(c, author=c.get('author', {'me': True})))
                     for c in (comments if comments is not None else [comment()])}
        self.threads = {key: [] for key in self.rows}
        self.calls = []
        self.resource = fixture()
        self.deny_resolve = False
        self.uncertain_reply = False

    def comments(self, doc):
        return copy.deepcopy([c for c in self.rows.values() if not c.get('deleted')])

    def document(self, doc):
        return copy.deepcopy(self.resource)

    def comment(self, doc, key):
        return copy.deepcopy(self.rows[key])

    def replies(self, doc, key):
        return copy.deepcopy(self.threads[key])

    def create_reply(self, doc, key, content):
        reply = {'id': str(len(self.threads[key])+1), 'content': content, 'author': {'me': True}}
        self.threads[key].append(reply); self.calls.append(('create', key))
        if self.uncertain_reply:
            self.uncertain_reply = False
            raise OSError('Connection lost after server accepted reply')
        return reply

    def update_reply(self, doc, key, reply_id, content):
        self.calls.append(('update', key))
        reply = next(r for r in self.threads[key] if r['id'] == reply_id)
        reply['content'] = content
        return reply

    def resolve_comment(self, doc, key):
        self.calls.append(('resolve-comment', key))
        if self.deny_resolve:
            raise ValueError('Permission denied')
        self.rows[key]['resolved'] = True


def failure(message='Invalid DOI'):
    return {'processed': [], 'errors': [{'commentId': 'comment-1', 'error': message}]}


def success():
    return {'processed': [{'commentId': 'comment-1'}], 'errors': []}


class CommentLifecycleTests(unittest.TestCase):
    def test_failed_reruns_reuse_one_reply(self):
        client = FakeGoogle(); snapshots = client.comments('doc')
        for message in ['Invalid DOI', 'Invalid DOI', 'No unique selection']:
            sync_feedback(client, 'doc', snapshots, failure(message), verified=False)
        self.assertEqual(len(client.threads['comment-1']), 1)
        self.assertEqual(client.threads['comment-1'][0]['content'], ERROR_PREFIX+'No unique selection')
        self.assertEqual(client.calls, [('create', 'comment-1'), ('update', 'comment-1')])
        self.assertFalse(client.rows['comment-1'].get('deleted'))

    def test_resolve_only_after_verification(self):
        client = FakeGoogle(); snapshots = client.comments('doc')
        sync_feedback(client, 'doc', snapshots, success(), verified=False)
        self.assertEqual(client.calls, [])
        sync_feedback(client, 'doc', snapshots, success(), verified=True)
        self.assertTrue(client.rows['comment-1']['resolved'])

    def test_success_after_error_resolves_comment(self):
        client = FakeGoogle(); snapshots = client.comments('doc')
        sync_feedback(client, 'doc', snapshots, failure(), verified=False)
        sync_feedback(client, 'doc', snapshots, success(), verified=True)
        self.assertTrue(client.rows['comment-1']['resolved'])

    def test_user_edited_command_is_left_alone(self):
        client = FakeGoogle(); snapshots = client.comments('doc')
        client.rows['comment-1']['content'] = '@cite 10.1234/different'
        result = sync_feedback(client, 'doc', snapshots, success(), verified=True)
        self.assertEqual(result['skipped'], ['comment-1']); self.assertEqual(client.calls, [])

    def test_human_and_other_accounts_replies_untouched(self):
        client = FakeGoogle()
        human = {'id': 'human', 'content': 'Keep my note', 'author': {'me': True}}
        other = {'id': 'other', 'content': ERROR_PREFIX+'Another account', 'author': {'me': False}}
        client.threads['comment-1'] = [human.copy(), other.copy()]
        upsert_error(client, 'doc', 'comment-1', 'Lookup failed')
        upsert_error(client, 'doc', 'comment-1', 'Different error')
        self.assertEqual(client.threads['comment-1'][:2], [human, other])
        self.assertEqual(len(client.threads['comment-1']), 3)

    def test_uncertain_create_is_discovered_on_next_run(self):
        client = FakeGoogle(); client.uncertain_reply = True
        result = sync_feedback(client, 'doc', client.comments('doc'), failure(), verified=False)
        self.assertEqual(len(result['errors']), 1)
        sync_feedback(client, 'doc', client.comments('doc'), failure('Now a different error'), verified=False)
        self.assertEqual(len(client.threads['comment-1']), 1)
        self.assertEqual(client.calls, [('create', 'comment-1'), ('update', 'comment-1')])

    def test_cleanup_retry_does_not_reinsert_citation(self):
        client = FakeGoogle(); client.deny_resolve = True
        snapshots = client.comments('doc')
        sync_feedback(client, 'doc', snapshots, success(), verified=True)
        self.assertEqual(len(client.threads['comment-1']), 1)
        # Represent a prior verified document write in its embedded command ledger.
        tab = client.resource['tabs'][0]['documentTab']
        for key in list(tab['namedRanges']):
            if key.startswith('CGPS_DOC_'): del tab['namedRanges'][key]
        config = {'schema':'cgps-citations/1','style':'elsevier-harvard','locale':'en-GB',
                  'processedCommands':{'comment-1':fingerprint(comment())}}
        for i, req in enumerate(encode('CGPS_DOC_', config, {'startIndex':0,'endIndex':1,'tabId':'t.test'})):
            mark = req['createNamedRange']
            tab['namedRanges'][mark['name']] = {'namedRanges':[{'namedRangeId':'config-'+str(i),'ranges':[mark['range']]}]}
        client.deny_resolve = False
        with tempfile.TemporaryDirectory() as root:
            result = run_once(client, 'synthetic-document', 't.test', root,
                              lookup=lambda _:self.fail('Should never reinsert or look up'))
        self.assertIsNone(result['verification'])
        self.assertEqual(result['feedback']['resolved'], ['comment-1'])

    def test_apply_failure_replies_without_resolving(self):
        client = FakeGoogle()
        plan, report = commands_plan(Document(fixture(),'t.test'), [comment()], lookup=lambda _:source())
        with patch('citegoblin.live.apply', side_effect=ValueError('Revision changed')):
            result = apply_with_feedback(client, {'plan':plan,'report':report}, 'not-written.json')
        self.assertIsNone(result['verification'])
        self.assertNotIn(('resolve-comment','comment-1'),client.calls)
        self.assertIn('Revision changed', client.threads['comment-1'][0]['content'])

    def test_apply_verifies_before_resolving(self):
        client = FakeGoogle()
        plan, report = commands_plan(Document(fixture(),'t.test'), [comment()], lookup=lambda _:source())
        def verified(*args):
            self.assertEqual(client.calls, [])
            return {'verified':True}
        with patch('citegoblin.live.apply', side_effect=verified):
            result = apply_with_feedback(client, plan, 'not-written.json')
        self.assertTrue(result['verification']['verified'])
        self.assertTrue(client.rows['comment-1']['resolved'])

    def test_dry_run_does_not_touch_comments(self):
        client = FakeGoogle([comment('@cite invalid')])
        with tempfile.TemporaryDirectory() as root:
            result = run_once(client,'synthetic-document','t.test',root,dry_run=True)
        self.assertTrue(result['dryRun']);self.assertEqual(client.calls, [])

    def test_another_authors_command_is_resolved_and_preserved(self):
        client = FakeGoogle([dict(comment(),author={'me':False})]); snapshots=client.comments('doc')
        sync_feedback(client,'doc',snapshots,success(),verified=True)
        sync_feedback(client,'doc',snapshots,success(),verified=True)
        self.assertEqual(client.calls,[('resolve-comment','comment-1')])
        self.assertTrue(client.rows['comment-1']['resolved'])
        self.assertFalse(client.rows['comment-1'].get('deleted',False))
        self.assertEqual(client.threads['comment-1'],[])

    def test_planner_failure_replies_instead_of_escaping(self):
        def broken_formatter(reg):raise ValueError('Formatting failed')
        plan, report=commands_plan(Document(fixture(),'t.test'),[comment()],lookup=lambda _:source(),formatter=broken_formatter)
        self.assertIsNone(plan);self.assertEqual(report['processed'],[])
        self.assertEqual(report['errors'][0]['error'],'Formatting failed')


if __name__=='__main__':unittest.main()
