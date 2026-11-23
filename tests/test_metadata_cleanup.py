import copy
import unittest
from citegoblin.metadata_cleanup import clean_title,clean_metadata,effective_csl
from citegoblin.formatting import format_registry
from citegoblin.exporting import export_references
from citegoblin.cleanup import build_cleanup_plan
from test_cleanup import reference_document

NAMES=['Escherichia coli','Felis catus']


class MetadataCleanupTests(unittest.TestCase):
    def test_allcaps_protects_acronyms_and_formats_species(self):
        cleaned,caps=clean_title('GENOMIC SURVEILLANCE OF ESCHERICHIA COLI IN THE UK',NAMES)
        self.assertTrue(caps)
        self.assertEqual(cleaned,'Genomic surveillance of <i><span class="nocase">Escherichia coli</span></i> in the <span class="nocase">UK</span>')
        self.assertEqual(clean_title(cleaned,NAMES)[0],cleaned)

    def test_custom_terms_preserve_names_and_gene_case(self):
        cleaned,_=clean_title('DETECTION OF BLANDM IN LONDON USING WGS',NAMES,protected=['blaNDM','London'])
        self.assertIn('>blaNDM<',cleaned);self.assertIn('>London<',cleaned);self.assertIn('>WGS<',cleaned)

    def test_mixed_case_title_is_not_recased(self):
        cleaned,caps=clean_title('McDonald and blaNDM in London',NAMES)
        self.assertFalse(caps);self.assertEqual(cleaned,'McDonald and blaNDM in London')

    def test_entities_whitespace_and_inline_markup(self):
        cleaned,_=clean_title('  Cats &amp; dogs: <jats:italic>Felis catus</jats:italic>\n and <sup>2</sup>  ',NAMES)
        self.assertEqual(cleaned,'Cats &amp; dogs: <i><span class="nocase">Felis catus</span></i> and <sup>2</sup>')
        self.assertEqual(clean_title(cleaned,NAMES)[0],cleaned)

    def test_corrections_keep_originals_and_are_reversible(self):
        registry=reference_document().registry();key=next(iter(registry['records']))
        registry['records'][key]['csl']['title']='FELIS CATUS IN THE UK'
        original=copy.deepcopy(registry['records'][key]['csl'])
        changes,warnings=clean_metadata(registry,NAMES)
        self.assertTrue(changes);self.assertTrue(warnings)
        self.assertEqual(registry['records'][key]['csl'],original)
        self.assertIn('Felis catus',effective_csl(registry['records'][key])['title'])
        self.assertEqual(clean_metadata(registry,NAMES),( [],[] ))
        restored,_=clean_metadata(registry,NAMES,restore=True)
        self.assertTrue(restored);self.assertNotIn('cslOverrides',registry['records'][key])
        self.assertEqual(effective_csl(registry['records'][key]),original)

    def test_formatter_and_exports_use_effective_metadata(self):
        registry=reference_document().registry();key=next(iter(registry['records']))
        registry['records'][key]['csl']['title']='GENOMIC SURVEILLANCE OF ESCHERICHIA COLI IN THE UK'
        clean_metadata(registry,NAMES)
        for style in ('apa','ieee','nature'):
            registry['style']=style;preview=format_registry(registry)
            self.assertIn('UK',preview['bibliography']);self.assertIn('Escherichia coli',preview['bibliography'])
            self.assertNotIn('GENOMIC SURVEILLANCE',preview['bibliography'])
            self.assertTrue(any(s['style'].get('italic')for s in preview['bibliographyStyles']))
        for format_name in ('ris','bibtex','endnote'):
            output=export_references(registry,format_name)
            self.assertIn('Genomic surveillance',output);self.assertNotIn('GENOMIC SURVEILLANCE',output)
        self.assertTrue(registry['records'][key]['csl']['title'].isupper())

    def test_cleanup_plan_persists_overrides_and_freezes_in_text_citations(self):
        doc=reference_document(citation=True);plan=build_cleanup_plan(doc,NAMES)
        self.assertTrue(plan['metadataChanges']);self.assertEqual(plan['operations'],[])
        self.assertEqual(list(plan['expected']['citations'].values()),['[1]'])
        self.assertTrue(any('createNamedRange'in req and req['createNamedRange']['name'].startswith('CGPS_REF_')for b in plan['batches']for req in b))
