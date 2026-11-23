"""Opt-in scientific-name typography, using an explicit approved-name catalogue."""
import json
from pathlib import Path
import re
from .document import units
from .planning import digest

CATALOGUE=Path(__file__).parent/'data/binomials.json'


def load_names(extra=None):
    names=[r['name']for r in json.loads(CATALOGUE.read_text())['names']]
    if extra:
        path=Path(extra).expanduser()
        names.extend(line.strip()for line in path.read_text().splitlines() if line.strip()and not line.lstrip().startswith('#'))
    result={}
    for value in names:
        match=re.fullmatch(r'([A-Za-z][a-zA-Z-]+)\s+([A-Za-z][a-zA-Z-]+)',value.strip())
        if not match:raise ValueError('Approved names must be two Latin-alphabet words: '+value)
        canonical=match[1].capitalize()+' '+match[2].lower()
        result[canonical.casefold()]=canonical
    return list(result.values())


def _segments(document):
    for paragraph in document.paragraphs:
        text='';positions=[]
        for run in paragraph['runs']:
            pos=run['startIndex']
            for char in run['textRun']['content']:
                positions.append(pos);text+=char;pos+=units(char)
        yield text,positions


def _protected(document):
    ranges=[]
    for name,group in document.named.items():
        if name.startswith(('CGPS_CITE_','CGPS_BIB_','Z_F')):
            ranges.extend(r for n in group['namedRanges']for r in n['ranges'])
    return ranges


def build_binomial_plan(document,names,*,abbreviations=False):
    approved=[]
    for value in names:
        match=re.fullmatch(r'([A-Z][a-z-]+) ([a-z][a-z-]+)',value)
        if not match:raise ValueError('Invalid canonical binomial: '+value)
        approved.append((match[1],match[2]))
    if not approved:raise ValueError('The approved-name list is empty')
    terms='|'.join(re.escape(g)+r'(?P<gap'+str(i)+r'>[ \t\u00a0]+)'+re.escape(s)for i,(g,s)in enumerate(approved))
    pattern=re.compile(r'(?<![\w-])(?:'+terms+r')(?![\w-])',re.I)
    abbreviated=re.compile(r'(?<![\w-])([A-Za-z])\.([ \t\u00a0]+)([A-Za-z][A-Za-z-]+)(?![\w-])')
    protected=_protected(document);changes=[];skipped=[];seen={};patches={}
    for text,positions in _segments(document):
        matches=[(m,False)for m in pattern.finditer(text)]
        if abbreviations:matches.extend((m,True)for m in abbreviated.finditer(text))
        for match,short in sorted(matches,key=lambda item:item[0].start()):
            if short and not any(g[0].lower()==match[1].lower() and s==match[3].lower() for g,s in approved):continue
            start=positions[match.start()];end=positions[match.end()-1]+units(match[0][-1])
            ran={'startIndex':start,'endIndex':end,'tabId':document.tab_id}
            if any(start<r['endIndex']and end>r.get('startIndex',0)for r in protected):
                skipped.append({'text':match[0],'range':ran,'reason':'managed citation or bibliography'});continue
            try:original,pending,_=document.text(ran)
            except ValueError:
                skipped.append({'text':match[0],'range':ran,'reason':'non-text structure'});continue
            runs=[r for r in document.runs if start<r['endIndex']and end>r['startIndex']]
            if pending or any(r['textRun'].get('suggestedTextStyleChanges')for r in runs):
                skipped.append({'text':original,'range':ran,'reason':'pending suggestion'});continue
            if any(r['textRun'].get('textStyle',{}).get('link')for r in runs):
                skipped.append({'text':original,'range':ran,'reason':'hyperlink'});continue
            if short:
                candidates={g for g,s in approved if g[0].lower()==match[1].lower() and s==match[3].lower()
                            and g in seen.get(s,set())}
                if len(candidates)!=1:
                    skipped.append({'text':original,'range':ran,'reason':'abbreviated genus lacks unique earlier full-name context'});continue
                replacement=match[1].upper()+'.'+match[2]+match[3].lower()
            else:
                index=next(i for i in range(len(approved)) if match.group('gap'+str(i))is not None)
                genus,species=approved[index];seen.setdefault(species,set()).add(genus)
                replacement=genus+match.group('gap'+str(index))+species
            if units(original)!=units(replacement):raise ValueError('Case change would alter UTF-16 length')
            styled=all(r['textRun'].get('textStyle',{}).get('italic')is True and
                       r['textRun'].get('textStyle',{}).get('smallCaps',False)is False for r in runs)
            if replacement==original and styled:continue
            changes.append({'before':original,'after':replacement,'range':ran,'italic':True,'smallCaps':False})
            position=start
            for old,new in zip(original,replacement):
                if old!=new:patches[position]=new
                position+=units(old)
    packages=[]
    for change in sorted(changes,key=lambda c:c['range']['startIndex'],reverse=True):
        ran=change['range'];position=ran['startIndex'];characters=[]
        for old,new in zip(change['before'],change['after']):
            if old!=new:characters.append((position,new,document.style_at(position)))
            position+=units(old)
        package=[]
        # Change only individual letters. Do not delete whole words or passages.
        for position,char,style in reversed(characters):
            location={'index':position,'tabId':document.tab_id}
            letter_range={'startIndex':position,'endIndex':position+units(char),'tabId':document.tab_id}
            package.extend([{'deleteContentRange':{'range':letter_range}},
                            {'insertText':{'location':location,'text':char}}])
            if style:package.append({'updateTextStyle':{'range':letter_range,'textStyle':style,'fields':','.join(style)}})
        package.append({'updateTextStyle':{'range':ran,'textStyle':{'italic':True,'smallCaps':False},'fields':'italic,smallCaps'}})
        packages.append(package)
    batches=[];batch=[]
    for package in packages:
        if batch and len(json.dumps(batch+package))>40000:batches.append(batch);batch=[]
        batch+=package
    if batch:batches.append(batch)
    expected=[]
    for paragraph in document.paragraphs:
        content=''
        for run in paragraph['runs']:
            position=run['startIndex']
            for char in run['textRun']['content']:
                content+=patches.get(position,char);position+=units(char)
        if content:expected.append(content)
    return {'schema':'citegoblin-binomials/1','documentId':document.id,'tabId':document.tab_id,
            'revisionId':document.revision,'changes':changes,'skipped':skipped,'batches':batches,
            'batchHashes':[digest(b)for b in batches],'expectedTextHash':digest(expected),
            'tables':document.tables,'images':document.images}


def verify_binomials(document,plan):
    if document.id!=plan['documentId']or document.tab_id!=plan['tabId']:raise ValueError('Wrong document or tab')
    if digest(document.unchanged_text([]))!=plan['expectedTextHash']:raise ValueError('Document text differs from the approved case changes')
    if document.tables!=plan['tables']or document.images!=plan['images']:raise ValueError('Native structure changed')
    for change in plan['changes']:
        ran=change['range']
        if document.text(ran)[0]!=change['after']:raise ValueError('Scientific name differs from plan')
        for run in document.runs:
            if run['startIndex']<ran['endIndex']and run['endIndex']>ran['startIndex']:
                style=run['textRun'].get('textStyle',{})
                if style.get('italic')is not True or style.get('smallCaps',False)is not False:
                    raise ValueError('Scientific-name formatting differs from plan')
    return {'verified':True,'namesChanged':len(plan['changes'])}


def apply_binomials(client,plan,journal):
    from .document import Document
    from .live import write
    if plan.get('schema')!='citegoblin-binomials/1':raise ValueError('Not a binomial-formatting plan')
    if [digest(b)for b in plan['batches']]!=plan['batchHashes']:raise ValueError('Plan batch hashes do not match')
    journal=Path(journal);journal.parent.mkdir(parents=True,exist_ok=True)
    if journal.exists():
        previous=json.loads(journal.read_text())
        if previous.get('planHash')!=digest(plan):raise ValueError('Journal belongs to another plan')
        if previous.get('complete'):return verify_binomials(Document(client.document(plan['documentId']),plan['tabId']),plan)
        raise ValueError('An earlier run is incomplete; inspect live state and replan, do not replay')
    current=client.document(plan['documentId'])
    if current['revisionId']!=plan['revisionId']:raise ValueError('Document changed; regenerate the plan')
    state={'planHash':digest(plan),'complete':False,'done':0,'inflight':None,'revision':plan['revisionId']}
    write(journal,state)
    for i,batch in enumerate(plan['batches']):
        state['inflight']=i;write(journal,state)
        response=client.batch(plan['documentId'],batch,state['revision'])
        revision=response.get('writeControl',{}).get('requiredRevisionId')
        if not revision:raise ValueError('Write result has no revision; inspect before retrying')
        state.update(done=i+1,inflight=None,revision=revision);write(journal,state)
    result=verify_binomials(Document(client.document(plan['documentId']),plan['tabId']),plan)
    state.update(complete=True,verification=result);write(journal,state)
    return result
