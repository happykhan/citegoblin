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


def write(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2))
    temporary.replace(path)


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


def run_once(client, document_id, tab, workdir, *, reference_data=(), dry_run=False,
             allow_suggestions=False, lookup=None):
    root = Path(workdir)
    root.mkdir(parents=True, exist_ok=True)
    comments = client.comments(document_id)
    pending=[c for c in comments if not c.get('resolved') and not c.get('deleted')
             and c.get('content','').strip().startswith(('@cite','@style','@refresh'))]
    if not pending:
        return {'dryRun':dry_run,'idle':True,'report':{'processed':[],'alreadyProcessed':[],'errors':[],'comments':[]}}
    parse_errors=[]
    for comment in pending:
        try:parse(comment)
        except ValueError as failure:parse_errors.append({'commentId':comment['id'],'error':str(failure)})
    if len(parse_errors)==len(pending):
        report={'processed':[],'alreadyProcessed':[],'errors':parse_errors,'comments':pending}
        if dry_run:return {'dryRun':True,'report':report}
        feedback=sync_feedback(client,document_id,comments,report,verified=False)
        return {'verification':None,'report':report,'feedback':feedback}
    try:
        document = Document(client.document(document_id), tab)
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
                    and c.get('content', '').strip().startswith(('@cite', '@style', '@refresh'))]
        report = {'processed': [], 'alreadyProcessed': [],
                  'errors': [{'commentId': c['id'], 'error': str(failure)} for c in commands],
                  'comments': commands}
        plan = None
    saved = {'documentId': document_id, 'plan': plan, 'report': report}
    key = digest(saved)
    write(root / (key + '.plan.json'), saved)
    if dry_run:
        return {'dryRun': True, 'report': report}
    if plan:
        result = apply_with_feedback(client, saved, root / (digest(plan) + '.journal.json'))
    else:
        # The embedded ledger is written after the text batches. Already-applied
        # commands need comment-cleanup retries only, never another insertion.
        feedback = sync_feedback(client, document_id, comments, report, verified=True)
        result = {'verification': None, 'report': report, 'feedback': feedback}
    write(root / (key + '.result.json'), result)
    return result
