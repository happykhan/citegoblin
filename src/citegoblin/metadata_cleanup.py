"""Reversible reference-title corrections; imported CSL fields stay intact."""
import copy
import html
from html.parser import HTMLParser
import re
from .binomials import clean_reference_text

# Explicit terms, never a guess that any short capitalised word is an acronym.
TERMS=('DNA RNA mRNA rRNA tRNA PCR qPCR RT-PCR WGS AMR AST SNP SNPs MLST cgMLST wgMLST '
       'UK USA US EU WHO HIV AIDS MRSA MSSA KPC NDM OXA-48 OXA-48-like COVID-19 SARS-CoV-2 '
       'NCBI ENA INSDC ECDC CDC NHS ICU QC QA').split()


class _Title(HTMLParser):
    def __init__(self):super().__init__(convert_charrefs=True);self.parts=[];self.stack=[]
    def handle_data(self,value):self.parts.append(('text',value))
    def handle_starttag(self,tag,attrs):
        mapped={'em':'i','strong':'b','jats:italic':'i','jats:bold':'b','jats:sup':'sup','jats:sub':'sub'}.get(tag,tag)
        if mapped in ('i','b','sup','sub'):
            self.parts.append(('tag','<'+mapped+'>'));self.stack.append((tag,mapped))
        elif tag=='span' and ('class','nocase')in attrs:
            self.parts.append(('tag','<span class="nocase">'));self.stack.append((tag,'span'))
        elif tag in ('br','p','div'):self.parts.append(('text',' '))
    def handle_endtag(self,tag):
        if self.stack and self.stack[-1][0]==tag:self.parts.append(('tag','</'+self.stack.pop()[1]+'>'))
        elif tag in ('p','div'):self.parts.append(('text',' '))


def effective_csl(reference):
    return dict(reference['csl'],**reference.get('cslOverrides',{}))


def clean_title(value,names,*,protected=(),abbreviations=False,normalise=True):
    parser=_Title();parser.feed(value);parser.close()
    for _,tag in reversed(parser.stack):parser.parts.append(('tag','</'+tag+'>'))
    plain=''.join(v for kind,v in parser.parts if kind=='text')
    allcaps=normalise and len(re.findall(r'[A-Za-z]',plain))>1 and plain.isupper() and len(plain.lower())==len(plain)
    terms={term.casefold():term for term in (*TERMS,*names,*protected)}
    pattern=re.compile(r'(?<![\w-])(?:'+'|'.join(re.escape(t)for t in sorted(terms,key=len,reverse=True))+r')(?![\w-])',re.I)
    result=[];capitalised=False;italic=0;nocase=0
    for kind,value in parser.parts:
        if kind=='tag':
            if value=='<i>':italic+=1
            elif value=='</i>':italic-=1
            elif value=='<span class="nocase">':nocase+=1
            elif value=='</span>':nocase-=1
            result.append(value);continue
        if normalise:value=re.sub(r'\s+',' ',value)
        patches=[]
        for match in pattern.finditer(value):patches.append((match.start(),match.end(),terms[match[0].casefold()]))
        if allcaps:
            lowered=value.lower()
            if not capitalised:
                first=re.search(r'[^\W\d_]',lowered)
                if first:lowered=lowered[:first.start()]+lowered[first.start()].upper()+lowered[first.end():];capitalised=True
            value=lowered
            for start,end,term in reversed(patches):value=value[:start]+term+value[end:]
        # Match names before escaping so offsets refer to the actual text.
        value,matches,_=clean_reference_text(value,names,abbreviations=abbreviations)
        spans=[]
        for match in matches:
            raw=value.encode('utf-16-le')
            start=len(raw[:match['start']*2].decode('utf-16-le'));end=len(raw[:match['end']*2].decode('utf-16-le'))
            marked=html.escape(value[start:end],quote=False)
            if not nocase:marked='<span class="nocase">'+marked+'</span>'
            if not italic:marked='<i>'+marked+'</i>'
            spans.append((start,end,marked))
        # Protect explicit terms from CSL title-case conversion as well.
        for match in pattern.finditer(value):
            if any(match.start()<end and match.end()>start for start,end,_ in spans):continue
            term=terms[match[0].casefold()]
            if not nocase and match[0]==term:spans.append((match.start(),match.end(),'<span class="nocase">'+html.escape(term,quote=False)+'</span>'))
        cursor=0
        for start,end,replacement in sorted(spans):
            result.append(html.escape(value[cursor:start],quote=False));result.append(replacement);cursor=end
        result.append(html.escape(value[cursor:],quote=False))
    return ''.join(result).strip(),allcaps


def clean_metadata(registry,names,*,protected=(),abbreviations=False,normalise=True,restore=False):
    changes=[];warnings=[]
    for key,reference in registry['records'].items():
        before=effective_csl(reference);overrides=copy.deepcopy(reference.get('cslOverrides',{}))
        if restore:overrides={}
        else:
            for field in ('title','title-short'):
                value=before.get(field)
                if not isinstance(value,str):continue
                cleaned,allcaps=clean_title(value,names,protected=protected,abbreviations=abbreviations,normalise=normalise)
                if cleaned!=reference['csl'].get(field):overrides[field]=cleaned
                else:overrides.pop(field,None)
                if allcaps:warnings.append({'referenceId':key,'field':field,'reason':'All-capitals title converted to sentence case. Check proper nouns and acronyms; use --preserve for additional terms.'})
        if overrides:reference['cslOverrides']=overrides
        else:reference.pop('cslOverrides',None)
        after=effective_csl(reference)
        for field in set(before)|set(after):
            if before.get(field)!=after.get(field):changes.append({'referenceId':key,'field':field,'before':before.get(field),'after':after.get(field)})
    return changes,warnings
