"""CSL styles shared with Zotero, with deterministic local installations."""
import json
import re
import urllib.error
import urllib.request
from xml.etree import ElementTree as ET
from .auth import config_dir, private_write
from pathlib import Path

FORMATTER=Path(__file__).parent/'formatter'
UPSTREAM='7fa488bd2f765eb161e93c7963838ee2c9c17fe5'
NS={'c':'http://purl.org/net/xbiblio/csl'}
ALIASES={'author-year':'elsevier-harvard','harvard':'elsevier-harvard','vancouver':'nlm-citation-sequence',
         'apa7':'apa','apa 7':'apa','chicago':'chicago-author-date','chicago author-date':'chicago-author-date',
         'mla':'modern-language-association'}


def style_id(value):
    value=value.strip().lower()
    value=ALIASES.get(value,value)
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,120}',value):
        raise ValueError('Use a CSL style ID, such as ieee, apa or chicago-author-date')
    return value


def inspect_style(xml):
    try:root=ET.fromstring(xml)
    except ET.ParseError as error:raise ValueError('Invalid CSL style XML') from error
    if root.tag!='{'+NS['c']+'}style':raise ValueError('Not a CSL style')
    parent=root.find('c:info/c:link[@rel="independent-parent"]',NS)
    info={'title':root.findtext('c:info/c:title',default='',namespaces=NS),
          'parent':parent.get('href') if parent is not None else None}
    category=root.find('c:info/c:category[@citation-format]',NS)
    info['citationFormat']=category.get('citation-format') if category is not None else None
    if info['parent']:return info
    if root.get('class')!='in-text' or root.find('c:bibliography',NS) is None:
        raise ValueError('This style requires footnotes or has no bibliography; only in-text styles are supported')
    return info


def installed_styles():
    result={}
    for folder in (FORMATTER,config_dir()/'styles'):
        if not folder.exists():continue
        for path in sorted(folder.glob('*.csl')):
            try:info=inspect_style(path.read_text())
            except ValueError:continue
            if not info['parent'] and (folder==FORMATTER or path.stem not in result):
                result[path.stem]=dict(info,id=path.stem,path=path)
    return result


def resolve_style(value):
    key=style_id(value)
    if key not in installed_styles():
        raise ValueError(f"Style '{key}' is not installed. Run: citegoblin styles install {key}")
    return key


def load_style(value):
    key=resolve_style(value)
    info=installed_styles()[key]
    return info,info['path'].read_text()


def download_style(key):
    key=style_id(key)
    url=f'https://raw.githubusercontent.com/citation-style-language/styles/{UPSTREAM}/{key}.csl'
    try:
        with urllib.request.urlopen(url,timeout=25) as response:raw=response.read(2_000_001)
    except urllib.error.HTTPError as error:
        if error.code==404:raise ValueError('No CSL style with that ID in the supported upstream snapshot: '+key) from error
        raise
    if len(raw)>2_000_000:raise ValueError('CSL style exceeds size limit')
    return raw.decode('utf-8')


def install_style(value,*,fetch=download_style):
    key=style_id(value)
    if key in installed_styles():
        info=installed_styles()[key];return {k:v for k,v in info.items() if k!='path'}
    current=key;visited=set();requested_title=None
    while True:
        if current in visited or len(visited)>5:raise ValueError('Circular or excessive CSL parent chain')
        visited.add(current);xml=fetch(current);info=inspect_style(xml)
        if requested_title is None:requested_title=info['title']
        if not info['parent']:break
        match=re.fullmatch(r'https?://www\.zotero\.org/styles/([a-z0-9-]+)',info['parent'])
        if not match:raise ValueError('Style parent is not an official Zotero CSL style ID')
        current=match[1]
    folder=config_dir()/'styles'
    private_write(folder/(key+'.csl'),xml)
    metadata={'id':key,'title':requested_title,'resolvedParent':current if current!=key else None,
              'sourceCommit':UPSTREAM,'citationFormat':info['citationFormat']}
    private_write(folder/(key+'.json'),json.dumps(metadata,indent=2))
    return metadata
