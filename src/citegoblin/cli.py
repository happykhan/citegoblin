import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
import re
from .document import Document,encode
from .formatting import FORMATTER,format_registry
from .styles import installed_styles,install_style,resolve_style
from .references import resolve,comment_candidates
from .planning import build_plan,verify,digest
from .runner import commands_plan


def read(path):return json.loads(Path(path).read_text())
def write(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2))
def emit(value):print(json.dumps(value,ensure_ascii=False,indent=2))


def main():
    p=argparse.ArgumentParser(description='Comment-driven Google Docs citation management. No Zotero or AI.')
    sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('setup-formatter')
    q=sub.add_parser('binomials',help='Preview and apply scientific-name case and italics')
    actions=q.add_subparsers(dest='binomial_action',required=True)
    q=actions.add_parser('plan');q.add_argument('source',help='Native document JSON, document ID or Google Docs URL')
    q.add_argument('--tab',required=True);q.add_argument('--output',required=True)
    q.add_argument('--names',help='Additional approved binomials, one per line')
    q.add_argument('--abbreviations',action='store_true',help='Also format abbreviations with unique earlier full-name context')
    q=actions.add_parser('apply');q.add_argument('plan');q.add_argument('--journal',required=True)
    q=sub.add_parser('styles',help='List or install Zotero-compatible CSL styles')
    actions=q.add_subparsers(dest='style_action',required=True)
    actions.add_parser('list')
    install=actions.add_parser('install');install.add_argument('style_id')
    q=sub.add_parser('login');q.add_argument('--client-secrets');q.add_argument('--token-file')
    sub.add_parser('auth-status')
    sub.add_parser('logout')
    q=sub.add_parser('export',help='Export references as BibTeX, RIS or EndNote tagged text')
    q.add_argument('source',help='Register JSON, native document JSON, Google Docs ID or URL')
    q.add_argument('--format',required=True,choices=('bibtex','ris','endnote'))
    q.add_argument('--output',required=True,help='Destination file, or - for standard output')
    q.add_argument('--tab',help='Required for native document JSON or a live Google document')
    q.add_argument('--cited-only',action='store_true',help='Export only references used in managed citations')
    q=sub.add_parser('lookup');q.add_argument('source')
    q=sub.add_parser('comments');q.add_argument('input')
    q=sub.add_parser('scan');q.add_argument('input');q.add_argument('--tab',required=True);q.add_argument('--output',required=True)
    q=sub.add_parser('format');q.add_argument('input');q.add_argument('--output',required=True);q.add_argument('--style')
    q=sub.add_parser('plan');q.add_argument('input');q.add_argument('--tab',required=True);q.add_argument('--output',required=True);q.add_argument('--style');q.add_argument('--allow-citation-suggestions',action='store_true')
    q=sub.add_parser('process-comments');q.add_argument('input');q.add_argument('comments');q.add_argument('--tab',required=True);q.add_argument('--output',required=True);q.add_argument('--references');q.add_argument('--docx');q.add_argument('--allow-citation-suggestions',action='store_true')
    q=sub.add_parser('verify');q.add_argument('input');q.add_argument('plan')
    q=sub.add_parser('apply');q.add_argument('plan');q.add_argument('--journal',required=True)
    q=sub.add_parser('init');q.add_argument('document_id');q.add_argument('--tab',required=True);q.add_argument('--placeholder',default='[[bibliography]]');q.add_argument('--workdir',required=True);q.add_argument('--dry-run',action='store_true')
    q=sub.add_parser('init-plan');q.add_argument('input');q.add_argument('--tab',required=True);q.add_argument('--placeholder',default='[[bibliography]]');q.add_argument('--output',required=True)
    q=sub.add_parser('run');q.add_argument('document_id');q.add_argument('--tab',required=True);q.add_argument('--workdir',required=True);q.add_argument('--references');q.add_argument('--dry-run',action='store_true');q.add_argument('--watch',type=int,metavar='SECONDS');q.add_argument('--allow-citation-suggestions',action='store_true')
    a=p.parse_args()
    try:
        if a.command in ('login','auth-status','logout'):
            from . import auth
            if a.command=='login':
                auth.login(a.client_secrets,a.token_file);emit({'signedIn':True})
            elif a.command=='logout':emit(auth.logout())
            else:emit(auth.status())
            return
        if a.command=='binomials':
            from .binomials import build_binomial_plan,load_names,apply_binomials
            if a.binomial_action=='apply':
                from .google import Google
                emit(apply_binomials(Google(),read(a.plan),a.journal));return
            source=Path(a.source).expanduser()
            if source.is_file():document=Document(read(source),a.tab)
            else:
                match=re.fullmatch(r'https://docs\.google\.com/document/d/([A-Za-z0-9_-]+)(?:/[^\s]*)?',a.source)
                key=match[1]if match else a.source
                if not re.fullmatch(r'[A-Za-z0-9_-]{10,}',key):raise ValueError('Source is not an existing JSON file or a Google document ID/URL')
                from .google import Google
                document=Document(Google().document(key),a.tab)
            plan=build_binomial_plan(document,load_names(a.names),abbreviations=a.abbreviations)
            write(a.output,plan)
            emit({'namesToChange':len(plan['changes']),'changes':plan['changes'],'skipped':plan['skipped'],'plan':a.output});return
        if a.command=='styles':
            if a.style_action=='install':emit(install_style(a.style_id))
            else:emit([{k:v for k,v in info.items()if k!='path'} for info in installed_styles().values()])
            return
        if a.command=='setup-formatter':
            subprocess.run(['npm','ci','--ignore-scripts','--prefix',str(FORMATTER)],check=True);return
        if a.command=='export':
            from .exporting import export_references
            path=Path(a.source).expanduser()
            if path.is_file():
                data=read(path)
                if isinstance(data,dict) and 'records'in data:registry=data
                else:
                    if not a.tab:raise ValueError('--tab is required for native document JSON')
                    registry=Document(data,a.tab).registry()
            else:
                if not a.tab:raise ValueError('--tab is required for a live Google document')
                match=re.fullmatch(r'https://docs\.google\.com/document/d/([A-Za-z0-9_-]+)(?:/[^\s]*)?',a.source)
                key=match[1]if match else a.source
                if not re.fullmatch(r'[A-Za-z0-9_-]{10,}',key):raise ValueError('Source is not an existing JSON file or a Google document ID/URL')
                from .google import Google
                registry=Document(Google().document(key),a.tab).registry()
            content=export_references(registry,a.format,cited_only=a.cited_only)
            if a.output=='-':sys.stdout.write(content)
            else:Path(a.output).expanduser().write_text(content,encoding='utf-8')
            return
        if a.command=='lookup':emit(resolve(a.source));return
        if a.command=='comments':
            data=read(a.input);emit(comment_candidates(data if isinstance(data,list)else data['comments']));return
        if a.command=='scan':write(a.output,Document(read(a.input),a.tab).registry());return
        if a.command=='format':
            registry=read(a.input)
            if a.style:registry['style']=resolve_style(a.style)
            write(a.output,format_registry(registry));return
        if a.command=='apply':
            from .google import Google
            from .live import apply_with_feedback
            emit(apply_with_feedback(Google(),read(a.plan),a.journal));return
        if a.command=='verify':
            plan=read(a.plan);emit(verify(Document(read(a.input),plan['tabId']),plan));return
        if a.command in ('init-plan','init'):
            if a.command=='init':
                from .google import Google
                client=Google();resource=client.document(a.document_id)
            else:resource=read(a.input)
            doc=Document(resource,a.tab)
            if 'CGPS_DOC_'in doc.groups:raise ValueError('Document is already initialised')
            if any(n.startswith('Z_F')for n in doc.named):raise ValueError('Zotero fields require explicit migration first')
            ran=doc.locate(a.placeholder);anchor={'startIndex':0,'endIndex':1,'tabId':a.tab}
            requests=encode('CGPS_DOC_',{'schema':'cgps-citations/1','style':'elsevier-harvard','locale':'en-GB','numbering':'author-year'},anchor)+encode('CGPS_BIB_',{'currentOrder':[]},ran)
            plan={'documentId':doc.id,'tabId':doc.tab_id,'revisionId':doc.revision,'requests':requests,'kind':'initialisation-only'}
            if a.command=='init-plan':write(a.output,plan);return
            root=Path(a.workdir);root.mkdir(parents=True,exist_ok=True)
            key=digest(plan);write(root/(key+'.init-plan.json'),plan)
            if a.dry_run:emit(plan);return
            journal=root/(key+'.init-journal.json')
            if journal.exists():raise ValueError('Initialisation already attempted; inspect live state before retrying')
            write(journal,{'inflight':True,'revisionId':doc.revision})
            client.batch(doc.id,requests,doc.revision)
            after=Document(client.document(doc.id),doc.tab_id);reg=after.registry()
            if reg['records'] or reg['citations'] or after.text(reg['bibliography']['range'])[0]!=a.placeholder:
                raise ValueError('Initialisation readback mismatch')
            write(journal,{'complete':True});emit({'initialised':True});return
        if a.command=='plan':
            doc=Document(read(a.input),a.tab);reg=doc.registry()
            if a.style:reg['style']=resolve_style(a.style)
            write(a.output,build_plan(doc,reg,allow_suggestions=a.allow_citation_suggestions));return
        if a.command=='process-comments':
            document=Document(read(a.input),a.tab)
            plan,report=commands_plan(document,read(a.comments),reference_data=read(a.references)if a.references else (),export=Path(a.docx).read_bytes()if a.docx else None,allow_suggestions=a.allow_citation_suggestions)
            write(a.output,{'documentId':document.id,'plan':plan,'report':report});emit(report);return
        if a.command=='run':
            if a.watch is not None and a.watch<30:raise ValueError('Polling interval must be at least 30 seconds')
            from .google import Google
            from .live import run_once
            client=Google()
            while True:
                emit(run_once(client,a.document_id,a.tab,a.workdir,
                              reference_data=read(a.references)if a.references else (),
                              dry_run=a.dry_run,allow_suggestions=a.allow_citation_suggestions))
                if a.watch is None:break
                time.sleep(a.watch)
    except (ValueError,OSError,RuntimeError,subprocess.SubprocessError)as error:
        print('citegoblin: '+str(error),file=sys.stderr);raise SystemExit(2)


if __name__=='__main__':main()
