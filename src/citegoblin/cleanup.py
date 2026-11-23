"""Explicit, reviewable cleanup checks; no source inference or prose rewriting."""
import copy
from .binomials import build_binomial_plan,verify_binomials
from .document import Document,units
from .planning import build_plan,digest,verify


def _case_preview(document,changes):
    resource=copy.deepcopy(document.raw)
    preview=Document(resource,document.tab_id)
    patches={}
    for change in changes:
        position=change['range']['startIndex']
        for before,after in zip(change['before'],change['after']):
            if before!=after:patches[position]=after
            position+=units(before)
    for run in preview.runs:
        position=run['startIndex'];text=[]
        for char in run['textRun']['content']:
            text.append(patches.get(position,char));position+=units(char)
        run['textRun']['content']=''.join(text)
    return Document(resource,document.tab_id)


def build_cleanup_plan(document,names,*,abbreviations=False,check='all'):
    if check not in ('all','names','citations'):raise ValueError('Unknown cleanup check')
    names_plan=build_binomial_plan(document,names,abbreviations=abbreviations) if check!='citations' else None
    changes=names_plan['changes'] if names_plan else []
    preview=_case_preview(document,changes)
    citation_plan=None;checks=['scientific-names'] if names_plan else []
    # A missing register is normal for an ordinary document. A broken one is an error.
    managed='CGPS_DOC_'in document.groups
    if check!='names' and managed:
        citation_plan=build_plan(preview,preview.registry());checks.append('citations-and-bibliography')
    elif check=='citations':raise ValueError('Document has no CiteGoblin register; initialise it first')
    batches=(names_plan['batches'] if names_plan else [])+(citation_plan['batches'] if citation_plan else [])
    final_names=copy.deepcopy(changes)
    bibliography_changed=False
    if citation_plan:
        before=document.registry();bib=before['bibliography']['range']
        bibliography_changed=document.text(bib)[0]!=citation_plan['expected']['bibliography']
        shifts=[(op['range']['endIndex'],units(op['new'])-units(op['old']))for op in citation_plan['operations']]
        shifts.append((bib['endIndex'],units(citation_plan['expected']['bibliography'])-(bib['endIndex']-bib['startIndex'])))
        for change in final_names:
            ran=change['range'];delta=sum(delta for end,delta in shifts if end<=ran['startIndex'])
            ran['startIndex']+=delta;ran['endIndex']+=delta
    return {'schema':'citegoblin-cleanup/1','documentId':document.id,'tabId':document.tab_id,
            'revisionId':document.revision,'checks':checks,'changes':changes,
            'skipped':names_plan['skipped'] if names_plan else [],
            'operations':citation_plan['operations'] if citation_plan else [],
            'bibliographyChanged':bibliography_changed,'finalNames':final_names,
            'namesPlan':names_plan,'citationPlan':citation_plan,
            'batches':batches,'batchHashes':[digest(b)for b in batches]}


def verify_cleanup(document,plan):
    if plan.get('schema')!='citegoblin-cleanup/1':raise ValueError('Not a cleanup plan')
    if plan['citationPlan']:
        result=verify(document,plan['citationPlan'])
        for change in plan['finalNames']:
            ran=change['range']
            if document.text(ran)[0]!=change['after']:raise ValueError('Cleaned name differs from plan')
            for run in document.runs:
                if run['startIndex']<ran['endIndex'] and run['endIndex']>ran['startIndex']:
                    style=run['textRun'].get('textStyle',{})
                    if style.get('italic')is not True or style.get('smallCaps',False):
                        raise ValueError('Cleaned name formatting differs from plan')
    else:result=verify_binomials(document,plan['namesPlan'])
    return dict(result,checks=plan['checks'],namesChanged=len(plan['changes']))


def apply_cleanup(client,plan,journal):
    from .google import apply
    if plan.get('schema')!='citegoblin-cleanup/1':raise ValueError('Not a cleanup plan')
    return apply(client,plan,journal,verifier=verify_cleanup)
