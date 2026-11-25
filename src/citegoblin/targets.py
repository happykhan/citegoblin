"""Resolve a native Google Docs link or ID and an explicit or unambiguous tab."""
import re
from urllib.parse import urlsplit,parse_qs
from .document import Document


def document_target(source,tab=None):
    source=source.strip();url_tab=None
    if re.fullmatch(r'[A-Za-z0-9_-]{10,}',source):key=source
    else:
        url=urlsplit(source)
        if url.scheme!='https' or url.netloc!='docs.google.com':
            raise ValueError('Use a Google Docs URL (https://docs.google.com/document/d/...) or its document ID')
        match=re.fullmatch(r'/document/(?:u/\d+/)?d/([A-Za-z0-9_-]{10,})(?:/(?:edit|preview|view))?/?',url.path)
        if not match:raise ValueError('This is not a native Google Docs document link')
        key=match[1]
        tabs=parse_qs(url.query).get('tab',[])
        if len(tabs)>1:raise ValueError('The URL contains multiple tab values; use a link to one document tab')
        url_tab=tabs[0] if tabs else None
    chosen=tab if tab is not None else url_tab
    if chosen is not None and not re.fullmatch(r'[A-Za-z0-9_.-]+',chosen):raise ValueError('Invalid document tab ID')
    return key,chosen


def document_tab(resource,tab=None,section="main"):
    if tab is not None:return Document(resource,tab,section)
    resource=resource.get('structuredContent',resource)
    def walk(tabs):
        for value in tabs:
            yield value
            yield from walk(value.get('childTabs',[]))
    tabs=list(walk(resource.get('tabs',[])))
    if len(tabs)!=1:
        choices=', '.join(t.get('tabId',t.get('tabProperties',{}).get('tabId','?'))for t in tabs)
        raise ValueError('Document has multiple tabs or no accessible tab. Open the intended tab and copy its URL, or supply --tab TAB_ID. Available tabs: '+choices)
    return Document(resource,tabs[0].get('tabId',tabs[0].get('tabProperties',{}).get('tabId')),section)
