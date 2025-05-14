from bs4 import BeautifulSoup
from django.db import transaction
from django.conf import settings
from django.core.files.base import ContentFile
import tarfile

from core.models import Account
from identifiers.models import Identifier
from journal import models as journal_models
from production.logic import replace_galley_file, save_galley
from submission import models as submission_models
from utils.logger import get_logger

from plugins.ingenta import parsers

logger = get_logger(__name__)


class DummyRequest():
    """ Used as to mimic request interface for `save_galley`"""
    def __init__(self, user):
        self.user = user


def import_from_archive(tar_path, journal, owner):
    logger.info("Ingenta import from archive: %s", tar_path)
    with tarfile.open(tar_path, "r:gz") as archive:
        file_names = archive.getnames()
        for name in sorted(file_names):
            if name.endswith(".xml"):
                logger.info("Extracting file %s", name)
                xml = archive.extractfile(name)
                prefix = name.split(".xml")[0]
                pdf = None
                pdf_name = prefix + ".pdf"
                if pdf_name in file_names:
                    pdf_blob = archive.extractfile(pdf_name).read()
                    pdf = ContentFile(pdf_blob)
                    pdf.name = pdf_name
                import_article(journal, xml, owner, pdf)


def import_article(journal, xml_file, owner, pdf=None):
    logger.info("Ingenta import from XML: %s", xml_file.name)
    xml_contents = xml_file.read()
    article = import_article_xml(journal, xml_contents, owner)

    request = DummyRequest(owner)

    if pdf and pdf.name not in article.pdfs.values_list(
        "file__original_filename", flat=True,
    ):
        logger.info("Importing new PDF %s", pdf.name)
        save_galley(article, request, pdf, is_galley=True)
    elif pdf:
        logger.info("Replacing PDF %s", pdf.name)
        galley = article.pdfs.get(file__original_filename=pdf.name)
        replace_galley_file(article, request, galley, pdf)
    else:
        logger.info("No PDF provided")


def import_article_xml(journal, xml_contents, owner):
    soup = BeautifulSoup(xml_contents, 'lxml')
    if not soup.find("journal-title") or not soup.find("journal-title").text:
        # MS: I found some empty SGML files that have no journal title
        logger.warning("Empty XML detected")
        return None
    metadata = parsers.parse_article_metadata(soup)
    article = get_or_create_article(journal, metadata, owner)

    issue, created = get_or_create_issue(metadata, article.journal)
    if created:
        issue.date = article.date_published
        issue.save()
    issue.articles.add(article)
    article.primary_issue = issue
    article.save()

    return article


def get_or_create_article(journal, metadata, owner):
    with transaction.atomic():
        article = None
        section, _ = submission_models.Section.objects.get_or_create(
                journal=journal,
                name=metadata["section_name"],
        )
        if metadata.get("ingenta_id"):
            try:
                ident = Identifier.objects.get(
                    id_type="ingenta_id", identifier=metadata["ingenta_id"])
            except Identifier.DoesNotExist:
                pass
            else:
                article = ident.article

        if not article:
            article = submission_models.Article.objects.create(
                journal=journal,
                title=metadata["title"],
                abstract=metadata["abstract"],
                date_published=metadata["date_published"],
                date_accepted=metadata["date_accepted"],
                date_submitted=metadata["date_submitted"],
                page_numbers=metadata["page_range"],
                stage=submission_models.STAGE_PUBLISHED,
                is_import=True,
                owner=owner,
            )
            logger.debug("New Article: %s", article)
        import_article_authors(article, metadata)

        for id_type in {"doi", "ingenta_id", "sici"}:
            if metadata.get(id_type):
                ident, created = Identifier.objects.get_or_create(
                    id_type=id_type,
                    identifier=metadata[id_type],
                    article=article,
                )
                if created:
                    logger.debug("New identifier: %s", ident)

        logger.info("Imported article: %s", article)
        article.section = section
        article.save()
        return article


def get_or_create_issue(metadata, journal):
    issue_type = journal_models.IssueType.objects.get(
        code="issue",
        journal=journal,
    )
    issue, created = journal_models.Issue.objects.get_or_create(
        volume=metadata["volume"],
        issue=metadata["issue"],
        journal=journal,
        defaults={"issue_type": issue_type}
    )
    if created:
        logger.info("New Issue created: %s", issue)
    return issue, created


def import_article_authors(article, metadata):
    authors = metadata["authors"]
    for author in authors:
        account, _ = Account.objects.get_or_create(
            email=author["email"],
            defaults={
                "first_name": author["first_name"],
                "middle_name": author["middle_name"],
                "last_name": author["last_name"],
                # Ingenta only provides author names
                "institution": article.journal.name,
            }
        )
        account.snapshot_self(article)
