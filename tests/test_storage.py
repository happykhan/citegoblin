import copy
import gzip
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from citegoblin.document import Document
from citegoblin.planning import digest
from citegoblin.storage import document_directory,cache_references,finish_run,preview
from citegoblin.live import run_once,write
from test_manager import fixture,comment
from test_comment_sync import FakeGoogle


class StorageTests(unittest.TestCase):
    def test_default_paths_separate_documents_and_tabs(self):
        with patch.dict(os.environ,{'CITEGOBLIN_HOME':'/tmp/citegoblin-test'}):
            first=document_directory('doc-a','t.a');self.assertEqual(str(first),'/tmp/citegoblin-test/documents/doc-a/tabs/t.a')
            self.assertNotEqual(first,document_directory('doc-b','t.a'))
            self.assertNotEqual(first,document_directory('doc-a','t.b'))
        for value in ('..','../other','/absolute','doc/slash'):
            with self.assertRaises(ValueError):document_directory(value,'t.a')

    def test_cache_excludes_prose_and_can_export(self):
        from citegoblin.exporting import export_references
        with tempfile.TemporaryDirectory()as root:
            path=Path(cache_references(Document(fixture('Private manuscript wording.\nExisting references\n'),'t.test'),root))
            data=json.loads(path.read_text());self.assertNotIn('Private manuscript wording',path.read_text())
            self.assertEqual(data['records'],{});self.assertEqual(export_references(data,'ris'),'')
            first=path.stat().st_mtime_ns;cache_references(Document(fixture('Other wording.\nExisting references\n'),'t.test'),root)
            self.assertEqual(path.stat().st_mtime_ns,first)
            if os.name=='posix':self.assertEqual(path.stat().st_mode&0o777,0o600)

    def test_success_archives_only_latest_run_and_clears_finished_files(self):
        with tempfile.TemporaryDirectory()as location:
            root=Path(location)
            for i in range(4):
                plan={'batches':[],'value':i};saved={'plan':plan};key=digest(saved)
                write(root/(key+'.plan.json'),saved);write(root/(key+'.result.json'),{'ok':True});write(root/(digest(plan)+'.journal.json'),{'complete':True})
                finish_run(root,key,saved,{'verification':{'verified':True}})
            files=list(root.iterdir());self.assertEqual([p.name for p in files],['last-run.json.gz'])
            archive=json.loads(gzip.decompress(files[0].read_bytes()));self.assertEqual(archive['saved']['plan']['value'],3)

    def test_uncertain_or_corrupt_journals_and_their_plans_are_preserved(self):
        with tempfile.TemporaryDirectory()as location:
            root=Path(location)
            for content in ('{"complete":false}','not valid JSON'):
                saved={'plan':{'batches':[]}};key=digest(saved);plan=root/(key+'.plan.json');journal=root/(digest(saved['plan'])+'.journal.json')
                write(plan,saved);journal.write_text(content)
                finish_run(root,key,saved,{'verification':None})
                self.assertTrue(plan.exists());self.assertEqual(journal.read_text(),content)

    def test_preview_is_bounded_compressed_and_private(self):
        with tempfile.TemporaryDirectory()as root:
            for i in range(10):path=Path(preview(root,{'index':i,'repeated':'x'*10000}))
            self.assertEqual(len(list(Path(root).iterdir())),1)
            self.assertLess(path.stat().st_size,200)
            self.assertEqual(json.loads(gzip.decompress(path.read_bytes()))['index'],9)
            if os.name=='posix':self.assertEqual(path.stat().st_mode&0o777,0o600)

    def test_run_uses_default_document_folder_without_workdir(self):
        client=FakeGoogle([])
        with tempfile.TemporaryDirectory()as root,patch.dict(os.environ,{'CITEGOBLIN_HOME':root}):
            self.assertTrue(run_once(client,'document-id','t.test')['idle'])
            self.assertTrue((Path(root)/'documents/document-id/tabs/t.test').is_dir())

    def test_repeated_failures_do_not_accumulate_plan_files(self):
        client=FakeGoogle([comment('@cite 10.1234/missing',quote='does not occur')])
        with tempfile.TemporaryDirectory()as root:
            for i in range(5):run_once(client,'document-id','t.test',root)
            self.assertFalse(list(Path(root).glob('*.plan.json')))
            self.assertFalse(list(Path(root).glob('*.result.json')))
            self.assertEqual(len(list(Path(root).glob('last-run.json.gz'))),1)
