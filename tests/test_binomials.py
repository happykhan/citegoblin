from pathlib import Path
import tempfile
import unittest
from citegoblin.binomials import clean_reference_text,load_names,overlay_styles
from citegoblin.document import units

NAMES=['Felis catus','Escherichia coli','Staphylococcus aureus']


class ReferenceNameTests(unittest.TestCase):
    def test_normalises_only_approved_names_in_reference_text(self):
        text,changes,_=clean_reference_text('Title: FELIS CATUS and Escherichia Coli. Ordinary TITLE CASE.',NAMES)
        self.assertEqual(text,'Title: Felis catus and Escherichia coli. Ordinary TITLE CASE.')
        self.assertEqual(len(changes),2);self.assertTrue(all(c['italic']for c in changes))

    def test_offsets_use_utf16_and_preserve_nbsp(self):
        text,changes,_=clean_reference_text('😀 FELIS\u00a0CATUS ST131',NAMES)
        self.assertEqual(text,'😀 Felis\u00a0catus ST131');self.assertEqual(changes[0]['start'],3)
        self.assertEqual(changes[0]['end']-changes[0]['start'],units('FELIS\u00a0CATUS'))

    def test_abbreviations_need_context_in_the_same_reference(self):
        text,changes,skipped=clean_reference_text('Felis catus and f. CATUS.\nF. CATUS.',NAMES,abbreviations=True)
        self.assertEqual(text,'Felis catus and F. catus.\nF. CATUS.')
        self.assertEqual(len(changes),2);self.assertEqual(len(skipped),1)

    def test_ambiguous_abbreviations_are_left_alone(self):
        text,changes,skipped=clean_reference_text('Escherichia coli; Entamoeba coli; E. COLI.',NAMES+['Entamoeba coli'],abbreviations=True)
        self.assertTrue(text.endswith('E. COLI.'));self.assertEqual(len(skipped),1)

    def test_urls_and_unknown_names_are_not_changed(self):
        text,changes,_=clean_reference_text('https://example.org/FELIS_CATUS Unknown species',NAMES)
        self.assertEqual(text,'https://example.org/FELIS_CATUS Unknown species');self.assertEqual(changes,[])

    def test_italic_overlay_preserves_other_csl_styles(self):
        spans=overlay_styles([{'start':0,'end':20,'style':{'bold':True,'smallCaps':True}}],[{'start':3,'end':14}])
        name=next(s for s in spans if s['start']==3)
        self.assertEqual(name['style'],{'bold':True,'smallCaps':False,'italic':True})
        self.assertTrue(spans[0]['style']['smallCaps']);self.assertTrue(spans[-1]['style']['smallCaps'])

    def test_bundled_cat_name_and_local_extension(self):
        self.assertIn('Felis catus',load_names())
        with tempfile.TemporaryDirectory()as root:
            path=Path(root)/'names.txt';path.write_text('Bacillus subtilis\n')
            self.assertIn('Bacillus subtilis',load_names(path))
            path.write_text('Not a valid binomial')
            with self.assertRaises(ValueError):load_names(path)
