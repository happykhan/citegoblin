"""Route untagged citations by persistent section heading ranges."""

import re

from .commands import SECTION, anchor_quote, fingerprint, section_name, split_section
from .document import encode

BOUNDARY_COMMAND = re.compile(r'@section\s+(' + SECTION + r')', re.I)


def boundary_target(comment):
    match = BOUNDARY_COMMAND.fullmatch(comment.get('content', '').strip())
    if not match:
        raise ValueError('Select a complete section heading and add @section followed by its tag, for example @section annex')
    return section_name(match[1])


def boundaries_plan(document, comments, *, export=None):
    boundaries = {name: document.range(prefix) for name, prefix in document.boundaries.items()}
    updates = {}
    for comment in comments:
        name = boundary_target(comment)
        if name in updates:
            raise ValueError(f'Keep only one open @section {name} comment')
        prefix = f'CGPS_START_{name}_'
        payload = {'commentId': comment['id'], 'fingerprint': fingerprint(comment)}
        if prefix in document.groups and document.value(prefix) == payload:
            updates[name] = (payload, boundaries[name], [])
            continue
        quote = anchor_quote(comment, export)
        found = document.heading(quote)
        if document.text(found)[1]:
            raise ValueError(f'Review the pending suggestions on the heading for @section {name}')
        if any(r.get('startIndex', 0) < found['endIndex'] and r['endIndex'] > found['startIndex']
               for _, ranges in document.managed_ranges(include_current=True) for r in ranges):
            raise ValueError(f'The heading for @section {name} overlaps managed citation or reference text')
        requests = [{'deleteNamedRange': {'namedRangeId': key}} for key in document.ids(prefix)] if prefix in document.groups else []
        requests.extend(encode(prefix, payload, found))
        boundaries[name] = found
        updates[name] = (payload, found, requests)
    starts = [ran['startIndex'] for ran in boundaries.values()]
    if len(starts) != len(set(starts)):
        raise ValueError('Use a different heading for each @section tag')
    index = 'CGPS_SECTIONS_'
    old_names = set(document.value(index)['names']) if index in document.groups else set()
    missing = old_names - boundaries.keys()
    if missing:
        tags = ', '.join(sorted(missing))
        raise ValueError(f'Missing section boundaries for {tags}. Add @section again to the appropriate headings.')
    requests = [request for _, _, requests in updates.values() for request in requests]
    if set(boundaries) != old_names:
        if index in document.groups:
            requests.extend({'deleteNamedRange': {'namedRangeId': key}} for key in document.ids(index))
        requests.extend(encode(index, {'names': sorted(boundaries)}, {
            'startIndex': 0, 'endIndex': 1, 'tabId': document.tab_id,
        }))
    return boundaries, updates, requests


def verify_boundaries(document, updates):
    for name, (payload, ran, _) in updates.items():
        prefix = document.boundaries.get(name)
        if prefix is None or document.range(prefix) != ran or document.value(prefix) != payload:
            raise ValueError(f'The heading for @section {name} could not be verified')


def citation_section(document, comment, boundaries, *, export=None):
    content = comment.get('content', '').strip()
    name, command = split_section(content, default=None)
    if name is not None:
        return name
    if not boundaries or not re.match(r'^@cite\s+', command):
        return 'main'
    owner = document.command_owner(comment['id'])
    if owner is not None:
        return owner
    quote = anchor_quote(comment, export)
    start = document.locate(quote)['startIndex']
    applicable = [(ran['endIndex'], name) for name, ran in boundaries.items() if ran['endIndex'] < start]
    return max(applicable, default=(0, 'main'))[1]
