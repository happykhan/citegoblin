"""A small command language. Comment location and source are user instructions."""
import hashlib
import json
import re
from html.parser import HTMLParser
from io import BytesIO
from zipfile import ZipFile
from xml.etree import ElementTree as ET
from .references import identifier
from .styles import resolve_style


class Plain(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts = []
    def handle_data(self, data): self.parts.append(data)


def plain(value):
    parser = Plain(); parser.feed(value); return ''.join(parser.parts)


def fingerprint(comment):
    return hashlib.sha256(json.dumps([comment.get('content'),comment.get('anchor')],ensure_ascii=False).encode()).hexdigest()


SECTION = r'[a-z][a-z0-9-]{0,23}'


def section_name(name):
    name = name.lower()
    if not re.fullmatch(SECTION, name):
        raise ValueError('A section tag must start with a letter and contain at most 24 letters, digits or hyphens')
    return name


def split_section(content, default='main'):
    """Return the section and the command without its routing tag."""
    text = content.strip()
    location = re.fullmatch(r'(@bib|@references)\s+(' + SECTION + r')', text, re.I)
    if location:
        return section_name(location[2]), location[1].lower()
    tagged = re.fullmatch(r'(@cite|@style|@refresh)\s+\[(' + SECTION + r')\](?:\s+(.*))?', text, re.I | re.S)
    if tagged:
        return section_name(tagged[2]), (tagged[1].lower() + ' ' + (tagged[3] or '')).strip()
    short = re.fullmatch(r'@cite\s+(' + SECTION + r')\s+((?:10\.\d|https?://|doi:|pmid:|ref:|url:).*|\d+)',
                         text, re.I | re.S)
    if short:
        return section_name(short[1]), '@cite ' + short[2]
    return default, text


def is_bibliography_command(content):
    return split_section(content)[1] in ('@bib', '@references')


def parse(comment):
    _, text = split_section(comment.get('content', ''))
    if re.match(r'^@style\s+',text):
        return {'kind':'style','style':resolve_style(re.sub(r'^@style\s+','',text).strip())}
    if text in ('@bib','@references'):return {'kind':'bibliography'}
    if text == '@refresh replace-references':
        return {'kind': 'refresh', 'replaceEditedReferences': True}
    if text == '@refresh': return {'kind':'refresh'}
    if re.match(r'^@cite\s+', text):
        source = re.sub(r'^@cite\s+', '', text).strip()
        if source.startswith(('ref:','url:')):
            return {'kind':'cite','source':source}
        return {'kind':'cite',**identifier(source)}
    if text.startswith(('@cite','@style','@refresh','@bib','@references')):
        raise ValueError('Malformed CiteGoblin command')
    return None


def docx_anchor(comment, content):
    """Recover selected text from a Docs DOCX export; refuse ambiguous thread matches."""
    ns = {'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    w = '{'+ns['w']+'}'
    with ZipFile(BytesIO(content)) as archive:
        if 'word/comments.xml' not in archive.namelist(): raise ValueError('Export has no comment anchors')
        comments = ET.fromstring(archive.read('word/comments.xml'))
        matches = [c for c in comments if ''.join(c.itertext()).strip() == comment['content'].strip()]
        if len(matches)>1:
            author=(comment.get('author') or {}).get('displayName')
            stamp=comment.get('createdTime','')[:19]
            matches=[c for c in matches if c.get(w+'author')==author and c.get(w+'date','')[:19]==stamp]
        if len(matches)!=1: raise ValueError('Cannot uniquely match exported comment')
        key=matches[0].get(w+'id'); active=False; text=[]
        for node in ET.fromstring(archive.read('word/document.xml')).iter():
            if node.tag==w+'commentRangeStart' and node.get(w+'id')==key: active=True
            elif node.tag==w+'commentRangeEnd' and node.get(w+'id')==key: active=False
            elif node.tag==w+'t' and active: text.append(node.text or '')
        quote=''.join(text)
        if not quote: raise ValueError('Comment is not attached to selected text')
        return quote


def anchor_quote(comment, export=None):
    quoted=comment.get('quotedFileContent') or {}
    quote=quoted.get('value')
    if quote: return plain(quote) if quoted.get('mimeType')=='text/html' else quote
    if export is None: raise ValueError('Comment quote unavailable; a DOCX export is required to recover its anchor')
    return docx_anchor(comment,export)
