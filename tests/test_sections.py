import unittest

from citegoblin.bibliography import placement_plan
from citegoblin.commands import parse, split_section
from citegoblin.document import Document
from citegoblin.runner import commands_plan
from citegoblin.sections import boundaries_plan, citation_section, verify_boundaries
from test_manager import comment, fixture, source

TAB = 't.test'
TEXT = ('Main study found a result.\nMain References\nExisting references\n'
        'Annex\nAnnex study found another result.\nAnnex References\n')


def apply_markers(raw, requests):
    named = raw['tabs'][0]['documentTab']['namedRanges']
    for request in requests:
        if 'createNamedRange' in request:
            marker = request['createNamedRange']
            named[marker['name']] = {'namedRanges': [
                {'namedRangeId': marker['name'], 'ranges': [marker['range']]}
            ]}


class SectionsTests(unittest.TestCase):
    def test_nearest_section_routes_plain_citations_and_tag_overrides_it(self):
        raw = fixture(TEXT)
        document = Document(raw, TAB)
        boundary = comment('@section annex', 'Annex', key='section-annex')
        ranges, updates, requests = boundaries_plan(document, [boundary])
        self.assertEqual(citation_section(document, comment(quote='Main study found a result.'), ranges), 'main')
        self.assertEqual(citation_section(document, comment(quote='Annex study found another result.'), ranges), 'annex')
        explicit = comment('@cite [main] 10.1234/demo', 'Annex study found another result.')
        self.assertEqual(citation_section(document, explicit, ranges), 'main')
        apply_markers(raw, requests)
        persisted = Document(raw, TAB)
        verify_boundaries(persisted, updates)
        self.assertEqual(boundaries_plan(persisted, [boundary])[2], [])

        plain = comment('@cite [1] Derwing TM. An example. Journal. 2024;1:1.')
        self.assertEqual(split_section(plain['content'])[0], 'main')
        self.assertEqual(parse(comment('@cite annex 10.1234/demo')), {'kind': 'cite', 'doi': '10.1234/demo'})

    def test_missing_boundary_stops_automatic_routing(self):
        raw = fixture(TEXT)
        _, _, requests = boundaries_plan(Document(raw, TAB), [comment('@section annex', 'Annex')])
        apply_markers(raw, requests)
        named = raw['tabs'][0]['documentTab']['namedRanges']
        for key in list(named):
            if key.startswith('CGPS_START_annex_'):
                del named[key]
        with self.assertRaisesRegex(ValueError, 'Missing section boundaries for annex'):
            boundaries_plan(Document(raw, TAB), [])

    def test_annex_uses_namespaced_metadata_and_keeps_main_register_separate(self):
        raw = fixture(TEXT)
        main = Document(raw, TAB)
        annex = Document(raw, TAB, 'annex')
        heading = comment('@bib annex', 'Annex References', key='bib-annex')
        plan = placement_plan(annex, heading)
        self.assertEqual(plan['section'], 'annex')
        self.assertTrue(all(req['createNamedRange']['name'].startswith('CGPS_SCOPE_annex_')
                            for req in plan['requests'] if 'createNamedRange' in req))
        self.assertEqual(main.registry()['records'], {})
        with self.assertRaisesRegex(ValueError, 'Not a bibliography comment'):
            placement_plan(main, heading)

    def test_already_processed_command_cannot_change_registers(self):
        raw = fixture(TEXT)
        annex = Document(raw, TAB, 'annex')
        item = comment('@cite 10.1234/demo', 'Main study found a result.', key='used')
        anchor = {'startIndex': 0, 'endIndex': 1, 'tabId': TAB}
        apply_markers(raw, annex.encode('CGPS_DOC_', {'processedCommands': {'used': 'stamp'}}, anchor))
        main = Document(raw, TAB)
        plan, report = commands_plan(main, [item], lookup=lambda _: source())
        self.assertIsNone(plan)
        self.assertIn('already used in section annex', report['errors'][0]['error'])
