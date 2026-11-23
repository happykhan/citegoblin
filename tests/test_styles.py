import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from citegoblin.styles import install_style,installed_styles,resolve_style,inspect_style
from citegoblin.formatting import format_registry
from citegoblin.richtext import inline_styles
from citegoblin.commands import parse
from citegoblin.planning import build_plan,add_citation
from citegoblin.document import Document
from citegoblin.references import record
from test_manager import fixture,source,comment


class StyleTests(unittest.TestCase):
    def registry(self):
        doc=Document(fixture(),'t.test');reg=doc.registry();r=record(source());reg['records'][r['id']]=r
        add_citation(doc,reg,'A finding 😀 [42].',[{'id':r['id']}])
        return doc,reg

    def test_all_seven_bundled_styles_render(self):
        doc,reg=self.registry()
        for key in installed_styles():
            reg['style']=key;out=format_registry(reg)
            self.assertEqual(len(out['citations']),1,key)
            self.assertIn('Smith',out['bibliography'],key)
            self.assertEqual(len(out['order']),1,key)
        self.assertGreaterEqual(len(installed_styles()),7)

    def test_case_insensitive_comments_and_aliases(self):
        for name,key in [('IEEE','ieee'),('APA','apa'),('APA 7','apa'),('Chicago','chicago-author-date'),('MLA','modern-language-association')]:
            self.assertEqual(parse(comment('@style '+name))['style'],key)

    def test_nature_superscript_and_apa_italics_are_native_styles(self):
        doc,reg=self.registry();reg['style']='nature';out=format_registry(reg)
        spans=next(iter(out['citationStyles'].values()))
        self.assertTrue(any(s['style'].get('baselineOffset')=='SUPERSCRIPT'for s in spans))
        plan=build_plan(doc,reg)
        self.assertTrue(any(r.get('updateTextStyle',{}).get('textStyle',{}).get('baselineOffset')=='SUPERSCRIPT'for batch in plan['batches']for r in batch))
        self.assertTrue(all(r['updateTextStyle']['textStyle'].get('baselineOffset','NONE')in ('NONE','SUPERSCRIPT','SUBSCRIPT')for batch in plan['batches']for r in batch if 'updateTextStyle'in r))
        reg['style']='apa';out=format_registry(reg)
        self.assertTrue(any(s['style'].get('italic')for s in out['bibliographyStyles']))

    def test_rich_text_mapping_preserves_utf16_and_rejects_different_text(self):
        spans=inline_styles('😀 <i>café &amp; DNA</i>','😀 café & DNA')
        self.assertEqual(spans,[{'start':3,'end':13,'style':{'italic':True}}])
        with self.assertRaises(ValueError):inline_styles('<i>wrong text</i>','other text')

    def test_install_resolves_dependent_style_with_no_arbitrary_hosts(self):
        parent='''<style xmlns="http://purl.org/net/xbiblio/csl" class="in-text"><info><title>Parent</title><category citation-format="numeric"/></info><citation/><bibliography/></style>'''
        dependent='''<style xmlns="http://purl.org/net/xbiblio/csl"><info><title>Journal</title><link rel="independent-parent" href="http://www.zotero.org/styles/parent-example"/></info></style>'''
        with tempfile.TemporaryDirectory()as root,patch('citegoblin.styles.config_dir',return_value=Path(root)):
            result=install_style('journal-example',fetch=lambda key:dependent if key=='journal-example'else parent)
            self.assertEqual(result['resolvedParent'],'parent-example')
            self.assertEqual(resolve_style('journal-example'),'journal-example')
            self.assertTrue((Path(root)/'styles/journal-example.csl').exists())
            bad=dependent.replace('http://www.zotero.org','https://example.org')
            with self.assertRaises(ValueError):install_style('unsafe-example',fetch=lambda _:bad)

    def test_note_styles_and_path_traversal_are_rejected(self):
        with self.assertRaises(ValueError):inspect_style('<style xmlns="http://purl.org/net/xbiblio/csl" class="note"><bibliography/></style>')
        with self.assertRaises(ValueError):resolve_style('../../oauth-client')


if __name__=='__main__':unittest.main()
