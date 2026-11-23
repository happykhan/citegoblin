"""Cleanup is restricted to the generated bibliography, never manuscript prose."""
import copy
from .binomials import clean_reference_text,overlay_styles
from .document import units
from .formatting import format_registry
from .planning import build_plan,digest,verify
from .richtext import styling_matches


def body_signature(document,bib):
    """Ignore run segmentation and the bibliography paragraph's final newline."""
    blocks=[];characters=[];previous=None
    for run in document.runs:
        style=run['textRun'].get('textStyle',{});position=run['startIndex']
        for char in run['textRun']['content']:
            excluded=bib['startIndex']<=position<bib['endIndex'] or (position==bib['endIndex']and char=='\n')
            if not excluded:
                if previous!=style and characters:
                    blocks.append({'text':''.join(characters),'style':previous});characters=[]
                previous=style;characters.append(char)
            position+=units(char)
    if characters:blocks.append({'text':''.join(characters),'style':previous})
    return digest(blocks)


def _current_styles(document,bib):
    return [{'start':max(r['startIndex'],bib['startIndex'])-bib['startIndex'],
             'end':min(r['endIndex'],bib['endIndex'])-bib['startIndex'],
             'style':r['textRun'].get('textStyle',{})}for r in document.runs
            if r['startIndex']<bib['endIndex']and r['endIndex']>bib['startIndex']]


def build_cleanup_plan(document,names,*,abbreviations=False,check='all'):
    if check not in ('all','names','bibliography'):raise ValueError('Unknown cleanup check')
    if 'CGPS_DOC_'not in document.groups or 'CGPS_BIB_'not in document.groups:raise ValueError('Mark the References heading with @bib and run CiteGoblin before cleanup')
    registry=copy.deepcopy(document.registry());bib=registry['bibliography']['range']
    current,pending,_=document.text(bib)
    if pending or any(r['textRun'].get('suggestedTextStyleChanges')for r in document.runs if r['startIndex']<bib['endIndex']and r['endIndex']>bib['startIndex']):
        raise ValueError('References contain pending suggestions; review them before cleanup')
    checks=[]
    if check!='bibliography':
        registry['referenceCleanup']={'enabled':True,'names':list(names),'abbreviations':abbreviations}
        checks.append('scientific-names-in-references')
    if check=='names':
        text,found,skipped=clean_reference_text(current,names,abbreviations=abbreviations)
        preview={'citations':[],'bibliography':text,'bibliographyStyles':overlay_styles(_current_styles(document,bib),found),
                 'order':registry['bibliography'].get('currentOrder',[]),'referenceNames':found,'referenceNamesSkipped':skipped}
    else:
        preview=format_registry(registry);checks.append('reference-formatting')
    plan=build_plan(document,registry,formatter=lambda _:preview,bibliography_only=True)
    changes=[]
    for found in preview.get('referenceNames',[]):
        style={'start':found['start'],'end':found['end'],'style':{'italic':True,'smallCaps':False}}
        if current==preview['bibliography']and styling_matches(document,bib,[style]):continue
        changes.append(dict(found,range={'startIndex':bib['startIndex']+found['start'],'endIndex':bib['startIndex']+found['end'],'tabId':document.tab_id}))
    plan.update(schema='citegoblin-cleanup/2',bibliographyOnly=True,scopeRange=bib,
                outputEndIndex=bib['startIndex']+units(plan['expected']['bibliography']),
                bodyStylesHash=body_signature(document,bib),cleanupSettings=registry.get('referenceCleanup'),
                checks=checks,changes=changes,skipped=preview.get('referenceNamesSkipped',[]),
                bibliographyChanged=current!=plan['expected']['bibliography']or not styling_matches(document,bib,preview.get('bibliographyStyles',[])))
    return plan


def verify_cleanup(document,plan):
    if plan.get('schema')!='citegoblin-cleanup/2' or not plan.get('bibliographyOnly'):raise ValueError('Not a References-only cleanup plan; generate a new plan')
    result=verify(document,plan);bib=document.registry()['bibliography']['range']
    if body_signature(document,bib)!=plan['bodyStylesHash']:raise ValueError('Body text or formatting changed outside References')
    if document.value('CGPS_DOC_').get('referenceCleanup')!=plan['cleanupSettings']:raise ValueError('Reference cleanup settings differ from plan')
    return dict(result,checks=plan['checks'],namesChanged=len(plan['changes']),scope='References only')


def _validate_scope(plan):
    if plan.get('schema')!='citegoblin-cleanup/2' or not plan.get('bibliographyOnly'):raise ValueError('Not a References-only cleanup plan; generate a new plan')
    bib=plan['scopeRange'];start=bib['startIndex'];end=plan['outputEndIndex']
    for batch in plan['batches']:
        for request in batch:
            if len(request)!=1:raise ValueError('Invalid cleanup request')
            kind=next(iter(request));data=request[kind]
            if kind=='deleteContentRange':valid=data['range']==bib
            elif kind=='insertText':valid=data['location']=={'index':start,'tabId':bib['tabId']}and data['text']==plan['expected']['bibliography']
            elif kind=='updateTextStyle':
                ran=data['range'];valid=ran.get('tabId')==bib['tabId']and start<=ran['startIndex']<ran['endIndex']<=end
            elif kind in ('createNamedRange','deleteNamedRange'):continue
            else:valid=False
            if not valid:raise ValueError('Cleanup request would edit outside References')


def apply_cleanup(client,plan,journal):
    from .google import apply
    _validate_scope(plan)
    return apply(client,plan,journal,verifier=verify_cleanup)
