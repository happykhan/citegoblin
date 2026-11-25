"""A persistent heading comment selects the managed bibliography location."""
from pathlib import Path
from .commands import anchor_quote,fingerprint,parse,split_section
from .document import Document,units
from .planning import digest

EMPTY='\u200b'


def placement_plan(document,comment,*,export=None):
    if split_section(comment['content'])[0] != document.section or parse(comment)!={'kind':'bibliography'}:raise ValueError('Not a bibliography comment')
    if any(n.startswith('Z_F')for n in document.named):raise ValueError('Zotero fields require explicit migration first')
    managed='CGPS_DOC_'in document.groups
    registry=document.registry() if managed else None
    config = {'schema': 'cgps-citations/1', 'style': 'elsevier-harvard',
              'locale': 'en-GB', 'numbering': 'author-year'}
    if managed:
        config = document.value('CGPS_DOC_')
    elif document.section != 'main':
        main = Document(document.raw, document.tab_id)
        if 'CGPS_DOC_' in main.groups:
            main_config = main.value('CGPS_DOC_')
            config.update({key: main_config[key] for key in ('style', 'locale', 'numbering') if key in main_config})
    if config.get('bibliographyCommentId')==comment['id'] and config.get('processedCommands',{}).get(comment['id'])==fingerprint(comment):return None
    document.check_other_command(comment['id'])
    quote=anchor_quote(comment,export)
    heading=document.heading(quote)
    paragraph_end=heading['endIndex'] + 1
    text,pending,_=document.text(heading)
    if pending or text.strip()!=quote.strip():raise ValueError('Select the complete bibliography heading, without other paragraphs or pending suggestions')
    if any(r['textRun'].get('suggestedTextStyleChanges')for r in document.runs if r['startIndex']<heading['endIndex'] and r['endIndex']>heading['startIndex']):
        raise ValueError('Bibliography heading has pending formatting suggestions')
    for owner, ranges in document.managed_ranges():
        if any(r.get('startIndex', 0) <= paragraph_end and r['endIndex'] > heading['startIndex']
               for r in ranges):
            raise ValueError(f'This heading overlaps a citation or References in section {owner}. Use a different heading.')
    target=heading['endIndex'];requests=[];original=''.join(document.unchanged_text([]))
    old=registry['bibliography']['range'] if registry else None
    bibtext=document.text(old)[0] if old else EMPTY
    if old and document.text(old)[1]:raise ValueError('Bibliography contains pending suggestions')
    if old and old['startIndex']<=target<old['endIndex']:raise ValueError('The heading is inside the existing bibliography')
    if registry and any(c['range']['startIndex']<heading['endIndex'] and c['range']['endIndex']>heading['startIndex']for c in registry['citations']):
        raise ValueError('A managed citation overlaps the bibliography heading')
    # Adopt a bibliography already immediately below this heading without moving text.
    adopt=bool(old and old['startIndex']==paragraph_end)
    expected=original
    if adopt:ran=old
    else:
        original_target=target
        if old:
            requests.extend({'deleteNamedRange':{'namedRangeId':key}}for key in document.ids('CGPS_BIB_'))
            if old['endIndex']>old['startIndex']:requests.append({'deleteContentRange':{'range':old}})
            if old['endIndex']<=target:target-=old['endIndex']-old['startIndex']
        bibtext=bibtext or EMPTY
        inserted='\n'+bibtext
        # Native indices include table structure; they are not offsets into flattened text.
        pieces=[]
        for run in document.runs:
            position=run['startIndex']
            for char in run['textRun']['content']:
                if position==original_target:pieces.append(inserted)
                if not old or not old['startIndex']<=position<old['endIndex']:pieces.append(char)
                position+=units(char)
        expected=''.join(pieces)
        requests.append({'insertText':{'location':{'index':target,'tabId':document.tab_id},'text':inserted}})
        ran={'startIndex':target+1,'endIndex':target+1+units(bibtext),'tabId':document.tab_id}
        requests.extend(document.encode('CGPS_BIB_',document.value('CGPS_BIB_') if managed else {'currentOrder': [], 'renderedTextHash': digest(bibtext)},ran))
        requests.append({'updateParagraphStyle':{'range':ran,'paragraphStyle':{'namedStyleType':'NORMAL_TEXT'},'fields':'namedStyleType'}})
        if old:
            for run in document.runs:
                start=max(old['startIndex'],run['startIndex']);end=min(old['endIndex'],run['endIndex'])
                style=run['textRun'].get('textStyle',{})
                if start<end and style:
                    span=dict(ran,startIndex=ran['startIndex']+start-old['startIndex'],endIndex=ran['startIndex']+end-old['startIndex'])
                    requests.append({'updateTextStyle':{'range':span,'textStyle':style,'fields':','.join(style)}})
    config=dict(config,bibliographyCommentId=comment['id'],processedCommands=dict(config.get('processedCommands',{}),**{comment['id']:fingerprint(comment)}))
    if managed:requests.extend({'deleteNamedRange':{'namedRangeId':key}}for key in document.ids('CGPS_DOC_'))
    requests.extend(document.encode('CGPS_DOC_',config,{'startIndex':0,'endIndex':1,'tabId':document.tab_id}))
    signature=lambda r:{'records':r['records'],'citations':[{k:c[k]for k in ('id','items','text')}for c in r['citations']]}
    return {'schema':'citegoblin-bibliography/1','documentId':document.id,'tabId':document.tab_id,'revisionId':document.revision,
            **({'section': document.section} if document.section != 'main' else {}),
            'requests':requests,'requestHash':digest(requests),'commentId':comment['id'],'config':config,
            'range':ran,'bibliography':bibtext,'expectedTextHash':digest(expected),'tables':document.tables,'images':document.images,
            'registrySignature':signature(registry) if registry else {'records':{},'citations':[]}}


def verify_placement(document,plan):
    if document.id!=plan['documentId'] or document.tab_id!=plan['tabId'] or document.section!=plan.get('section','main'):raise ValueError('Wrong document, tab or section')
    registry=document.registry()
    if document.value('CGPS_DOC_')!=plan['config']:raise ValueError('Bibliography configuration differs from plan')
    if registry['bibliography']['range']!=plan['range'] or document.text(plan['range'])[0]!=plan['bibliography']:raise ValueError('Bibliography location differs from plan')
    signature={'records':registry['records'],'citations':[{k:c[k]for k in ('id','items','text')}for c in registry['citations']]}
    if signature!=plan['registrySignature']:raise ValueError('Existing citations or reference records changed')
    if digest(''.join(document.unchanged_text([])))!=plan['expectedTextHash']:raise ValueError('Document text differs from bibliography placement plan')
    if document.tables!=plan['tables'] or document.images!=plan['images']:raise ValueError('Document structure changed')
    return {'verified':True,'commentKeptOpen':plan['commentId']}


def apply_placement(client,plan,journal):
    from .live import write
    if plan.get('schema')!='citegoblin-bibliography/1' or digest(plan['requests'])!=plan['requestHash']:raise ValueError('Invalid bibliography placement plan')
    journal=Path(journal)
    if journal.exists():raise ValueError('Bibliography setup already attempted; inspect live state before retrying')
    document=Document(client.document(plan['documentId']),plan['tabId'],plan.get('section','main'))
    if document.revision!=plan['revisionId']:raise ValueError('Document changed; regenerate the plan')
    write(journal,{'inflight':True,'planHash':digest(plan)})
    client.batch(document.id,plan['requests'],document.revision)
    result=verify_placement(Document(client.document(document.id),document.tab_id,document.section),plan)
    write(journal,{'complete':True,'verification':result});return result
