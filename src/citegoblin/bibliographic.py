"""Resolve pasted author–year journal references through Crossref, without AI."""
import html
import json
import re
import urllib.parse
import urllib.request
from .references import lookup_doi, normal_doi, title_key


def clean(value):
    return ' '.join(html.unescape(re.sub('<[^>]+>', '', value)).replace('*', '').split())


def page_key(value):
    value = re.sub(r'\s+', '', value).replace('–', '-').replace('—', '-')
    match = re.fullmatch(r'(\d+)-(\d+)', value)
    if match and len(match[2]) < len(match[1]):
        return match[1] + '-' + match[1][:-len(match[2])] + match[2]
    return value


def parse_reference(value):
    value = clean(value)
    year = re.search(r'\(([12][0-9]{3})\)\s*\.\s*', value)
    if not year:
        raise ValueError('Unrecognised reference format; use Author, A. (Year). Title. Journal, volume(issue), pages, or supply a DOI/PMID')
    prefix, rest = value[:year.start()].strip(), value[year.end():].strip()
    authors = []
    name = re.compile(r'([^,;&]+?),\s*((?:[^\W\d_]\.\s*)+)', re.UNICODE)
    end = 0
    for match in name.finditer(prefix):
        if prefix[end:match.start()].strip(' ,;&'):
            raise ValueError('Cannot read the reference author list; supply a DOI/PMID')
        authors.append({'family':clean(match[1]),'initials':re.sub(r'\W', '', match[2]).lower()})
        end = match.end()
    if not authors or prefix[end:].strip(' ,;&'):
        raise ValueError('Cannot read the reference author list; supply a DOI/PMID')
    # The journal/volume/page tail disambiguates sentence punctuation in titles.
    tail = re.fullmatch(r'(.+)\.\s+(.+?),\s*([0-9]+)\s*(?:\(([^)]+)\))?\s*,\s*([A-Za-z]?[0-9]+(?:\s*[-–—]\s*[A-Za-z]?[0-9]+)?)\.?', rest)
    if not tail:
        raise ValueError('Cannot read title, journal, volume and pages; supply a DOI/PMID')
    return {'text':value,'authors':authors,'year':int(year[1]),'title':tail[1],
            'journal':tail[2],'volume':tail[3],'issue':tail[4],'pages':tail[5]}


def publication_date(work):
    for field in ('published-print', 'issued', 'published-online'):
        date = work.get(field, {})
        if date.get('date-parts') and date['date-parts'][0]:
            return date
    return {}


def matches_reference(reference, work):
    titles = work.get('title') or []
    journals = work.get('container-title') or []
    if not titles or not journals:
        return False
    if title_key(clean(titles[0])) != title_key(reference['title']): return False
    if title_key(clean(journals[0])) != title_key(reference['journal']): return False
    date = publication_date(work).get('date-parts', [[]])[0]
    if not date or str(date[0]) != str(reference['year']): return False
    if str(work.get('volume', '')) != reference['volume']: return False
    if reference['issue'] and str(work.get('issue', '')) != reference['issue']: return False
    if page_key(str(work.get('page', ''))) != page_key(reference['pages']): return False
    authors = work.get('author') or []
    if len(authors) != len(reference['authors']): return False
    for supplied, actual in zip(reference['authors'], authors):
        if title_key(supplied['family']) != title_key(actual.get('family', '')): return False
        given = actual.get('given', '')
        initials = ''.join(part[0] for part in re.findall(r'[^\W\d_]+', given)).lower()
        if initials != supplied['initials']: return False
    return bool(work.get('DOI'))


def search_crossref(text):
    query = urllib.parse.urlencode({'query.bibliographic':text,'rows':10})
    request = urllib.request.Request('https://api.crossref.org/works?'+query,
        headers={'Accept':'application/json','User-Agent':'CiteGoblin/0.1 bibliographic lookup'})
    with urllib.request.urlopen(request,timeout=25) as response:
        raw = response.read(2_000_001)
    if len(raw) > 2_000_000: raise ValueError('Crossref search response exceeds size limit')
    return json.loads(raw)['message']['items']


def lookup_reference(text, *, search=search_crossref, fetch=lookup_doi):
    reference = parse_reference(text)
    candidates = {normal_doi(work['DOI']):work for work in search(reference['text'])
                  if matches_reference(reference, work)}
    if not candidates:
        raise ValueError('No Crossref record matches the supplied title, authors, year, journal, volume and pages. Check the reference or supply a DOI/PMID')
    if len(candidates) != 1:
        raise ValueError('Reference is ambiguous: multiple matching DOIs ('+', '.join(sorted(candidates))+'). Supply the intended DOI')
    doi, work = next(iter(candidates.items()))
    csl = fetch(doi)
    if normal_doi(csl.get('DOI','')) != doi:
        raise ValueError('Resolved metadata returned a different DOI')
    # Keep the journal publication date from the matched authoritative record,
    # rather than a later online digitisation date.
    csl = dict(csl, issued=publication_date(work))
    if title_key(csl['title']) != title_key(reference['title']):
        raise ValueError('Resolved DOI title differs from the supplied reference')
    return csl
