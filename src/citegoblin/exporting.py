"""Portable bibliography exports from the managed CSL reference register."""
import html
from html.parser import HTMLParser
import re

FORMATS = ('bibtex', 'ris', 'endnote')


class _Plain(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts = []
    def handle_data(self, value): self.parts.append(value)


def text(value):
    if value is None: return ''
    if isinstance(value, list): return '; '.join(text(v) for v in value)
    parser = _Plain(); parser.feed(str(value))
    return ' '.join(''.join(parser.parts).split())


def latex(value):
    replacements = {'\\':r'\textbackslash{}', '{':r'\{', '}':r'\}', '&':r'\&', '%':r'\%',
                    '$':r'\$', '#':r'\#', '_':r'\_', '~':r'\textasciitilde{}', '^':r'\textasciicircum{}'}
    return ''.join(replacements.get(c, c) for c in text(value))


def name(person, *, bibtex=False):
    if person.get('literal'):
        return '{'+latex(person['literal'])+'}' if bibtex else text(person['literal']).rstrip(',')+','
    family = ' '.join(text(person.get(k)) for k in ('non-dropping-particle','family') if person.get(k))
    given = text(person.get('given')); suffix = text(person.get('suffix'))
    if bibtex:
        return ', '.join(latex(v) for v in (family,suffix,given) if v)
    return ', '.join(v for v in (family, given, suffix) if v)


def date_parts(csl):
    return (csl.get('issued',{}).get('date-parts') or [[]])[0]


def year(csl):
    parts = date_parts(csl)
    return str(parts[0]) if parts else ''


def pages(csl):
    value = text(csl.get('page')).replace('–','-').replace('—','-')
    match = re.fullmatch(r'(\d+)-(\d+)', value)
    if match:
        start, end = match.groups()
        if len(end)<len(start): end=start[:-len(end)]+end
        return start, end
    return value, ''


def records(registry, cited_only=False):
    if not isinstance(registry,dict) or not isinstance(registry.get('records'),dict):
        raise ValueError('Export needs a CiteGoblin reference register or managed Google document')
    refs=registry['records']
    cited={i['id'] for c in registry.get('citations',[]) for i in c['items']}
    if cited_only and 'citations' not in registry:
        raise ValueError('--cited-only requires the register citation mappings')
    if not cited.issubset(refs): raise ValueError('Citation refers to a missing reference')
    order=list(dict.fromkeys([*(registry.get('bibliography',{}).get('currentOrder') or []),*refs]))
    selected=[]
    for key in order:
        if key not in refs or (cited_only and key not in cited): continue
        from .metadata_cleanup import effective_csl
        ref=refs[key];csl=effective_csl(ref) if isinstance(ref.get('csl'),dict) else None
        if not re.fullmatch(r'[A-Za-z0-9_-]+',key): raise ValueError('Reference ID cannot be exported as a citation key')
        if not isinstance(csl,dict) or not text(csl.get('title')): raise ValueError('Reference has no title: '+key)
        selected.append((key,dict(csl,DOI=csl.get('DOI') or ref.get('doi'),PMID=csl.get('PMID') or ref.get('pmid'))))
    return selected


def bibtex(key,csl):
    kind={'article-journal':'article','article-magazine':'article','article-newspaper':'article',
          'book':'book','chapter':'incollection','paper-conference':'inproceedings','report':'techreport',
          'thesis':'phdthesis'}.get(csl.get('type'),'misc')
    if csl.get('type')=='thesis' and 'master' in text(csl.get('genre')).lower():kind='mastersthesis'
    fields=[]
    def add(field,value,raw=False):
        if value: fields.append('  '+field+' = {'+(value if raw else latex(value))+'}')
    for field in ('author','editor'):
        add(field,' and '.join(name(p,bibtex=True) for p in csl.get(field,[])),raw=True)
    # Extra braces retain case in tool names, gene symbols and abbreviations.
    add('title','{'+latex(csl['title'])+'}',raw=True)
    container='journal' if kind=='article' else 'booktitle'
    add(container,csl.get('container-title'))
    add('year',year(csl)); add('volume',csl.get('volume'));add('number',csl.get('issue'))
    start,end=pages(csl);add('pages',start+'--'+end if end else start)
    publisher='institution' if kind=='techreport' else 'school' if kind.endswith('thesis') else 'publisher'
    add(publisher,csl.get('publisher'));add('address',csl.get('publisher-place'))
    for field in ('edition','DOI','URL','ISBN','ISSN','PMID'):
        add(field.lower(),csl.get(field))
    if csl.get('type') in ('webpage','post-weblog','software','dataset'):add('howpublished',csl.get('genre') or csl['type'])
    return '@'+kind+'{'+key+',\n'+',\n'.join(fields)+'\n}\n'


def ris(key,csl):
    kind={'article-journal':'JOUR','article-magazine':'MGZN','article-newspaper':'NEWS','book':'BOOK',
          'chapter':'CHAP','paper-conference':'CPAPER','report':'RPRT','thesis':'THES',
          'webpage':'ELEC','post-weblog':'BLOG','software':'COMP','dataset':'DATA'}.get(csl.get('type'),'GEN')
    lines=['TY  - '+kind,'ID  - '+key]
    def add(tag,value):
        if value:lines.append(tag+'  - '+text(value))
    for author in csl.get('author',[]):add('AU',name(author))
    for editor in csl.get('editor',[]):add('ED',name(editor))
    add('TI',csl['title']);add('T2',csl.get('container-title'))
    add('PY',year(csl))
    parts=date_parts(csl)
    if len(parts)>1:add('DA','/'.join(str(p).zfill(2) for p in parts))
    for tag,field in [('VL','volume'),('IS','issue'),('PB','publisher'),('CY','publisher-place'),
                      ('ET','edition'),('DO','DOI'),('UR','URL'),('LA','language'),('AB','abstract')]:add(tag,csl.get(field))
    start,end=pages(csl);add('SP',start);add('EP',end)
    for field in ('ISBN','ISSN'):
        values=csl.get(field) or []
        for value in values if isinstance(values,list) else [values]:add('SN',value)
    if csl.get('PMID'):add('AN',csl['PMID']);add('DB','PubMed')
    lines.append('ER  - ')
    return '\n'.join(lines)+'\n'


def endnote(key,csl):
    kind={'article-journal':'Journal Article','article-magazine':'Magazine Article','article-newspaper':'Newspaper Article',
          'book':'Book','chapter':'Book Section','paper-conference':'Conference Paper','report':'Report',
          'thesis':'Thesis','webpage':'Web Page','post-weblog':'Blog','software':'Computer Program',
          'dataset':'Dataset'}.get(csl.get('type'),'Generic')
    lines=['%0 '+kind,'%F '+key]
    def add(tag,value):
        if value:lines.append('%'+tag+' '+text(value))
    for author in csl.get('author',[]):add('A',name(author))
    for editor in csl.get('editor',[]):add('E',name(editor))
    add('T',csl['title']);add('D',year(csl))
    add('J' if kind in ('Journal Article','Magazine Article','Newspaper Article') else 'B',csl.get('container-title'))
    for tag,field in [('V','volume'),('N','issue'),('I','publisher'),('C','publisher-place'),('7','edition'),
                      ('R','DOI'),('U','URL'),('G','language'),('X','abstract'),('9','genre')]:add(tag,csl.get(field))
    start,end=pages(csl);add('P',start+'-'+end if end else start)
    for field in ('ISBN','ISSN'):
        values=csl.get(field) or []
        for value in values if isinstance(values,list) else [values]:add('@',value)
    if csl.get('PMID'):add('M',csl['PMID']);add('~','PubMed')
    return '\n'.join(lines)+'\n'


def export_references(registry, format_name, *, cited_only=False):
    if format_name not in FORMATS: raise ValueError('Unsupported export format')
    formatter={'bibtex':bibtex,'ris':ris,'endnote':endnote}[format_name]
    return '\n'.join(formatter(key,csl) for key,csl in records(registry,cited_only))
