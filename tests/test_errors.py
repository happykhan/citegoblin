import contextlib
import io
import tempfile
import unittest
from unittest.mock import patch
from citegoblin.errors import BASE,help_url,with_help,link_errors
from citegoblin.comment_sync import ERROR_PREFIX
from citegoblin.live import run_once
from test_manager import comment
from test_request_counts import CountedGoogle


class ErrorHelpTests(unittest.TestCase):
    def test_routes_common_errors_to_the_relevant_page(self):
        cases={
            'Google denied access to this file':'reference/troubleshooting/#google-returned-http-403',
            'OS keychain unavailable':'reference/troubleshooting/#no-supported-operating-system-keychain-is-available',
            'Google sign-in did not complete':'getting-started/google-login/',
            'Your account is not on the allowlist':'getting-started/beta-testing/',
            'Quote has 2 matches':'reference/troubleshooting/#quote-has-multiple-matches-or-the-comment-anchor-is-unavailable',
            'Style is not installed':'guides/styles/',
            'Invalid DOI identifier':'guides/citations/',
            'Document changed; regenerate the plan':'reference/troubleshooting/#document-changed-or-a-previous-run-is-incomplete',
            'Document has multiple tabs':'getting-started/first-document/#copy-the-document-url',
            'Invalid canonical binomial':'guides/cleanup/',
            'Run citegoblin setup-formatter first':'getting-started/install/',
            'Unexpected problem':'reference/troubleshooting/',
        }
        for message,path in cases.items():
            with self.subTest(message=message):self.assertEqual(help_url(message),BASE+path)

    def test_link_is_added_once_without_including_user_text_in_url(self):
        message='Invalid DOI: 10.1234/private-manuscript'
        linked=with_help(message);self.assertEqual(with_help(linked),linked)
        self.assertTrue(linked.startswith(message));self.assertNotIn('private-manuscript',linked.split('Help: ')[1])

    def test_only_error_fields_are_annotated_in_structured_output(self):
        raw={'title':'Invalid DOI','errors':[{'commentId':'c','error':'Invalid DOI'}],'cacheError':'OS keychain unavailable'}
        linked=link_errors(raw);self.assertEqual(linked['title'],raw['title'])
        self.assertIn('Help: ',linked['errors'][0]['error']);self.assertIn('Help: ',linked['cacheError'])
        self.assertNotIn('Help: ',raw['errors'][0]['error'])

    def test_existing_reply_is_updated_once_without_extra_replies(self):
        message="Style 'missing-style' is not installed. Run: citegoblin styles install missing-style"
        client=CountedGoogle([comment('@style missing-style')]);client.threads['comment-1']=[{'id':'error','author':{'me':True},'content':ERROR_PREFIX+message}]
        with tempfile.TemporaryDirectory()as root:
            run_once(client,'doc','t.test',root);self.assertEqual(client.calls,[('update','comment-1')])
            client.calls.clear();client.reads={k:0 for k in client.reads}
            run_once(client,'doc','t.test',root)
        self.assertEqual(client.calls,[]);self.assertEqual(client.reads['comments'],1)
        self.assertEqual(len(client.threads['comment-1']),1)
        self.assertEqual(client.threads['comment-1'][0]['content'].count('Help: '),1)

    def test_argument_errors_have_cli_help(self):
        from citegoblin.cli import main
        stream=io.StringIO()
        with patch('sys.argv',['citegoblin','not-a-command']),contextlib.redirect_stderr(stream):
            with self.assertRaises(SystemExit):main()
        self.assertIn(BASE+'reference/cli/',stream.getvalue())

    def test_terminal_exception_has_a_help_link(self):
        from citegoblin.cli import main
        stream=io.StringIO()
        with patch('sys.argv',['citegoblin','lookup','invalid']),patch('citegoblin.cli.resolve',side_effect=ValueError('Invalid DOI identifier')),contextlib.redirect_stderr(stream):
            with self.assertRaises(SystemExit):main()
        self.assertIn(BASE+'guides/citations/',stream.getvalue())
