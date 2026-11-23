import copy
import unittest
from citegoblin.bibliographic import parse_reference, matches_reference, lookup_reference, page_key
from citegoblin.commands import parse
from citegoblin.document import Document
from citegoblin.runner import commands_plan
from test_manager import comment, fixture

REFERENCE='Derwing, T. M., Rossiter, M. J., & Munro, M. J. (2002). Teaching native speakers to listen to foreign-accented speech. Journal of Multilingual and Multicultural Development, 23(4), 245-259.'
WORK={'DOI':'10.1234/synthetic','title':['Teaching Native Speakers to Listen to Foreign-accented Speech'],
      'author':[{'family':'Derwing','given':'Tracey M.'},{'family':'Rossiter','given':'Marian J.'},{'family':'Munro','given':'Murray J.'}],
      'published-print':{'date-parts':[[2002,9]]},'issued':{'date-parts':[[2010,3,29]]},
      'container-title':['Journal of Multilingual and Multicultural Development'],'volume':'23','issue':'4','page':'245-259'}
CSL={'DOI':'10.1234/synthetic','type':'article-journal','title':WORK['title'][0],'author':WORK['author'],
     'issued':{'date-parts':[[2010]]},'container-title':WORK['container-title'][0]}


class BibliographicTests(unittest.TestCase):
    def test_exact_pasted_comment_parses_without_ai(self):
        parsed=parse(comment('@cite '+REFERENCE))
        self.assertEqual(parsed['reference'],REFERENCE)
        fields=parse_reference(REFERENCE)
        self.assertEqual(fields['year'],2002)
        self.assertEqual([a['family'] for a in fields['authors']],['Derwing','Rossiter','Munro'])
        self.assertTrue(matches_reference(fields,WORK))

    def test_markdown_and_wrapping_are_normalised(self):
        text=REFERENCE.replace('Journal of Multilingual and Multicultural Development','*Journal of Multilingual and Multicultural Development*').replace('foreign-accented','foreign-\naccented').replace('245-259','245–259')
        self.assertTrue(matches_reference(parse_reference(text),WORK))
        self.assertEqual(page_key('245–59'),'245-259')

    def test_conflicting_metadata_never_accepted(self):
        for key,value in [('volume','24'),('issue','3'),('page','245-260'),('title',['Different title']),
                          ('container-title',['Different journal']),('author',[{'family':'Smith','given':'T.'}]),
                          ('published-print',{'date-parts':[[2003]]})]:
            work=copy.deepcopy(WORK);work[key]=value
            self.assertFalse(matches_reference(parse_reference(REFERENCE),work),key)

    def test_unrelated_top_hit_is_ignored(self):
        wrong=copy.deepcopy(WORK);wrong['title']=['Unrelated paper'];wrong['DOI']='10.1234/wrong'
        result=lookup_reference(REFERENCE,search=lambda _:[wrong,WORK],fetch=lambda doi:dict(CSL,DOI=doi))
        self.assertEqual(result['DOI'],WORK['DOI'])
        self.assertEqual(result['issued'],WORK['published-print'])

    def test_ambiguity_and_absence_return_errors(self):
        for works,expected in [([], 'No Crossref'),([WORK,dict(WORK,DOI='10.1234/ambiguous')],'ambiguous')]:
            with self.assertRaisesRegex(ValueError,expected):lookup_reference(REFERENCE,search=lambda _:works,fetch=lambda _:self.fail('must not fetch ambiguous result'))

    def test_doi_fetch_cannot_substitute_another_article(self):
        with self.assertRaisesRegex(ValueError,'different DOI'):
            lookup_reference(REFERENCE,search=lambda _:[WORK],fetch=lambda _:dict(CSL,DOI='10.1234/other'))
        with self.assertRaisesRegex(ValueError,'title differs'):
            lookup_reference(REFERENCE,search=lambda _:[WORK],fetch=lambda _:dict(CSL,title='Wrong article'))

    def test_bad_format_is_reported_not_searched(self):
        with self.assertRaises(ValueError):lookup_reference('Anything (2002). Anything',search=lambda _:self.fail('should not search incomplete reference'))

    def test_command_pipeline_accepts_full_reference(self):
        plan,report=commands_plan(Document(fixture(),'t.test'),[comment('@cite '+REFERENCE)],reference_lookup=lambda _:dict(CSL,issued=WORK['published-print']))
        self.assertEqual(report['errors'],[])
        self.assertEqual(len(plan['expected']['references']),1)
        self.assertIn('Derwing',next(iter(plan['expected']['citations'].values())))
        self.assertIn('2002',next(iter(plan['expected']['citations'].values())))


if __name__=='__main__':unittest.main()
