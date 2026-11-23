"""One user-run or polling cycle, including idempotent comment feedback."""
import json
import re
from pathlib import Path
import subprocess
from .commands import fingerprint, parse
from .comment_sync import sync_feedback
from .document import Document
from .google import apply
from .planning import digest
from .runner import commands_plan
from .storage import document_directory,cache_references,preview,finish_run
from .auth import private_write


def write(path, value):
    path = Path(path)
    private_write(path,json.dumps(value,ensure_ascii=False,separators=(',',':')))


def apply_with_feedback(client, saved, journal):
    """Supports a bare edit plan or process-comments' {plan, report} output."""
    plan = saved.get('plan', saved)
    report = saved.get('report', plan.get('feedback', {}) if plan else {})
    document_id = plan['documentId'] if plan else saved.get('documentId')
    verification = None
    if plan:
        try:
            verification = apply(client, plan, journal)
        except (ValueError, OSError, RuntimeError) as failure:
            if not report:
                raise
            report = dict(report, errors=report['errors'] + [
                {'commentId': c['commentId'], 'error': 'Document update was not verified: ' + str(failure)}
                for c in report.get('processed', [])])
    if not report:
        return {'verification': verification}
    if not document_id:
        raise ValueError('Saved command report is missing documentId')
    feedback = sync_feedback(client, document_id, report['comments'], report,
                             verified=bool(verification and verification.get('verified')))
    return {'verification': verification, 'report': report, 'feedback': feedback}


def run_once(client, document_id, tab, workdir=None, *, reference_data=(), dry_run=False,
             allow_suggestions=False, lookup=None):
    root = Path(workdir).expanduser() if workdir else document_directory(document_id,tab)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    comments = client.comments(document_id)
    pending=[c for c in comments if not c.get('resolved') and not c.get('deleted')
             and c.get('content','').strip().startswith(('@cite','@style','@refresh','@bib','@references'))]
    if not pending:
        return {'dryRun':dry_run,'idle':True,'report':{'processed':[],'alreadyProcessed':[],'errors':[],'comments':[]}}
    anchor_cache=root/'bibliography-anchor.json'
    if len(pending)==1 and pending[0].get('content','').strip() in ('@bib','@references') and anchor_cache.exists():
        try:cached=json.loads(anchor_cache.read_text())
        except (ValueError,OSError):cached={}
        if cached=={'documentId':document_id,'tabId':tab,'commentId':pending[0]['id'],'fingerprint':fingerprint(pending[0])}:
            return {'dryRun':dry_run,'idle':True,'bibliographyCommentKeptOpen':pending[0]['id']}
    parse_errors=[]
    for comment in pending:
        try:parse(comment)
        except ValueError as failure:parse_errors.append({'commentId':comment['id'],'error':str(failure)})
    if len(parse_errors)==len(pending):
        report={'processed':[],'alreadyProcessed':[],'errors':parse_errors,'comments':pending}
        if dry_run:return {'dryRun':True,'report':report}
        feedback=sync_feedback(client,document_id,comments,report,verified=False)
        return {'verification':None,'report':report,'feedback':feedback}
    setup_key=None
    document=None
    try:
        document = Document(client.document(document_id), tab)
        bib_comments=[c for c in pending if c.get('content','').strip() in ('@bib','@references')]
        if len(bib_comments)>1:raise ValueError('Keep only one open @bib or @references location comment per document tab')
        if bib_comments:
            from .bibliography import placement_plan,apply_placement
            bib=bib_comments[0];export=None
            config=document.value('CGPS_DOC_') if 'CGPS_DOC_'in document.groups else {}
            unchanged=config.get('bibliographyCommentId')==bib['id'] and config.get('processedCommands',{}).get(bib['id'])==fingerprint(bib)
            if not unchanged and not bib.get('quotedFileContent'):export=client.export_docx(document_id)
            setup=placement_plan(document,bib,export=export)
            if setup:
                key=digest(setup);write(root/(key+'.bibliography-plan.json'),setup)
                if dry_run:
                    path=preview(root,{'bibliographySetup':setup});(root/(key+'.bibliography-plan.json')).unlink()
                    return {'dryRun':True,'bibliographySetup':setup,'previewFile':path,'nextStep':'Run without --dry-run to place the bibliography, then process citation and style comments.'}
                # Fresh comment read prevents placing a bibliography from an edited command.
                fresh=next((c for c in client.comments(document_id) if c['id']==bib['id']),None)
                if not fresh or fresh.get('resolved') or fresh.get('deleted') or fingerprint(fresh)!=fingerprint(bib):raise ValueError('Bibliography comment changed; run again')
                apply_placement(client,setup,root/(key+'.bibliography-journal.json'));setup_key=key
                document=Document(client.document(document_id),tab)
        cache_references(document,root)
        ledger = document.registry().get('processedCommands', {})
        needs_export = any(re.match(r'^@cite\s+', c.get('content', '').strip())
                           and not c.get('quotedFileContent') and not c.get('resolved') and not c.get('deleted')
                           and ledger.get(c['id']) != fingerprint(c) for c in comments)
        export = None
        if needs_export:
            try:
                export = client.export_docx(document_id)
            except (ValueError, OSError):
                # Other commands can still proceed. Missing anchors get individual errors.
                pass
        options = {'reference_data': reference_data, 'export': export, 'allow_suggestions': allow_suggestions}
        if lookup is not None:
            options['lookup'] = lookup
        plan, report = commands_plan(document, comments, **options)
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as failure:
        commands = [c for c in comments if not c.get('resolved') and not c.get('deleted')
                    and c.get('content', '').strip().startswith(('@cite', '@style', '@refresh', '@bib', '@references'))]
        report = {'processed': [], 'alreadyProcessed': [],
                  'errors': [{'commentId': c['id'], 'error': str(failure)} for c in commands],
                  'comments': commands}
        plan = None
    saved = {'documentId': document_id, 'plan': plan, 'report': report}
    key = digest(saved)
    write(root / (key + '.plan.json'), saved)
    if dry_run:
        path=preview(root,saved);(root/(key+'.plan.json')).unlink()
        return {'dryRun': True, 'report': report,'previewFile':path}
    if plan:
        result = apply_with_feedback(client, saved, root / (digest(plan) + '.journal.json'))
    else:
        # The embedded ledger is written after the text batches. Already-applied
        # commands need comment-cleanup retries only, never another insertion.
        feedback = sync_feedback(client, document_id, comments, report, verified=True)
        result = {'verification': None, 'report': report, 'feedback': feedback}
    locations=[c for c in pending if c.get('content','').strip() in ('@bib','@references')]
    failed={c['commentId'] for c in report.get('errors',[])+result.get('feedback',{}).get('errors',[])}
    if len(locations)==1 and locations[0]['id']not in failed:
        location=locations[0]
        write(anchor_cache,{'documentId':document_id,'tabId':tab,'commentId':location['id'],'fingerprint':fingerprint(location)})
    if result.get('verification',{} ) and result['verification'].get('verified'):
        try:cache_references(Document(client.document(document_id),tab),root)
        except (ValueError,OSError)as error:result['cacheError']=str(error)
    write(root / (key + '.result.json'), result)
    finish_run(root,key,saved,result,setup_key)
    return result
