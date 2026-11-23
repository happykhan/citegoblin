"""Compact per-document caches; the shared Google Doc remains authoritative."""
import gzip
import json
import os
from pathlib import Path
import re
from .auth import private_write
from .planning import digest


def document_directory(document_id,tab,base=None):
    for value in (document_id,tab):
        if not re.fullmatch(r'[A-Za-z0-9_.-]+',value) or value in ('.','..'):raise ValueError('Unsafe document or tab identifier')
    root=Path(base).expanduser() if base else Path(os.environ.get('CITEGOBLIN_HOME',Path.home()/'.citegoblin')).expanduser()
    return root/'documents'/document_id/'tabs'/tab


def compact(value):return json.dumps(value,ensure_ascii=False,separators=(',',':'))


def compressed(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    data=gzip.compress(compact(value).encode('utf-8'),mtime=0)
    temporary=path.with_name(path.name+'.tmp')
    handle=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(handle,'wb')as stream:stream.write(data)
    temporary.replace(path)
    return str(path)


def cache_references(document,root):
    registry=document.registry()
    value={'schema':'citegoblin-cache/1','documentId':document.id,'tabId':document.tab_id,
           'style':registry['style'],'locale':registry.get('locale','en-GB'),
           'records':{key:{k:record[k]for k in ('csl','cslOverrides')if k in record} for key,record in sorted(registry['records'].items())},
           'bibliography':{'currentOrder':registry['bibliography'].get('currentOrder',[])},
           'citations':[{'id':c['id'],'items':c['items']}for c in registry['citations']]}
    if 'referenceCleanup'in registry:value['referenceCleanup']=registry['referenceCleanup']
    path=Path(root)/'references.json';text=compact(value)
    if not path.exists()or path.read_text()!=text:private_write(path,text)
    return str(path)


def preview(root,value):return compressed(Path(root)/'preview.json.gz',value)


def finish_run(root,key,saved,result,setup_key=None):
    """Keep one compressed run, retaining every uncertain-write plan and journal."""
    root=Path(root)
    compressed(root/'last-run.json.gz',{'saved':saved,'result':result})
    candidates=[(root/(key+'.plan.json'),root/(key+'.result.json'),root/(digest(saved['plan'])+'.journal.json') if saved.get('plan') else None)]
    if setup_key:candidates.append((root/(setup_key+'.bibliography-plan.json'),None,root/(setup_key+'.bibliography-journal.json')))
    for plan_path,result_path,journal in candidates:
        if journal and journal.exists():
            try:complete=json.loads(journal.read_text()).get('complete')is True
            except (ValueError,OSError):complete=False
            if not complete:continue
            journal.unlink()
        for path in (plan_path,result_path):
            if path:path.unlink(missing_ok=True)
