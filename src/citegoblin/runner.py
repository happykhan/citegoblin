"""Deterministic user commands: no source relevance assessment and no AI calls."""
import copy
import subprocess
from .commands import parse,fingerprint,anchor_quote
from .planning import add_citation,build_plan
from .references import lookup_doi,lookup_pmid,record,normal_doi
from .bibliographic import lookup_reference


def commands_plan(document,comments,*,reference_data=(),lookup=lookup_doi,pmid_lookup=lookup_pmid,reference_lookup=lookup_reference,export=None,allow_suggestions=False,formatter=None):
    registry=copy.deepcopy(document.registry());processed=registry.setdefault('processedCommands',{})
    for data in reference_data:
        r=record(data,registry['records']);registry['records'][r['id']]=r
    accepted=[];errors=[];previous=[]
    def report():
        ids={c['commentId'] for c in accepted+previous+errors}
        return {'processed':accepted,'alreadyProcessed':previous,'errors':errors,
                'comments':[{k:c[k] for k in ('id','content','anchor','replies','_repliesComplete') if k in c} for c in comments if c['id'] in ids]}
    for comment in sorted(comments,key=lambda c:(c.get('createdTime',''),c['id'])):
        if comment.get('resolved') or comment.get('deleted'):continue
        stamp=fingerprint(comment)
        if processed.get(comment['id'])==stamp:
            previous.append({'commentId':comment['id'],**({'keepOpen':True} if comment.get('content','').strip() in ('@bib','@references') else {})});continue
        try:command=parse(comment)
        except ValueError as error:errors.append({'commentId':comment['id'],'error':str(error)});continue
        if command is None:continue
        # Stage one command so a failed anchor cannot add a stray reference.
        staged=copy.deepcopy(registry)
        try:
            if command['kind']=='bibliography':raise ValueError('Bibliography placement requires the run command')
            if command['kind']=='style':staged['style']=command['style']
            elif command['kind']=='cite':
                quote=anchor_quote(comment,export)
                # Resolve the location before performing a remote lookup.
                document.locate(quote)
                if 'doi'in command:
                    ref=next((r for r in staged['records'].values()if r.get('doi')and normal_doi(r['doi'])==command['doi']),None)
                    if ref is None:ref=record(lookup(command['doi']),staged['records'])
                elif 'pmid' in command:
                    ref=next((r for r in staged['records'].values() if str(r.get('pmid') or r['csl'].get('PMID',''))==command['pmid']),None)
                    if ref is None:ref=record(pmid_lookup(command['pmid']),staged['records'],pmid=command['pmid'])
                elif 'reference' in command:
                    ref=record(reference_lookup(command['reference']),staged['records'])
                elif command['source'].startswith('ref:'):
                    ref=staged['records'].get(command['source'][4:])
                else:
                    url=command['source'][4:].rstrip('/')
                    matches=[r for r in staged['records'].values()if r['csl'].get('URL','').rstrip('/')==url]
                    if len(matches)!=1:raise ValueError('URL needs one matching supplied CSL reference record')
                    ref=matches[0]
                if ref is None:raise ValueError('Reference ID not found')
                staged['records'][ref['id']]=ref
                add_citation(document,staged,quote,[{'id':ref['id']}],allow_suggestions=allow_suggestions)
        except (ValueError,OSError,RuntimeError)as error:
            errors.append({'commentId':comment['id'],'error':str(error)});continue
        registry=staged;registry.setdefault('processedCommands',{})[comment['id']]=stamp;processed=registry['processedCommands']
        accepted.append({'commentId':comment['id'],'kind':command['kind']})
    if not accepted:return None,report()
    options={'allow_suggestions':allow_suggestions}
    if formatter is not None:options['formatter']=formatter
    try:
        plan=build_plan(document,registry,**options)
    except (ValueError,OSError,RuntimeError,subprocess.SubprocessError) as error:
        errors.extend({'commentId':c['commentId'],'error':str(error)} for c in accepted)
        accepted.clear()
        return None,report()
    feedback=report();plan['feedback']=feedback
    return plan,feedback
