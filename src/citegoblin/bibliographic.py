"""Resolve pasted journal references through Crossref, without AI."""
import html
import json
import re
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from .references import lookup_doi, normal_doi


def clean(value):
    return ' '.join(html.unescape(re.sub('<[^>]+>', '', value)).replace('*', '').split())


def page_key(value):
    value = re.sub(r'\s+', '', value).replace('–', '-').replace('—', '-')
    match = re.fullmatch(r'(\d+)-(\d+)', value)
    if match and len(match[2]) < len(match[1]):
        return match[1] + '-' + match[1][:-len(match[2])] + match[2]
    return value


YEAR = r'[12][0-9]{3}'
PAGE = r'(?:article\s+)?(?P<pages>[a-z]?\d+(?:\s*[-–—]\s*[a-z]?\d+)?)'
VOLUME = r'(?P<volume>\d+)(?:\s*\((?P<issue>[^)]+)\))?'
NUMBERED_VOLUME = r'vol\.\s*(?P<volume>\d+)(?:,\s*no\.\s*(?P<issue>[^,]+))?'
DATE_PREFIX = r'(?:[a-z]{3,9}\.?\s+)?'
DATE_SUFFIX = r'(?:\s+[a-z]{3,9}\.?\s*(?:\d{1,2})?)?'

# The layout determines where the publication details live. Author and title
# boundaries are checked against Crossref, since initials and journals contain stops.
LAYOUTS = tuple(re.compile(pattern, re.IGNORECASE) for pattern in (
    rf'(?P<authors>.+?)(?:\s*\((?P<apa_year>{YEAR})\)|[,\.]\s+(?P<year>{YEAR}))\.\s+'
    rf'(?P<head>.+?)[, ]\s*{VOLUME}\s*[:,]\s*{PAGE}',
    rf'(?P<head>.+)\.\s+(?P<year>{YEAR}){DATE_SUFFIX}\s*;\s*{VOLUME}\s*:\s*{PAGE}',
    rf'(?P<head>.+?)\s+{VOLUME}\s*,\s*{PAGE}\s*\((?P<year>{YEAR})\)',
    rf'(?P<head>.+?),\s*{NUMBERED_VOLUME},\s*(?:pp?\.\s*)?{PAGE},\s*{DATE_PREFIX}(?P<year>{YEAR})',
    rf'(?P<head>.+?),\s*{NUMBERED_VOLUME},\s*{DATE_PREFIX}(?P<year>{YEAR}),\s*(?:pp?\.\s*)?{PAGE}',
))
TRAILING_DOI = re.compile(r'(?:\s|,)(?:https?://(?:dx\.)?doi\.org/|doi:\s*)(10\.\d{4,9}/\S+)\s*$', re.I)
SEPARATOR = re.compile(r'\.\s+|,\s+(?=[\'‘“"])|[\'’”"],\s+')
ET_AL = re.compile(r'(?:[ ,]+)et\s+al\.?$', re.I)
ELLIPSIS = re.compile(r'\s*(?:…|\.\s*\.\s*\.)\s*')


def key(value):
    text = unicodedata.normalize('NFKD', value).casefold()
    return ''.join(char for char in text if char.isalnum())


def split_citation(head, authors):
    cuts = list(SEPARATOR.finditer(head))
    if authors is not None:
        for cut in cuts:
            yield authors, head[:cut.start()], head[cut.end():]
        return
    for i, first in enumerate(cuts):
        for second in cuts[i+1:]:
            yield head[:first.start()] + first[0].rstrip(), head[first.end():second.start()], head[second.end():]


def parse_reference(value):
    value = clean(value)
    if len(value) > 4000:
        raise ValueError('Paste one journal reference at a time or supply a DOI or PMID')
    text = re.sub(r'^(?:\[\d+\]|\d+[.)])\s+', '', value)
    doi_match = TRAILING_DOI.search(text)
    doi = normal_doi(doi_match[1]) if doi_match else None
    if doi_match:
        text = text[:doi_match.start()].rstrip(' ,')
    layouts = []
    for layout in LAYOUTS:
        match = layout.fullmatch(text.rstrip('.'))
        if not match:
            continue
        fields = match.groupdict()
        head, authors = fields['head'], fields.get('authors')
        limit = 1 if authors is not None else 2
        if not limit <= sum(1 for _ in SEPARATOR.finditer(head)) <= 100:
            continue
        layouts.append({
            'year': int(fields.get('apa_year') or fields['year']),
            'volume': fields['volume'], 'issue': fields['issue'],
            'pages': fields['pages'], 'head': head, 'authors': authors,
        })
    if not layouts:
        raise ValueError('Could not read a complete journal reference. Supply a DOI or PMID.')
    return {'text': value, 'doi': doi, 'layouts': layouts}


def publication_date(work):
    for field in ('published-print', 'issued', 'published-online'):
        date = work.get(field, {})
        if date.get('date-parts') and date['date-parts'][0]:
            return date
    return {}


def author_forms(authors):
    """Render the name orders used by the supported reference layouts."""
    families = [a.get('family', '') for a in authors]
    given = [a.get('given', '') for a in authors]
    initials = [''.join(part[0] for part in re.findall(r'[^\W\d_]+', name)) for name in given]
    for names in (given, initials):
        inverted = [family + ' ' + name for family, name in zip(families, names)]
        natural = [name + ' ' + family for family, name in zip(families, names)]
        yield inverted
        yield natural
        yield inverted[:1] + natural[1:]


def matches_authors(text, authors):
    if not authors or any(not a.get('family') for a in authors):
        return False
    text = text.rstrip(' ,')
    truncated = ET_AL.search(text)
    if truncated:
        text = text[:truncated.start()]
    portions = ELLIPSIS.split(text)
    for names in author_forms(authors):
        if len(portions) == 2 and not truncated:
            if key(portions[1]) == key(names[-1]) and any(
                key(portions[0]) == key(' '.join(names[:count]))
                for count in range(1, len(names) - 1)
            ):
                return True
            continue
        counts = range(1, len(names)) if truncated else (len(names),)
        for count in counts:
            visible = names[:count]
            variants = [' '.join(visible)]
            if count > 1:
                variants.append(' '.join(visible[:-1]) + ' and ' + visible[-1])
            if key(text) in {key(variant) for variant in variants}:
                return True
    return False


def matches_reference(reference, work):
    titles = work.get('title') or []
    journals = (work.get('container-title') or []) + (work.get('short-container-title') or [])
    if not titles or not journals or not work.get('DOI'):
        return False
    if reference['doi'] and reference['doi'] != normal_doi(work['DOI']):
        return False
    date = publication_date(work).get('date-parts', [[]])[0]
    title = key(clean(titles[0]))
    journal_keys = {key(clean(name)) for name in journals if name}
    page_keys = {page_key(str(work[field])).casefold()
                 for field in ('page', 'article-number') if work.get(field)}
    for layout in reference['layouts']:
        if not date or str(date[0]) != str(layout['year']):
            continue
        if str(work.get('volume', '')) != layout['volume']:
            continue
        if layout['issue'] and str(work.get('issue', '')) != layout['issue']:
            continue
        if page_key(layout['pages']).casefold() not in page_keys:
            continue
        for authors, article_title, journal in split_citation(layout['head'], layout['authors']):
            if key(article_title) == title and key(journal) in journal_keys:
                if matches_authors(authors, work.get('author') or []):
                    return True
    return False


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
    try:
        works = search(reference['text'])
    except (urllib.error.URLError, TimeoutError) as error:
        raise ValueError('Crossref search is unavailable. Try again or supply a DOI or PMID.') from error
    candidates = {normal_doi(work['DOI']): work for work in works
                  if matches_reference(reference, work)}
    if not candidates:
        raise ValueError('No Crossref record matches the supplied title, authors, year, journal, volume and pages. Check the reference or supply a DOI or PMID.')
    if len(candidates) != 1:
        raise ValueError('Reference is ambiguous: multiple matching DOIs ('+', '.join(sorted(candidates))+'). Supply the intended DOI or PMID.')
    doi, work = next(iter(candidates.items()))
    csl = fetch(doi)
    if normal_doi(csl.get('DOI','')) != doi:
        raise ValueError('Resolved metadata returned a different DOI')
    # Keep the journal publication date from the matched authoritative record,
    # rather than a later online digitisation date.
    csl = dict(csl, issued=publication_date(work))
    if key(clean(csl['title'])) != key(clean(work['title'][0])):
        raise ValueError('Resolved DOI title differs from the supplied reference')
    return csl
