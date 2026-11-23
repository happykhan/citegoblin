"""Source identifiers and verified metadata, separate from claim assessment."""
import hashlib
import html
import json
import re
import unicodedata
import urllib.parse
import urllib.request
from xml.etree import ElementTree as ET


def normal_doi(doi):
    doi = re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)', '', doi.strip(), flags=re.I)
    doi = urllib.parse.unquote(doi).rstrip('.,;').lower()
    if not re.fullmatch(r'10\.\d{4,9}/\S+', doi):
        raise ValueError('Invalid DOI')
    return doi


def title_key(title):
    value = unicodedata.normalize('NFKD', title).lower()
    return re.sub('[^a-z0-9]', '', value)


def record(csl, existing=None, pmid=None):
    csl = dict(csl)
    pmid = normal_pmid(str(pmid or csl['PMID'])) if pmid or csl.get('PMID') else None
    doi = normal_doi(csl['DOI']) if csl.get('DOI') else None
    year = str((csl.get('issued', {}).get('date-parts') or [['']])[0][0])
    url = csl.get('URL', '').rstrip('/')
    if not csl.get('title'):
        raise ValueError('Reference title is required')
    # Preserve established IDs; do not regenerate IDs from differently serialised years.
    for old in (existing or {}).values():
        if pmid and str(old.get('pmid') or old['csl'].get('PMID','')) == pmid:
            if doi and old.get('doi') and normal_doi(old['doi']) != doi:
                raise ValueError('PMID matches a reference with a different DOI')
            return dict(old,pmid=pmid)
        if doi and old.get('doi') and normal_doi(old['doi']) == doi:
            if pmid and old.get('pmid') and str(old['pmid']) != pmid:
                raise ValueError('DOI matches a reference with a different PMID')
            return dict(old,pmid=pmid or old.get('pmid'))
        data = old['csl']
        other_year = str((data.get('issued', {}).get('date-parts') or [['']])[0][0])
        if not doi and not old.get('doi') and title_key(data['title']) == title_key(csl['title']) and other_year == year and data.get('URL','').rstrip('/') == url:
            return old
    identity = 'doi:'+doi if doi else 'title:'+title_key(csl['title'])+'year:'+year+'url:'+url
    key = 'r'+hashlib.sha256(identity.encode()).hexdigest()[:16]
    if pmid:
        csl['PMID'] = pmid
    if doi:
        csl['DOI'] = doi
    csl['id'] = key
    return {'id': key, 'doi': doi, 'pmid': pmid, 'csl': csl, 'aliases': [], 'currentNumber': None}


def lookup_doi(doi):
    doi = normal_doi(doi)
    url = 'https://api.crossref.org/works/'+urllib.parse.quote(doi, safe='')+'/transform/application/vnd.citationstyles.csl+json'
    request = urllib.request.Request(url, headers={'Accept':'application/json', 'User-Agent':'CiteGoblin/0.1 metadata lookup'})
    with urllib.request.urlopen(request, timeout=25) as response:
        raw = json.load(response)
    if normal_doi(raw['DOI']) != doi:
        raise ValueError('Registry returned a different DOI')
    # Do not propagate registry-internal fields into document metadata.
    keep = {'title','author','editor','translator','container-title','container-title-short','volume','issue','page',
            'publisher','publisher-place','URL','DOI','ISBN','ISSN','edition','genre','number','issued','type'}
    csl = {k:v for k,v in raw.items() if k in keep}
    csl['title'] = html.unescape(re.sub('<[^>]+>', '', csl['title'])).strip()
    csl['type'] = {'journal-article':'article-journal','posted-content':'article','book-chapter':'chapter'}.get(csl['type'], csl['type'])
    if raw.get('type') == 'posted-content':
        csl['genre'] = 'Preprint'
    if raw.get('published-print') and csl['type'] == 'article-journal':
        csl['issued'] = raw['published-print']
    return csl


def comment_candidates(comments):
    """Extract candidates, not instructions or an automatic insertion decision."""
    out = []
    for c in comments:
        if c.get('resolved') or c.get('deleted'):
            continue
        text = '\n'.join([c.get('content','')]+[r.get('content','') for r in c.get('replies',[])])
        dois = sorted({normal_doi(x) for x in re.findall(r'10\.\d{4,9}/[^\s<>;]+', text)})
        pmids = sorted(set(re.findall(r'(?:PMID[:\s]+|pubmed\.ncbi\.nlm\.nih\.gov/)(\d+)', text, re.I)))
        urls = sorted(set(re.findall(r'https?://[^\s<>]+', text)))
        if dois or pmids or urls:
            out.append({'commentId':c['id'], 'anchor':c.get('anchor'),
                        'quote':(c.get('quotedFileContent') or {}).get('value'),
                        'dois':dois,'pmids':pmids,'urls':urls,'status':'needs-location-and-source-review'})
    return out


def normal_pmid(value):
    value = value.strip()
    if value.startswith(('https://', 'http://')):
        url = urllib.parse.urlsplit(value)
        if url.hostname != 'pubmed.ncbi.nlm.nih.gov' or url.username or url.password:
            raise ValueError('Invalid PubMed URL')
        match = re.fullmatch(r'/([1-9][0-9]*)/?', url.path)
    else:
        match = re.fullmatch(r'(?:PMID\s*:\s*)?([1-9][0-9]*)', value, re.I)
    if not match:
        raise ValueError('Invalid PMID; use PMID:12345678 or a PubMed article URL')
    return match[1]


def identifier(value):
    value = value.strip()
    if re.match(r'^PMID\s*:', value, re.I) or value.isdigit():
        return {'pmid': normal_pmid(value)}
    if value.startswith(('https://', 'http://')) and urllib.parse.urlsplit(value).hostname == 'pubmed.ncbi.nlm.nih.gov':
        return {'pmid': normal_pmid(value)}
    try:
        return {'doi': normal_doi(value)}
    except ValueError:
        if re.search(r'\([12][0-9]{3}\)\s*\.', value):
            return {'reference':value}
        raise


def _text(node):
    return ''.join(node.itertext()).strip() if node is not None else ''


def pubmed_csl(content, expected_pmid):
    """Parse NCBI's authoritative PubMed XML; require an exact identifier match."""
    try:
        root = ET.fromstring(content)
    except ET.ParseError as error:
        raise ValueError('PubMed returned invalid XML metadata') from error
    matches = [a for a in root.findall('./PubmedArticle')
               if a.findtext('./MedlineCitation/PMID') == expected_pmid]
    if len(matches) != 1:
        raise ValueError('PubMed did not return exactly the requested article')
    entry = matches[0]; article = entry.find('./MedlineCitation/Article')
    if article is None:
        raise ValueError('PubMed returned an unsupported article record')
    title = _text(article.find('ArticleTitle'))
    if not title:
        raise ValueError('PubMed article has no title')
    csl = {'type':'article-journal', 'title':title, 'PMID':expected_pmid,
           'URL':'https://pubmed.ncbi.nlm.nih.gov/'+expected_pmid+'/'}
    for key, path in [('container-title','Journal/Title'),('container-title-short','Journal/ISOAbbreviation'),
                      ('volume','Journal/JournalIssue/Volume'),('issue','Journal/JournalIssue/Issue'),
                      ('page','Pagination/StartPage'),('ISSN','Journal/ISSN')]:
        text = _text(article.find(path))
        if text: csl[key] = text
    pages = _text(article.find('Pagination/MedlinePgn'))
    if pages: csl['page'] = pages
    elocation = next((_text(n) for n in article.findall('ELocationID') if n.get('EIdType') == 'pii'), None)
    if elocation and not csl.get('page'): csl['page'] = elocation
    authors = []
    for author in article.findall('AuthorList/Author'):
        collective = _text(author.find('CollectiveName'))
        family = _text(author.find('LastName'))
        if collective:
            authors.append({'literal':collective})
        elif family:
            item = {'family':family}
            given = _text(author.find('ForeName')) or _text(author.find('Initials'))
            if given: item['given'] = given
            suffix = _text(author.find('Suffix'))
            if suffix: item['suffix'] = suffix
            authors.append(item)
    if authors: csl['author'] = authors
    # Journal issue date is the publication date; do not mistake indexing or
    # manuscript-receipt dates for publication. Preserve e-publication separately.
    pubdate = article.find('Journal/JournalIssue/PubDate')
    year = _text(pubdate.find('Year')) if pubdate is not None else ''
    if not year and pubdate is not None:
        match = re.search(r'\b([12][0-9]{3})\b', _text(pubdate.find('MedlineDate')))
        year = match[1] if match else ''
    if not year:
        pubdate = article.find('ArticleDate[@DateType="Electronic"]')
        year = _text(pubdate.find('Year')) if pubdate is not None else ''
    if not re.fullmatch(r'[12][0-9]{3}', year):
        raise ValueError('PubMed article has no usable publication year')
    parts = [int(year)]
    month = _text(pubdate.find('Month'))
    months = {m:i+1 for i,m in enumerate(('Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'))}
    number = int(month) if month.isdigit() else months.get(month[:3].title())
    if number and 1 <= number <= 12:
        parts.append(number)
        day = _text(pubdate.find('Day'))
        if day.isdigit() and 1 <= int(day) <= 31: parts.append(int(day))
    csl['issued'] = {'date-parts':[parts]}
    dois = {normal_doi(_text(n)) for n in entry.findall('PubmedData/ArticleIdList/ArticleId') if n.get('IdType') == 'doi'}
    if len(dois) > 1: raise ValueError('PubMed record contains conflicting DOIs')
    if dois: csl['DOI'] = dois.pop()
    return csl


def lookup_pmid(value):
    pmid = normal_pmid(value)
    query = urllib.parse.urlencode({'db':'pubmed','id':pmid,'retmode':'xml','tool':'citegoblin'})
    request = urllib.request.Request('https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?'+query,
                                    headers={'User-Agent':'CiteGoblin/0.1 metadata lookup'})
    with urllib.request.urlopen(request, timeout=25) as response:
        content = response.read(2_000_001)
    if len(content) > 2_000_000: raise ValueError('PubMed record exceeds metadata size limit')
    return pubmed_csl(content, pmid)


def resolve(value):
    source = identifier(value)
    if 'reference' in source:
        from .bibliographic import lookup_reference
        return lookup_reference(source['reference'])
    return lookup_pmid(source['pmid']) if 'pmid' in source else lookup_doi(source['doi'])
