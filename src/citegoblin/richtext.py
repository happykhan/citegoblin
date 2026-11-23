"""Map CSL's inline HTML formatting onto its plain-text UTF-16 offsets."""
from html.parser import HTMLParser
from .document import units


class InlineParser(HTMLParser):
    def __init__(self):
        super().__init__();self.stack=[];self.characters=[]
    def handle_starttag(self,tag,attrs):
        style=dict(self.stack[-1][1])if self.stack else {}
        if tag in ('i','em'):style['italic']=True
        if tag in ('b','strong'):style['bold']=True
        if tag=='sup':style['baselineOffset']='SUPERSCRIPT'
        if tag=='sub':style['baselineOffset']='SUBSCRIPT'
        css=dict(attrs).get('style','').replace(' ','')
        if 'font-variant:small-caps' in css:style['smallCaps']=True
        if tag not in ('br','img','hr'):self.stack.append((tag,style))
    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,-1,-1):
            if self.stack[i][0]==tag:self.stack=self.stack[:i];break
    def handle_data(self,value):
        style=self.stack[-1][1] if self.stack else {}
        self.characters.extend((c,dict(style))for c in value)


def inline_styles(html,plain):
    parser=InlineParser();parser.feed(html)
    source=[(c,s)for c,s in parser.characters if not c.isspace()]
    target=[];offset=0
    for c in plain:
        if not c.isspace():target.append((c,offset,offset+units(c)))
        offset+=units(c)
    if ''.join(c for c,_ in source)!=''.join(c for c,_,_ in target):
        raise ValueError('CSL rich text differs from plain-text output; cannot safely map formatting')
    spans=[]
    for (_,style),(_,start,end)in zip(source,target):
        if not style:continue
        if spans and spans[-1]['style']==style and plain.encode('utf-16-le')[spans[-1]['end']*2:start*2].decode('utf-16-le').isspace():
            spans[-1]['end']=end
        elif spans and spans[-1]['style']==style and spans[-1]['end']==start:
            spans[-1]['end']=end
        else:spans.append({'start':start,'end':end,'style':style})
    return spans


def styling_matches(document,ran,spans):
    for span in spans:
        start=ran['startIndex']+span['start'];end=ran['startIndex']+span['end']
        for run in document.runs:
            if run['endIndex']<=start or run['startIndex']>=end:continue
            actual=run['textRun'].get('textStyle',{})
            if any(actual.get(key,False if isinstance(value,bool)else None)!=value for key,value in span['style'].items()):return False
    return True
