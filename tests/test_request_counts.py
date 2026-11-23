import copy
import tempfile
import unittest
from unittest.mock import patch
from citegoblin.comment_sync import ERROR_PREFIX,sync_feedback
from citegoblin.errors import with_help
from citegoblin.live import run_once
from test_comment_sync import FakeGoogle
from test_manager import comment


class CountedGoogle(FakeGoogle):
    def __init__(self,comments):
        super().__init__(comments);self.reads={'comments':0,'document':0,'comment':0,'replies':0}
    def comments(self,key):
        self.reads['comments']+=1
        result=super().comments(key)
        for c in result:
            c['replies']=copy.deepcopy(self.threads[c['id']]);c['_repliesComplete']=True
        return result
    def document(self,key):
        self.reads['document']+=1;return super().document(key)
    def comment(self,*args):
        self.reads['comment']+=1;return super().comment(*args)
    def replies(self,*args):
        self.reads['replies']+=1;return super().replies(*args)


class RequestCountTests(unittest.TestCase):
    def test_idle_poll_only_lists_comments(self):
        client=CountedGoogle([dict(comment(),resolved=True),comment('Ordinary discussion',key='human')])
        with tempfile.TemporaryDirectory()as root:result=run_once(client,'doc','t.test',root)
        self.assertTrue(result['idle'])
        self.assertEqual(client.reads,{'comments':1,'document':0,'comment':0,'replies':0})
        self.assertEqual(client.calls,[])

    def test_unchanged_invalid_command_is_one_read_no_writes(self):
        client=CountedGoogle([comment('@style missing-style')])
        client.threads['comment-1']=[{'id':'error','author':{'me':True},'content':ERROR_PREFIX+with_help("Style 'missing-style' is not installed. Run: citegoblin styles install missing-style")}]
        with tempfile.TemporaryDirectory()as root:result=run_once(client,'doc','t.test',root)
        self.assertEqual(client.reads,{'comments':1,'document':0,'comment':0,'replies':0})
        self.assertEqual(client.calls,[])
        self.assertEqual(result['feedback']['errorReplies'][0]['replyId'],'error')

    def test_new_parse_error_uses_two_lists_no_document_or_reply_read(self):
        client=CountedGoogle([comment('@style missing-style')])
        with tempfile.TemporaryDirectory()as root:result=run_once(client,'doc','t.test',root)
        self.assertEqual(client.reads,{'comments':2,'document':0,'comment':0,'replies':0})
        self.assertEqual(client.calls,[('create','comment-1')])

    def test_many_successes_share_one_freshness_read(self):
        client=CountedGoogle([comment(key='a'),comment(key='b'),comment(key='c')])
        snapshots=client.comments('doc');client.reads['comments']=0
        result=sync_feedback(client,'doc',snapshots,{'processed':[{'commentId':k}for k in 'abc'],'errors':[]},verified=True)
        self.assertEqual(result['resolved'],list('abc'))
        self.assertEqual(client.reads,{'comments':1,'document':0,'comment':0,'replies':0})

    def test_changed_error_updates_existing_reply_with_no_reply_list(self):
        client=CountedGoogle([comment('@style missing-style')]);client.threads['comment-1']=[{'id':'error','author':{'me':True},'content':ERROR_PREFIX+'Old error'}]
        with tempfile.TemporaryDirectory()as root:run_once(client,'doc','t.test',root)
        self.assertEqual(client.calls,[('update','comment-1')]);self.assertEqual(client.reads['replies'],0)

    def test_concurrent_command_edit_is_still_protected(self):
        client=CountedGoogle([comment()]);snapshots=client.comments('doc')
        client.rows['comment-1']['content']='@cite 10.1234/other'
        result=sync_feedback(client,'doc',snapshots,{'processed':[{'commentId':'comment-1'}],'errors':[]},verified=True)
        self.assertEqual(result['skipped'],['comment-1']);self.assertEqual(client.calls,[])


if __name__=='__main__':unittest.main()
