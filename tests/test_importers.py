from django.test import TestCase

from journal.models import IssueType
from utils.testing import helpers

from plugins.ingenta.importers import import_article_xml

XML_TEMPLATE = """
    <!DOCTYPE article PUBLIC '-//NLM//DTD Journal Publishing DTD v2.1 20050630//EN' 'http://uploads.ingentaconnect.com/docs/dtd/ingenta-journalpublishing.dtd'>
    <article article-type="{section_name}">
    <front>
        <journal-meta>
            <journal-title>Journal Title</journal-title>
        </journal-meta>
        <article-meta>
            <article-id pub-id-type="sici">{sici}</article-id>
            <article-id pub-id-type="publisher-id">{pubid}</article-id>
            <article-id pub-id-type="other">{ingenta_id}</article-id>
            <article-id pub-id-type="doi">{doi}</article-id>
        <article-categories>
            <subj-group>
            <subject>Articles</subject>
            </subj-group>
        </article-categories>
        <title-group>
            <article-title>{article_title}</article-title>
        </title-group>
        <contrib-group>
            <contrib>
            <name>
                <surname>{author_1_surname}</surname>
                <given-names>{author_1_given_names}</given-names>
            </name>
            </contrib>
            <contrib>
            <name>
                <surname>{author_2_surname}</surname>
                <given-names>{author_2_given_names}</given-names>
            </name>
            </contrib>
        </contrib-group>
        <pub-date>
            <day>{pub_date_day}</day>
            <month>{pub_date_month}</month>
            <year>{pub_date_year}</year>
        </pub-date>
        <volume>{volume}</volume>
        <issue>{issue}</issue>
        <fpage>{fpage}</fpage>
        <lpage>{lpage}</lpage>
        <abstract>
            {abstract}
        </abstract>
        </article-meta>
    </front>
    </article>
"""


class TestImportArticle(TestCase):

    def setUp(self):
        self.default_metadata = {
            "section_name": "article",
            "sici": "sici",
            "pubid": "pubid",
            "doi": "10.000/doi",
            "ingenta_id": "ingenta_id",
            "article_title": "article_title",
            "author_1_surname": "author_1_surname",
            "author_1_given_names": "author_1_name",
            "author_2_surname": "author_2_surname",
            "author_2_given_names": "author_2_name",
            "pub_date_day": "12",
            "pub_date_month": "12",
            "pub_date_year": "1986",
            "volume": "2",
            "issue": "1",
            "fpage": "111",
            "lpage": "112",
            "abstract": "abstract",
        }
        self.journal_one, _ = helpers.create_journals()
        helpers.create_roles(["author"])
        IssueType.objects.get_or_create(code="issue", journal = self.journal_one)
        self.owner = helpers.create_user("owner@email.com")


    def test_article_import(self):
        xml = XML_TEMPLATE.format(**self.default_metadata)
        article = import_article_xml(self.journal_one, xml, owner=self.owner)

        self.assertEqual(
            article.title, self.default_metadata["article_title"])

    def test_article_update(self):
        ingenta_id = "test_id"
        metadata = dict(self.default_metadata, ingenta_id=ingenta_id)
        xml = XML_TEMPLATE.format(**metadata)
        article_1 = import_article_xml(self.journal_one, xml, owner=self.owner)
        article_2 = import_article_xml(self.journal_one, xml, owner=self.owner)

        self.assertEqual(article_1, article_2)

    def test_article_section_import(self):
        section_name = "test section"
        metadata = dict(self.default_metadata, section_name=section_name)
        xml = XML_TEMPLATE.format(**metadata)
        article = import_article_xml(self.journal_one, xml, owner=self.owner)

        self.assertEqual(
            article.section.name, section_name)

    def test_article_author_import(self):
        test_author_name = "Test"
        test_author_surname = "McTest"
        metadata = dict(
            self.default_metadata,
            author_1_given_names=test_author_name,
            author_1_surname=test_author_surname,
        )
        xml = XML_TEMPLATE.format(**metadata)
        article = import_article_xml(self.journal_one, xml, owner=self.owner)

        self.assertTrue(
            test_author_surname
            in article.frozenauthor_set.values_list("last_name", flat=True)
        )

    def test_article_issue_import(self):
        issue = 13
        volume = 17
        metadata = dict(
            self.default_metadata,
            issue=issue,
            volume=volume,
        )
        xml = XML_TEMPLATE.format(**metadata)
        article = import_article_xml(self.journal_one, xml, owner=self.owner)

        self.assertTrue(
            article.primary_issue.volume == volume
            and article.primary_issue.issue == issue
            and article.issues.filter(volume=volume, issue=issue).exists()
        )
