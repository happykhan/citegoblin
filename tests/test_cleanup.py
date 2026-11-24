import copy
import io
import contextlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from citegoblin.cleanup import build_cleanup_plan,verify_cleanup,apply_cleanup,body_signature
from citegoblin.document import Document,encode,units
from citegoblin.references import record
from citegoblin.formatting import format_registry
from citegoblin.planning import digest
from citegoblin.richtext import styling_matches
from test_manager import source

NAMES=['Felis catus']


def reference_document(bib='Author. FELIS CATUS.',*,cleaned=False,citation=False):
    body='😀 FELIS CATUS in the body'+(' [1]'if citation else '')+'.\nReferences\n'
    text=body+bib+'\nFELIS CATUS after References.\n';position=1;elements=[]
    start=1+units(body);ran={'startIndex':start,'endIndex':start+units(bib),'tabId':'t.test'}
    for line in text.splitlines(keepends=True):
        runs=[];pstart=position
        for char in line:
            style={'fontSize':{'magnitude':11,'unit':'PT'}}
            if cleaned and start<=position<ran['endIndex']:
                at=bib.find('Felis catus')
                if at>=0 and start+units(bib[:at])<=position<start+units(bib[:at])+units('Felis catus'):style['italic']=True
            runs.append({'startIndex':position,'endIndex':position+units(char),'textRun':{'content':char,'textStyle':style}});position+=units(char)
        elements.append({'startIndex':pstart,'endIndex':position,'paragraph':{'elements':runs}})
    config={'schema':'cgps-citations/1','style':'elsevier-harvard','locale':'en-GB','numbering':'author-year','processedCommands':{}}
    if cleaned:config['referenceCleanup']={'enabled':True,'names':NAMES,'abbreviations':False}
    csl=source();csl['title']='Domestic cats (FELIS CATUS) distinguish names';ref=record(csl,{})
    if cleaned:
        from citegoblin.metadata_cleanup import clean_metadata
        clean_metadata({'records':{ref['id']:ref}},NAMES,normalise=False)
    anchor={'startIndex':0,'endIndex':1,'tabId':'t.test'}
    markers=encode('CGPS_DOC_',config,anchor)+encode('CGPS_REF_'+ref['id']+'_',ref,anchor)+encode('CGPS_BIB_',{'currentOrder':[ref['id']], 'renderedTextHash':digest(bib)},ran)
    if citation:
        offset=1+units(body[:body.index('[1]')]);markers+=encode('CGPS_CITE_cABC123_',{'items':[{'id':ref['id']}]},{'startIndex':offset,'endIndex':offset+3,'tabId':'t.test'})
    named={}
    for i,request in enumerate(markers):
        mark=request['createNamedRange'];named[mark['name']]={'namedRanges':[{'namedRangeId':str(i),'ranges':[mark['range']]}]}
    return Document({'documentId':'synthetic-document','revisionId':'revision-1','tabs':[{'tabProperties':{'tabId':'t.test'},'documentTab':{'body':{'content':elements},'namedRanges':named}}]},'t.test')


class CleanupTests(unittest.TestCase):
    def test_names_check_targets_references_and_preserves_body(self):
        doc=reference_document();plan=build_cleanup_plan(doc,NAMES,check='names')
        self.assertIn('Felis catus',plan['expected']['bibliography'])
        self.assertEqual(len(plan['changes']),1);self.assertTrue(plan['bibliographyOnly'])
        bib=doc.registry()['bibliography']['range']
        for batch in plan['batches']:
            for request in batch:
                if 'deleteContentRange'in request:self.assertEqual(request['deleteContentRange']['range'],bib)
                if 'updateTextStyle'in request:self.assertGreaterEqual(request['updateTextStyle']['range']['startIndex'],bib['startIndex'])
        self.assertIn('FELIS CATUS in the body',doc.runs[0]['textRun']['content']+''.join(r['textRun']['content']for r in doc.runs))

    def test_reference_cleanup_survives_a_later_refresh(self):
        doc=reference_document('Author. Felis catus.',cleaned=True);registry=doc.registry()
        preview=format_registry(registry)
        self.assertIn('Felis catus',preview['bibliography']);self.assertNotIn('FELIS CATUS',preview['bibliography'])
        offset=units(preview['bibliography'][:preview['bibliography'].index('Felis catus')])
        self.assertTrue(any(s['start']<=offset<s['end']and s['style'].get('italic')for s in preview['bibliographyStyles']))
        self.assertIn('FELIS CATUS',next(iter(registry['records'].values()))['csl']['title'])

    def test_readback_proves_body_and_reference_typography(self):
        before=reference_document();plan=build_cleanup_plan(before,NAMES,check='names')
        after=reference_document(plan['expected']['bibliography'],cleaned=True)
        self.assertTrue(verify_cleanup(after,plan)['verified'])
        after.runs[0]['textRun']['textStyle']['italic']=True
        with self.assertRaisesRegex(ValueError,'Body text or formatting'):verify_cleanup(after,plan)

    def test_missing_reference_italics_fail_readback(self):
        plan=build_cleanup_plan(reference_document(),NAMES,check='names')
        after=reference_document(plan['expected']['bibliography'],cleaned=True)
        for run in after.runs:run['textRun']['textStyle'].pop('italic',None)
        with self.assertRaises(ValueError):verify_cleanup(after,plan)

    def test_idempotent_names_check_has_no_requests(self):
        doc=reference_document('Author. Felis catus.',cleaned=True)
        doc=reference_document(format_registry(doc.registry())['bibliography'],cleaned=True)
        plan=build_cleanup_plan(doc,NAMES,check='names')
        self.assertEqual(plan['batches'],[]);self.assertEqual(plan['changes'],[])

    def test_no_existing_in_text_citation_is_reformatted(self):
        doc=reference_document(citation=True);plan=build_cleanup_plan(doc,NAMES)
        self.assertEqual(plan['operations'],[]);self.assertEqual(list(plan['expected']['citations'].values()),['[1]'])
        self.assertFalse(any('deleteNamedRange'in r and r['deleteNamedRange']['namedRangeId']in doc.ids('CGPS_CITE_cABC123_')for b in plan['batches']for r in b))

    def test_body_changes_after_references_are_detected(self):
        doc=reference_document();bib=doc.registry()['bibliography']['range'];before=body_signature(doc,bib)
        doc.runs[-2]['textRun']['content']='X'
        self.assertNotEqual(before,body_signature(doc,bib))

    def test_old_body_cleanup_plans_are_rejected_before_network_access(self):
        client=Mock()
        for schema in ('citegoblin-cleanup/1','citegoblin-binomials/1'):
            with self.assertRaisesRegex(ValueError,'References-only'):apply_cleanup(client,{'schema':schema},'unused.json')
        client.document.assert_not_called();client.batch.assert_not_called()

    def test_plan_cannot_mutate_body_even_if_its_batch_hash_is_recomputed(self):
        plan=build_cleanup_plan(reference_document(),NAMES,check='names');plan['batches'][0].insert(0,{'deleteContentRange':{'range':{'startIndex':1,'endIndex':2,'tabId':'t.test'}}})
        plan['batchHashes']=[digest(batch)for batch in plan['batches']];client=Mock()
        with self.assertRaisesRegex(ValueError,'outside References'):apply_cleanup(client,plan,'unused.json')
        client.document.assert_not_called()

    def test_pending_reference_style_suggestions_block_cleanup(self):
        doc=reference_document();bib=doc.registry()['bibliography']['range']
        run=next(r for r in doc.runs if r['startIndex']==bib['startIndex']);run['textRun']['suggestedTextStyleChanges']={'pending':{}}
        with self.assertRaisesRegex(ValueError,'pending suggestions'):build_cleanup_plan(doc,NAMES)

    def test_unregistered_documents_are_not_cleaned_by_guessing_a_heading(self):
        doc=reference_document();raw=copy.deepcopy(doc.raw);raw['tabs'][0]['documentTab']['namedRanges']={}
        with self.assertRaises(ValueError):build_cleanup_plan(Document(raw,'t.test'),NAMES)

    def test_stale_document_is_never_modified(self):
        plan=build_cleanup_plan(reference_document(),NAMES,check='names');client=Mock();client.document.return_value=dict(reference_document().raw,revisionId='different')
        with tempfile.TemporaryDirectory()as root:
            with self.assertRaisesRegex(ValueError,'Document changed'):apply_cleanup(client,plan,Path(root)/'journal.json')
        client.batch.assert_not_called()

    def test_removed_binomials_command_is_rejected(self):
        from citegoblin.cli import main
        with patch('sys.argv',['citegoblin','binomials','--help']),contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit)as error:main()
        self.assertEqual(error.exception.code,2)

    def test_generic_apply_rejects_old_cleanup_plans_before_writing(self):
        from citegoblin.google import apply
        client=Mock()
        with self.assertRaisesRegex(ValueError,'Unsupported edit plan'):apply(client,{'schema':'citegoblin-cleanup/1'},'unused.json')
        client.document.assert_not_called();client.batch.assert_not_called()
