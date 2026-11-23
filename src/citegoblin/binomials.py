"""Scientific-name typography within rendered reference text only."""
import json
from pathlib import Path
import re
from .document import units

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


def clean_reference_text(text,names,*,abbreviations=False):
    approved=[]
    for name in names:
        match=re.fullmatch(r'([A-Z][a-z-]+) ([a-z][a-z-]+)',name)
        if not match:raise ValueError('Invalid canonical binomial: '+name)
        approved.append((match[1],match[2]))
    if not approved:raise ValueError('The approved-name list is empty')
    terms='|'.join(re.escape(g)+r'(?P<gap'+str(i)+r'>[ \t\u00a0]+)'+re.escape(s)for i,(g,s)in enumerate(approved))
    full=re.compile(r'(?<![\w-])(?:'+terms+r')(?![\w-])',re.I)
    short=re.compile(r'(?<![\w-])([A-Za-z])\.([ \t\u00a0]+)([A-Za-z][A-Za-z-]+)(?![\w-])')
    output=[];changes=[];skipped=[];offset=0
    for line in text.splitlines(keepends=True):
        seen={};patches=[]
        matches=[(m,False)for m in full.finditer(line)]
        if abbreviations:matches.extend((m,True)for m in short.finditer(line))
        urls=[m.span()for m in re.finditer(r'https?://\S+',line)]
        for match,abbreviated in sorted(matches,key=lambda pair:pair[0].start()):
            if abbreviated and not any(g[0].lower()==match[1].lower()and s==match[3].lower()for g,s in approved):continue
            if any(match.start()<end and match.end()>start for start,end in urls):continue
            if abbreviated:
                candidates={g for g,s in approved if g[0].lower()==match[1].lower()and s==match[3].lower()and g in seen.get(s,set())}
                if len(candidates)!=1:
                    skipped.append({'text':match[0],'reason':'abbreviated genus lacks unique full-name context in this reference'});continue
                replacement=match[1].upper()+'.'+match[2]+match[3].lower()
            else:
                i=next(i for i in range(len(approved))if match.group('gap'+str(i))is not None)
                genus,species=approved[i];seen.setdefault(species,set()).add(genus)
                replacement=genus+match.group('gap'+str(i))+species
            if units(replacement)!=units(match[0]):raise ValueError('Name cleanup would change UTF-16 length')
            start=offset+units(line[:match.start()]);end=start+units(match[0])
            changes.append({'before':match[0],'after':replacement,'start':start,'end':end,'italic':True,'smallCaps':False})
            patches.append((match.start(),match.end(),replacement))
        for start,end,replacement in reversed(patches):line=line[:start]+replacement+line[end:]
        output.append(line);offset+=units(line)
    return ''.join(output),changes,skipped


def overlay_styles(spans,changes):
    overlays=[{'start':c['start'],'end':c['end'],'style':{'italic':True,'smallCaps':False}}for c in changes]
    all_spans=list(spans)+overlays
    bounds=sorted({position for span in all_spans for position in (span['start'],span['end'])})
    result=[]
    for start,end in zip(bounds,bounds[1:]):
        style={}
        for span in all_spans:
            if span['start']<=start and end<=span['end']:style.update(span['style'])
        if not style:continue
        if result and result[-1]['end']==start and result[-1]['style']==style:result[-1]['end']=end
        else:result.append({'start':start,'end':end,'style':style})
    return result
