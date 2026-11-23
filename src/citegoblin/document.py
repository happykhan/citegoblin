"""Google Docs JSON adapter. No network calls and no guessed citation detection."""
import json
import re

MARKER = re.compile(r'^(CGPS_REF_r[0-9a-f]{16}_|CGPS_CITE_c[A-Za-z0-9]{6}_|CGPS_BIB_|CGPS_DOC_)')


def units(s):
    return len(s.encode('utf-16-le')) // 2


def slice_units(s, start, end):
    return s.encode('utf-16-le')[start*2:end*2].decode('utf-16-le')


def encode(prefix, value, ran):
    raw = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
    size = 255-units(prefix)-3
    if size < 2:
        raise ValueError('Marker prefix too long')
    chunks, part = [], ''
    for char in raw:
        if units(part+char) > size:
            chunks.append(part)
            part = ''
        part += char
    if part:
        chunks.append(part)
    if len(chunks) > 1000:
        raise ValueError('Metadata exceeds marker capacity')
    return [{'createNamedRange': {'name': prefix+f'{i:03}'+chunk, 'range': ran}}
            for i, chunk in enumerate(chunks)]


def decode(names, prefix):
    ns = sorted(names)
    if [n[len(prefix):len(prefix)+3] for n in ns] != [f'{i:03}' for i in range(len(ns))]:
        raise ValueError('Missing or duplicated marker chunks: '+prefix)
    return json.loads(''.join(n[len(prefix)+3:] for n in ns))


def select_tab(doc, tab_id):
    doc = doc.get('structuredContent', doc)
    def walk(tabs):
        for tab in tabs:
            yield tab
            yield from walk(tab.get('childTabs', []))
    for tab in walk(doc.get('tabs', [])):
        if tab.get('tabId', tab.get('tabProperties', {}).get('tabId')) == tab_id:
            return doc, tab.get('documentTab', tab)
    raise ValueError('Explicit target tab not found')


class Document:
    def __init__(self, resource, tab_id):
        self.raw, self.tab = select_tab(resource, tab_id)
        self.id = self.raw['documentId']
        self.revision = self.raw['revisionId']
        self.tab_id = tab_id
        self.named = self.tab.get('namedRanges') or {}
        self.groups, self.runs, self.paragraphs = {}, [], []
        self.tables = self.images = 0
        for name in self.named:
            match = MARKER.match(name)
            if match:
                self.groups.setdefault(match[0], []).append(name)
        self._walk(self.tab['body']['content'])
        self.runs.sort(key=lambda r: r['startIndex'])
        # Footnote/header citations are not silently dropped.
        for container in ('footnotes', 'headers', 'footers'):
            if 'CGPS_CITE_' in json.dumps(self.tab.get(container) or {}):
                raise ValueError('Non-body citation fields are not supported yet')

    def _walk(self, elements):
        for e in elements:
            if 'paragraph' in e:
                runs = [r for r in e['paragraph'].get('elements', []) if 'textRun' in r]
                self.runs.extend(runs)
                self.paragraphs.append({'start': e['startIndex'], 'end': e['endIndex'], 'runs': runs})
                self.images += sum('inlineObjectElement' in r for r in e['paragraph'].get('elements', []))
            if 'table' in e:
                self.tables += 1
                for row in e['table']['tableRows']:
                    for cell in row['tableCells']:
                        self._walk(cell['content'])

    def value(self, prefix):
        return decode(self.groups[prefix], prefix)

    def ids(self, prefix):
        ids = []
        for name in self.groups[prefix]:
            rows = self.named[name]['namedRanges']
            if len(rows) != 1:
                raise ValueError('Duplicated named range: '+prefix)
            ids.append(rows[0]['namedRangeId'])
        return ids

    def range(self, prefix):
        ranges = [r for name in self.groups[prefix] for n in self.named[name]['namedRanges'] for r in n['ranges']]
        if not ranges or any(r.get('segmentId') or r.get('startIndex', 0) != ranges[0].get('startIndex', 0)
                             or r['endIndex'] != ranges[0]['endIndex'] for r in ranges):
            raise ValueError('Fragmented marker: '+prefix)
        return {'startIndex': ranges[0].get('startIndex', 0), 'endIndex': ranges[0]['endIndex'], 'tabId': self.tab_id}

    def text(self, ran):
        start, end = ran['startIndex'], ran['endIndex']
        out, pos, pending, deleted = '', start, False, False
        for run in self.runs:
            a, b = max(start, run['startIndex']), min(end, run['endIndex'])
            if b <= a:
                continue
            if a != pos:
                raise ValueError('Range crosses non-text structure')
            tr = run['textRun']
            out += slice_units(tr['content'], a-run['startIndex'], b-run['startIndex'])
            pos = b
            pending |= bool(tr.get('suggestedInsertionIds') or tr.get('suggestedDeletionIds'))
            deleted |= bool(tr.get('suggestedDeletionIds'))
        if pos != end:
            raise ValueError('Incomplete text range')
        return out, pending, deleted

    def style_at(self, index):
        return next((dict(r['textRun'].get('textStyle', {})) for r in self.runs
                     if r['startIndex'] <= index < r['endIndex']), {})

    def locate(self, quote, occurrence=None):
        """Exact matches only, excluding suggested deletions. No semantic inference."""
        if not quote:
            raise ValueError('Select non-empty text for a citation')
        hits = []
        for para in self.paragraphs:
            text, positions = '', []
            for run in para['runs']:
                if run['textRun'].get('suggestedDeletionIds'):
                    continue
                position = run['startIndex']
                for char in run['textRun']['content']:
                    text += char
                    positions.append(position)
                    position += units(char)
            offset = 0
            while (at := text.find(quote, offset)) >= 0:
                a = positions[at]
                b = positions[at+len(quote)-1]+units(quote[-1])
                self.text({'startIndex': a, 'endIndex': b})
                hits.append({'startIndex': a, 'endIndex': b, 'tabId': self.tab_id})
                offset = at+len(quote)
        if occurrence is not None:
            if occurrence < 0 or occurrence >= len(hits):
                raise ValueError('Requested quote occurrence does not exist')
            return hits[occurrence]
        if len(hits) != 1:
            raise ValueError(f'Quote has {len(hits)} matches; supply a precise quote or occurrence')
        return hits[0]

    def registry(self):
        if 'CGPS_DOC_' not in self.groups or 'CGPS_BIB_' not in self.groups:
            raise ValueError('No independent citation register; migration requires an explicit mapping')
        config = self.value('CGPS_DOC_')
        if config.get('schema') != 'cgps-citations/1':
            raise ValueError('Unsupported citation schema')
        bib = self.value('CGPS_BIB_')
        records, citations = {}, []
        for prefix in self.groups:
            if prefix.startswith('CGPS_REF_'):
                record = self.value(prefix)
                if prefix != 'CGPS_REF_'+record['id']+'_':
                    raise ValueError('Reference ID does not match marker')
                records[record['id']] = record
            elif prefix.startswith('CGPS_CITE_'):
                ran = self.range(prefix)
                text, pending, deleted = self.text(ran)
                if deleted:
                    raise ValueError('Citation is inside a suggested deletion; author decision required')
                citations.append({'id': prefix[10:-1], **self.value(prefix), 'text': text,
                                  'range': ran, 'pendingSuggestion': pending})
        citations.sort(key=lambda c: c['range']['startIndex'])
        for a, b in zip(citations, citations[1:]):
            if a['range']['endIndex'] > b['range']['startIndex']:
                raise ValueError('Overlapping citation markers')
        for citation in citations:
            for item in citation['items']:
                if item['id'] not in records:
                    raise ValueError('Missing reference: '+item['id'])
        return {**config, 'documentId': self.id, 'revisionId': self.revision, 'tabId': self.tab_id,
                'records': records, 'citations': citations, 'bibliography': {**bib, 'range': self.range('CGPS_BIB_')}}

    def unchanged_text(self, exclusions):
        """Comparable paragraph/cell text outside explicitly authorised edit ranges."""
        output = []
        for para in self.paragraphs:
            text = ''
            for run in para['runs']:
                start, end = run['startIndex'], run['endIndex']
                for ran in sorted(exclusions, key=lambda r: r['startIndex']):
                    if ran['startIndex'] >= end or ran['endIndex'] <= start:
                        continue
                    if ran['startIndex'] > start:
                        text += slice_units(run['textRun']['content'], start-run['startIndex'], ran['startIndex']-run['startIndex'])
                    start = max(start, ran['endIndex'])
                if start < end:
                    text += slice_units(run['textRun']['content'], start-run['startIndex'], end-run['startIndex'])
            # Citation/bibliography replacement may add/remove empty bibliography paragraphs.
            if text:
                output.append(text)
        return output
