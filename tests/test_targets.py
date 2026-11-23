import contextlib
import copy
import io
import tempfile
import unittest
from unittest.mock import Mock,patch
from citegoblin.targets import document_target,document_tab
from test_manager import fixture

KEY='example-document-id'
BASE='https://docs.google.com/document/d/'+KEY


class TargetTests(unittest.TestCase):
    def test_raw_id_and_common_google_docs_links(self):
        for source in (KEY,BASE,BASE+'/',BASE+'/edit',BASE+'/edit?usp=sharing',BASE+'/edit#heading=h.example',BASE+'/preview',BASE.replace('/document/','/document/u/0/')+'/edit'):
            self.assertEqual(document_target(source),(KEY,None))
        self.assertEqual(document_target(' '+BASE+'/edit?tab=t.123&usp=sharing#heading=h.x '),(KEY,'t.123'))

    def test_explicit_tab_overrides_url_tab(self):
        self.assertEqual(document_target(BASE+'/edit?tab=t.old','t.new'),(KEY,'t.new'))

    def test_rejects_wrong_sites_file_links_and_ambiguous_tabs(self):
        for source in ('https://example.com/document/d/'+KEY,BASE.replace('docs.google.com','docs.google.com.evil.test'),BASE.replace('https:','http:'),'https://drive.google.com/file/d/'+KEY+'/view','https://docs.google.com/document/create',BASE+'/edit?tab=t.a&tab=t.b','https://docs.google.com@evil.test/document/d/'+KEY,BASE+'/edit?tab=bad%20tab'):
            with self.subTest(source=source),self.assertRaises(ValueError):document_target(source)

    def test_single_tab_is_automatic_but_multiple_tabs_need_selection(self):
        raw=fixture();self.assertEqual(document_tab(raw).tab_id,'t.test')
        second=copy.deepcopy(raw['tabs'][0]);second['tabProperties']['tabId']='t.second';raw['tabs'].append(second)
        with self.assertRaisesRegex(ValueError,'multiple tabs'):document_tab(raw)
        self.assertEqual(document_tab(raw,'t.second').tab_id,'t.second')

    def test_nested_tabs_are_counted_and_can_be_selected(self):
        raw=fixture();child=copy.deepcopy(raw['tabs'][0]);child['tabProperties']['tabId']='t.child';raw['tabs'][0]['childTabs']=[child]
        with self.assertRaisesRegex(ValueError,'t.child'):document_tab(raw)
        self.assertEqual(document_tab(raw,'t.child').tab_id,'t.child')

    def test_run_passes_extracted_id_and_url_tab_to_runner(self):
        from citegoblin.cli import main
        client=Mock()
        with tempfile.TemporaryDirectory()as root,patch('sys.argv',['citegoblin','run',BASE+'/edit?tab=t.test&usp=sharing','--workdir',root]),patch('citegoblin.google.Google',return_value=client),patch('citegoblin.live.run_once',return_value={'idle':True})as run,contextlib.redirect_stdout(io.StringIO()):main()
        self.assertEqual(run.call_args.args[1:3],(KEY,'t.test'));client.document.assert_not_called()

    def test_run_finds_single_tab_for_a_plain_sharing_url(self):
        from citegoblin.cli import main
        client=Mock();client.document.return_value=fixture()
        with tempfile.TemporaryDirectory()as root,patch('sys.argv',['citegoblin','run',BASE+'/edit?usp=sharing','--workdir',root]),patch('citegoblin.google.Google',return_value=client),patch('citegoblin.live.run_once',return_value={'idle':True})as run,contextlib.redirect_stdout(io.StringIO()):main()
        client.document.assert_called_once_with(KEY);self.assertEqual(run.call_args.args[1:3],(KEY,'t.test'))

    def test_ambiguous_document_never_reaches_edit_runner(self):
        from citegoblin.cli import main
        raw=fixture();raw['tabs'].append(copy.deepcopy(raw['tabs'][0]));client=Mock();client.document.return_value=raw
        with tempfile.TemporaryDirectory()as root,patch('sys.argv',['citegoblin','run',BASE+'/edit','--workdir',root]),patch('citegoblin.google.Google',return_value=client),patch('citegoblin.live.run_once')as run,contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):main()
        run.assert_not_called();client.batch.assert_not_called()
