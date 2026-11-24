"""Pure edit planning: exact anchors, stable IDs, indivisible field packages."""
import copy
import hashlib
import json
import secrets
import string
from .document import encode, units
from .formatting import format_registry
from .styles import load_style
from .richtext import styling_matches
from .references import record, normal_doi


def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()


def build_plan(document, registry, *, allow_suggestions=False, formatter=format_registry, bibliography_only=False, replace_edited_references=False):
    before=document.registry(); old={c['id']:c for c in before['citations']}
    preview=formatter(registry)
    # Keep an invisible, non-empty native range until the first reference exists.
    if not preview['bibliography']:preview['bibliography']='\u200b'
    if bibliography_only:
        preview['citations']=[{'id':c['id'],'text':c['text']}for c in before['citations']]
        preview['citationStyles']={c['id']:[{'start':max(r['startIndex'],c['range']['startIndex'])-c['range']['startIndex'],
                    'end':min(r['endIndex'],c['range']['endIndex'])-c['range']['startIndex'],'style':r['textRun'].get('textStyle',{})}
                    for r in document.runs if r['startIndex']<c['range']['endIndex']and r['endIndex']>c['range']['startIndex']]for c in before['citations']}
    updates={c['id']:c['text'] for c in preview['citations']}
    packages=[]; new_ids=[]; operations=[]; tab=document.tab_id
    def replacement(prefix,text,ran,payload,style,new=False,spans=()):
        start=ran['startIndex']; package=[]
        if not new: package.extend({'deleteNamedRange':{'namedRangeId':i}} for i in document.ids(prefix))
        if ran['endIndex']>start: package.append({'deleteContentRange':{'range':ran}})
        insert=' '+text if new else text
        package.append({'insertText':{'text':insert,'location':{'index':start,'tabId':tab}}})
        newrange={'startIndex':start+(1 if new else 0),'endIndex':start+units(insert),'tabId':tab}
        style=dict(style);style.pop('link',None);style.update({'italic':False,'bold':False,'smallCaps':False,'underline':False,'baselineOffset':'NONE'})
        package.append({'updateTextStyle':{'range':newrange,'textStyle':style,'fields':','.join(style)}})
        for span in spans:
            package.append({'updateTextStyle':{'range':dict(newrange,startIndex=newrange['startIndex']+span['start'],endIndex=newrange['startIndex']+span['end']),
                           'textStyle':span['style'],'fields':','.join(span['style'])}})
        package.extend(encode(prefix,payload,newrange));return package
    bibliography = before['bibliography']
    bib = bibliography['range']
    old_text, pending, _ = document.text(bib)
    desired_text = preview['bibliography']
    bibspans = preview.get('bibliographyStyles', [])
    rendered_hash = digest(desired_text)
    payload = {'currentOrder': preview['order'], 'renderedTextHash': rendered_hash}
    rewrite = old_text != desired_text or not styling_matches(document, bib, bibspans)
    marker_changed = any(bibliography.get(key) != value for key, value in payload.items())

    if rewrite or marker_changed:
        if pending and not allow_suggestions:
            raise ValueError('Bibliography contains pending suggestions')
        if not replace_edited_references:
            baseline = bibliography.get('renderedTextHash')
            if baseline is None:
                # On the first run after upgrading, compare against the stored register
                # and style rather than treating existing manual edits as the baseline.
                if old_text == desired_text and bibliography.get('currentOrder', []) == preview['order']:
                    baseline = rendered_hash
                else:
                    baseline = digest(format_registry(before)['bibliography'] or '\u200b')
            if digest(old_text) != baseline:
                raise ValueError('References text has manual edits or differs from the last generated list. '
                                 'Restore the generated text, or add @refresh replace-references to replace the list.')
        if rewrite:
            requests = replacement('CGPS_BIB_', desired_text, bib, payload,
                                   document.style_at(bib['startIndex']), spans=bibspans)
        else:
            requests = [{'deleteNamedRange': {'namedRangeId': key}}
                        for key in document.ids('CGPS_BIB_')]
            requests.extend(encode('CGPS_BIB_', payload, bib))
        packages.append((bib['startIndex'], requests))
    for citation in registry['citations']:
        if bibliography_only:continue
        key=citation['id'];text=updates[key];prefix='CGPS_CITE_'+key+'_';new=key not in old
        spans=preview.get('citationStyles',{}).get(key,[])
        if not new and old[key]['text']==text and styling_matches(document,old[key]['range'],spans): continue
        if not new and old[key]['pendingSuggestion'] and not allow_suggestions:
            raise ValueError('Citation text is in a pending suggestion: '+key)
        if new:
            new_ids.append(key);ran=citation['range'];payload={'items':citation['items']}
        else:
            ran=old[key]['range'];payload=document.value(prefix);payload['items']=citation['items']
        packages.append((ran['startIndex'],replacement(prefix,text,ran,payload,document.style_at(ran['startIndex']),new,spans)))
        operations.append({'citationId':key,'old':old.get(key,{}).get('text'),'new':text,'range':ran})
    # Text operations go backwards; Docs then tracks later named ranges automatically.
    ordered=[p for _,p in sorted(packages,key=lambda p:p[0],reverse=True)]
    anchor={'startIndex':0,'endIndex':1,'tabId':tab}
    for item in registry['records'].values():
        prefix='CGPS_REF_'+item['id']+'_';payload=copy.deepcopy(item);payload['currentNumber']=None
        if prefix in document.groups and document.value(prefix)==payload: continue
        ordered.append(([{'deleteNamedRange':{'namedRangeId':i}}for i in document.ids(prefix)]if prefix in document.groups else [])+encode(prefix,payload,anchor))
    config={k:v for k,v in document.value('CGPS_DOC_').items()}
    if 'referenceCleanup'in registry:config['referenceCleanup']=copy.deepcopy(registry['referenceCleanup'])
    config.update({'style':registry['style'],'numbering':'numeric' if load_style(registry['style'])[0]['citationFormat']=='numeric' else 'author-year','processedCommands':registry.get('processedCommands',{})})
    if config!=document.value('CGPS_DOC_'):
        ordered.append([{'deleteNamedRange':{'namedRangeId':i}}for i in document.ids('CGPS_DOC_')]+encode('CGPS_DOC_',config,anchor))
    batches=[];batch=[]
    for package in ordered:
        if batch and len(json.dumps(batch+package))>40000: batches.append(batch);batch=[]
        batch.extend(package)
    if batch:batches.append(batch)
    exclusions=[c['range']for c in before['citations']]+[bib]
    return {'schema':'citegoblin-plan/1','documentId':document.id,'tabId':tab,'revisionId':document.revision,
            'batches':batches,'batchHashes':[digest(b)for b in batches],'operations':operations,
            'newCitationIds':new_ids,'expected':{'style':registry['style'],'references':sorted(registry['records']),
            'citationItems':{c['id']:c['items'] for c in registry['citations']},
            'recordHashes':{k:digest(dict(v,currentNumber=None)) for k,v in registry['records'].items()},
            'processedCommands':registry.get('processedCommands',{}),
            'citationStyles':preview.get('citationStyles',{}),'bibliographyStyles':bibspans,'bibliographyTextHash':rendered_hash,
            'citations':updates,'bibliography':preview['bibliography'],'unchangedTextHash':digest(document.unchanged_text(exclusions)),
            'tables':document.tables,'images':document.images}}


def add_citation(document, registry, quote, items, *, occurrence=None, allow_suggestions=False):
    ran=document.locate(quote,occurrence);_,pending,_=document.text(ran)
    if pending and not allow_suggestions: raise ValueError('Selected passage contains a pending suggestion')
    end=ran['endIndex']
    if quote[-1:] in '.;:,': end-=units(quote[-1])
    bib = registry['bibliography']['range']
    if bib['startIndex'] <= end <= bib['endIndex']:
        raise ValueError('Select a passage outside the generated References list')
    if any(c['range']['startIndex']<=end<c['range']['endIndex'] for c in registry['citations']):
        raise ValueError('Insertion point falls inside an existing citation')
    for item in items:
        if item['id']not in registry['records']: raise ValueError('Reference not in registry')
    # Same-position commands form a single citation group.
    for citation in registry['citations']:
        if citation.get('_new') and citation['range']['startIndex']==end:
            citation['items']+= [i for i in items if i not in citation['items']];return citation['id']
    key='c'+''.join(secrets.choice(string.ascii_letters+string.digits)for _ in range(6))
    while any(c['id']==key for c in registry['citations']):
        key='c'+''.join(secrets.choice(string.ascii_letters+string.digits)for _ in range(6))
    registry['citations'].append({'id':key,'items':items,'range':{'startIndex':end,'endIndex':end,'tabId':document.tab_id},'text':'','_new':True})
    registry['citations'].sort(key=lambda c:c['range']['startIndex'])
    return key


def verify(document, plan):
    registry=document.registry();expected=plan['expected']
    if document.id!=plan['documentId'] or document.tab_id!=plan['tabId']: raise ValueError('Wrong document/tab')
    if sorted(registry['records'])!=expected['references']: raise ValueError('Reference registry changed')
    if {c['id']:c['items'] for c in registry['citations']}!=expected['citationItems']:
        raise ValueError('Citation source mappings differ from plan')
    if {k:digest(dict(v,currentNumber=None)) for k,v in registry['records'].items()}!=expected['recordHashes']:
        raise ValueError('Reference metadata differs from plan')
    if registry.get('processedCommands',{})!=expected['processedCommands']:
        raise ValueError('Processed comment ledger differs from plan')
    actual={c['id']:c['text'] for c in registry['citations']}
    if actual!=expected['citations']: raise ValueError('Citation text or identities differ from plan')
    bib=registry['bibliography']['range']
    if 'bibliographyTextHash' in expected:
        if registry['bibliography'].get('renderedTextHash') != expected['bibliographyTextHash']:
            raise ValueError('Stored References text fingerprint differs from plan')
    if document.text(bib)[0]!=expected['bibliography']: raise ValueError('Bibliography differs from plan')
    if not styling_matches(document,bib,expected.get('bibliographyStyles',[])):
        raise ValueError('Bibliography inline formatting differs from plan')
    for citation in registry['citations']:
        if not styling_matches(document,citation['range'],expected.get('citationStyles',{}).get(citation['id'],[])):
            raise ValueError('Citation inline formatting differs from plan')
    exclusions=[dict(c['range'],startIndex=c['range']['startIndex']-(1 if c['id']in plan['newCitationIds']else 0))for c in registry['citations']]+[bib]
    if digest(document.unchanged_text(exclusions))!=expected['unchangedTextHash']: raise ValueError('Text outside authorised citation ranges changed')
    if document.tables!=expected['tables'] or document.images!=expected['images']: raise ValueError('Native structure changed')
    if registry['style']!=expected['style']: raise ValueError('Style metadata differs from plan')
    return {'verified':True,'citations':len(actual),'references':len(registry['records'])}
