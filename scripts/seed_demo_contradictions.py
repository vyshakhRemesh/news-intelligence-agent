"""
Seed twelve fictional demo articles (six contradiction pairs) and store
model-detected contradictions in PostgreSQL.

Run from the project root:

    python -m scripts.seed_demo_contradictions

The script is idempotent:
- Existing demo articles are updated instead of duplicated.
- Existing contradiction rows are updated by ContradictionService.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Final

from src.contradiction.contradiction_service import ContradictionService
from src.database.connection import SessionLocal, init_db
from src.database.models import ArticleContradiction, RawArticles


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

DEMO_PREFIX: Final[str] = "demo-contradiction-v1"
THRESHOLD: Final[float] = 0.50

# Six pairs = twelve articles/statements. These are fictional and use
# explicit negation so the NLI model has a clear relationship to classify.
DEMO_PAIRS: Final[list[dict]] = [
    {
        "topic": "transport",
        "first": {
            "title": "Riverton council approves transport plan",
            "content": (
                "The Riverton City Council approved the new public "
                "transport plan during Monday's meeting."
            ),
            "source_name": "Demo Source A",
            "slug": "riverton-plan-approved",
        },
        "second": {
            "title": "Riverton council does not approve transport plan",
            "content": (
                "The Riverton City Council did not approve the new public "
                "transport plan during Monday's meeting."
            ),
            "source_name": "Demo Source B",
            "slug": "riverton-plan-not-approved",
        },
    },
    {
        "topic": "technology",
        "first": {
            "title": "NovaTech launches Orion platform",
            "content": (
                "NovaTech launched the Orion artificial intelligence "
                "platform on Tuesday."
            ),
            "source_name": "Demo Source A",
            "slug": "novatech-orion-launched",
        },
        "second": {
            "title": "NovaTech does not launch Orion platform",
            "content": (
                "NovaTech did not launch the Orion artificial intelligence "
                "platform on Tuesday."
            ),
            "source_name": "Demo Source B",
            "slug": "novatech-orion-not-launched",
        },
    },
    {
        "topic": "business",
        "first": {
            "title": "Aster Motors reports quarterly profit",
            "content": (
                "Aster Motors reported a quarterly profit of 200 million "
                "rupees for the second quarter."
            ),
            "source_name": "Demo Source A",
            "slug": "aster-motors-profit",
        },
        "second": {
            "title": "Aster Motors does not report quarterly profit",
            "content": (
                "Aster Motors did not report a quarterly profit of 200 "
                "million rupees for the second quarter."
            ),
            "source_name": "Demo Source B",
            "slug": "aster-motors-no-profit",
        },
    },
    {
        "topic": "education",
        "first": {
            "title": "Lakeside University approves the new scholarship plan",
            "content": (
                "Lakeside University approved the new student scholarship "
                "plan during Monday's governing council meeting."
            ),
            "source_name": "Demo Source A",
            "slug": "lakeside-scholarship-approved",
        },
        "second": {
            "title": "Lakeside University does not approve the scholarship plan",
            "content": (
                "Lakeside University did not approve the new student "
                "scholarship plan during Monday's governing council meeting."
            ),
            "source_name": "Demo Source B",
            "slug": "lakeside-scholarship-not-approved",
        },
    },
    {
        "topic": "infrastructure",
        "first": {
            "title": "Harbor Metro begins passenger operations",
            "content": (
                "Harbor Metro began passenger operations on the new "
                "Blue Line on Friday morning."
            ),
            "source_name": "Demo Source A",
            "slug": "harbor-metro-operations-began",
        },
        "second": {
            "title": "Harbor Metro does not begin passenger operations",
            "content": (
                "Harbor Metro did not begin passenger operations on the "
                "new Blue Line on Friday morning."
            ),
            "source_name": "Demo Source B",
            "slug": "harbor-metro-operations-not-began",
        },
    },
    {
        "topic": "health",
        "first": {
            "title": "Greenfield clinic begins vaccination drive",
            "content": (
                "Greenfield Community Clinic began its vaccination drive "
                "on Saturday morning."
            ),
            "source_name": "Demo Source A",
            "slug": "greenfield-drive-began",
        },
        "second": {
            "title": "Greenfield clinic does not begin vaccination drive",
            "content": (
                "Greenfield Community Clinic did not begin its vaccination "
                "drive on Saturday morning."
            ),
            "source_name": "Demo Source B",
            "slug": "greenfield-drive-not-began",
        },
    },
    {
        "topic": "government",
        "first": {
            "title": "Westbridge council approves housing policy",
            "content": (
                "The Westbridge City Council approved the new affordable "
                "housing policy during Tuesday's meeting."
            ),
            "source_name": "Demo Source A",
            "slug": "westbridge-housing-approved",
        },
        "second": {
            "title": "Westbridge council does not approve housing policy",
            "content": (
                "The Westbridge City Council did not approve the new "
                "affordable housing policy during Tuesday's meeting."
            ),
            "source_name": "Demo Source B",
            "slug": "westbridge-housing-not-approved",
        },
    },
    {
        "topic": "technology",
        "first": {
            "title": "QuantumSoft launches Atlas cloud service",
            "content": (
                "QuantumSoft launched the Atlas cloud computing service "
                "for enterprise customers on Wednesday."
            ),
            "source_name": "Demo Source A",
            "slug": "quantumsoft-atlas-launched",
        },
        "second": {
            "title": "QuantumSoft does not launch Atlas cloud service",
            "content": (
                "QuantumSoft did not launch the Atlas cloud computing "
                "service for enterprise customers on Wednesday."
            ),
            "source_name": "Demo Source B",
            "slug": "quantumsoft-atlas-not-launched",
        },
    },
    {
        "topic": "business",
        "first": {
            "title": "BluePeak Energy reports annual profit",
            "content": (
                "BluePeak Energy reported an annual profit of 500 million "
                "rupees for the financial year."
            ),
            "source_name": "Demo Source A",
            "slug": "bluepeak-profit-reported",
        },
        "second": {
            "title": "BluePeak Energy does not report annual profit",
            "content": (
                "BluePeak Energy did not report an annual profit of "
                "500 million rupees for the financial year."
            ),
            "source_name": "Demo Source B",
            "slug": "bluepeak-profit-not-reported",
        },
    },
    {
        "topic": "health",
        "first": {
            "title": "Sunrise Hospital begins free health camp",
            "content": (
                "Sunrise Hospital began a free community health camp "
                "on Sunday morning."
            ),
            "source_name": "Demo Source A",
            "slug": "sunrise-health-camp-began",
        },
        "second": {
            "title": "Sunrise Hospital does not begin free health camp",
            "content": (
                "Sunrise Hospital did not begin a free community health "
                "camp on Sunday morning."
            ),
            "source_name": "Demo Source B",
            "slug": "sunrise-health-camp-not-began",
        },
    },
    {
        "topic": "education",
        "first": {
            "title": "Northfield University signs research agreement",
            "content": (
                "Northfield University signed a research agreement with "
                "the National Science Centre on Friday."
            ),
            "source_name": "Demo Source A",
            "slug": "northfield-agreement-signed",
        },
        "second": {
            "title": "Northfield University does not sign research agreement",
            "content": (
                "Northfield University did not sign a research agreement "
                "with the National Science Centre on Friday."
            ),
            "source_name": "Demo Source B",
            "slug": "northfield-agreement-not-signed",
        },
    },
    {
        "topic": "sports",
        "first": {
            "title": "Riverdale team wins championship final",
            "content": (
                "The Riverdale football team won the championship final "
                "against Hilltown on Saturday."
            ),
            "source_name": "Demo Source A",
            "slug": "riverdale-final-won",
        },
        "second": {
            "title": "Riverdale team does not win championship final",
            "content": (
                "The Riverdale football team did not win the championship "
                "final against Hilltown on Saturday."
            ),
            "source_name": "Demo Source B",
            "slug": "riverdale-final-not-won",
        },
    },
    {
        "topic": "environment",
        "first": {
            "title": "Evergreen agency approves forest restoration plan",
            "content": (
                "The Evergreen Environmental Agency approved the forest "
                "restoration plan during Thursday's review meeting."
            ),
            "source_name": "Demo Source A",
            "slug": "evergreen-restoration-approved",
        },
        "second": {
            "title": "Evergreen agency does not approve restoration plan",
            "content": (
                "The Evergreen Environmental Agency did not approve the "
                "forest restoration plan during Thursday's review meeting."
            ),
            "source_name": "Demo Source B",
            "slug": "evergreen-restoration-not-approved",
        },
    },
    {
        "topic": "finance",
        "first": {
            "title": "Metro Bank launches digital payment service",
            "content": (
                "Metro Bank launched a new digital payment service for "
                "retail customers on Monday."
            ),
            "source_name": "Demo Source A",
            "slug": "metro-bank-payment-launched",
        },
        "second": {
            "title": "Metro Bank does not launch digital payment service",
            "content": (
                "Metro Bank did not launch a new digital payment service "
                "for retail customers on Monday."
            ),
            "source_name": "Demo Source B",
            "slug": "metro-bank-payment-not-launched",
        },
    },
    {
        "topic": "science",
        "first": {
            "title": "Orion Laboratory begins lunar research programme",
            "content": (
                "Orion Laboratory began its lunar research programme "
                "on Tuesday morning."
            ),
            "source_name": "Demo Source A",
            "slug": "orion-lunar-programme-began",
        },
        "second": {
            "title": "Orion Laboratory does not begin lunar programme",
            "content": (
                "Orion Laboratory did not begin its lunar research "
                "programme on Tuesday morning."
            ),
            "source_name": "Demo Source B",
            "slug": "orion-lunar-programme-not-began",
        },
    },
    {
        "topic": "transport",
        "first": {
            "title": "Central Rail signs expansion contract",
            "content": (
                "Central Rail signed the northern route expansion contract "
                "with UrbanBuild on Thursday."
            ),
            "source_name": "Demo Source A",
            "slug": "central-rail-contract-signed",
        },
        "second": {
            "title": "Central Rail does not sign expansion contract",
            "content": (
                "Central Rail did not sign the northern route expansion "
                "contract with UrbanBuild on Thursday."
            ),
            "source_name": "Demo Source B",
            "slug": "central-rail-contract-not-signed",
        },
    },
]


def _upsert_article(
    db,
    *,
    title: str,
    content: str,
    source_name: str,
    slug: str,
    topic: str,
) -> RawArticles:
    """Insert the demo article or update the existing one."""

    url = f"https://demo.local/{DEMO_PREFIX}/{slug}"

    article = (
        db.query(RawArticles)
        .filter(
            RawArticles.url == url,
            RawArticles.source_name == source_name,
        )
        .first()
    )

    now = datetime.now(timezone.utc)

    if article is None:
        article = RawArticles(
            title=title,
            author="Project Demo Seeder",
            source_name=source_name,
            source_type="test",
            description=content,
            content=content,
            url=url,
            published_at=now,
            cleaned_title=title,
            cleaned_content=content,
            language="en",
            language_confidence=1.0,
            primary_topic=topic,
            topics=[topic],
            quality_score=90,
            preprocessing_status="completed",
            processed_at=now,
            is_duplicate=False,
            duplicate_of_id=None,
        )
        db.add(article)
        db.flush()
        logger.info("Inserted article %s: %s", article.id, title)
    else:
        article.title = title
        article.description = content
        article.content = content
        article.cleaned_title = title
        article.cleaned_content = content
        article.primary_topic = topic
        article.topics = [topic]
        article.quality_score = 90
        article.preprocessing_status = "completed"
        article.processed_at = now
        article.is_duplicate = False
        article.duplicate_of_id = None
        logger.info("Reused article %s: %s", article.id, title)

    return article


def _as_analysis_input(article: RawArticles) -> dict:
    """Convert a database article into the format expected by the service."""

    return {
        "article_id": article.id,
        "title": article.title,
        "description": article.description or "",
        "source": article.source_name or "Unknown",
        "topic": article.primary_topic or "general",
        "text": article.cleaned_content or article.content or "",
    }


def main() -> None:
    init_db()
    db = SessionLocal()

    try:
        # Loads the NLI model once, then reuses it for all six pairs.
        service = ContradictionService(db=db)
        article_ids: list[int] = []
        detected_pairs = 0

        for pair_number, pair in enumerate(DEMO_PAIRS, start=1):
            first = _upsert_article(
                db,
                topic=pair["topic"],
                **pair["first"],
            )
            second = _upsert_article(
                db,
                topic=pair["topic"],
                **pair["second"],
            )

            # Both foreign-key article IDs must exist before the service
            # writes into article_contradictions.
            db.commit()
            db.refresh(first)
            db.refresh(second)
            article_ids.extend([first.id, second.id])

            result = service.analyse_articles(
                articles=[
                    _as_analysis_input(first),
                    _as_analysis_input(second),
                ],
                threshold=THRESHOLD,
                save_results=True,
            )

            if result["contradiction_count"] == 0:
                logger.warning(
                    "Pair %d was not detected above threshold %.2f: %s <-> %s",
                    pair_number,
                    THRESHOLD,
                    first.title,
                    second.title,
                )
                continue

            detected_pairs += 1
            detected = result["contradictions"][0]
            logger.info(
                "Pair %d detected: IDs=(%s, %s), contradiction=%.4f, "
                "entailment=%.4f, neutral=%.4f",
                pair_number,
                first.id,
                second.id,
                detected["contradiction_score"],
                detected["entailment_score"],
                detected["neutral_score"],
            )

        stored_rows = (
            db.query(ArticleContradiction)
            .filter(
                ArticleContradiction.article_1_id.in_(article_ids),
                ArticleContradiction.article_2_id.in_(article_ids),
            )
            .order_by(ArticleContradiction.contradiction_score.desc())
            .all()
        )

        print("\n" + "=" * 72)
        print("CONTRADICTION STATEMENT SUMMARY")
        print("=" * 72)
        print(f"Articles available : {len(article_ids)}")
        print(f"Expected article pairs  : {len(DEMO_PAIRS)}")
        print(f"Pairs detected this run : {detected_pairs}")
        print(f"Rows found in DB        : {len(stored_rows)}")
        print(f"Threshold used          : {THRESHOLD:.2f}")
        print("-" * 72)

        for row in stored_rows:
            print(
                f"Pair ({row.article_1_id}, {row.article_2_id}) | "
                f"contradiction={row.contradiction_score:.4f} | "
                f"entailment={row.entailment_score:.4f} | "
                f"neutral={row.neutral_score:.4f}"
            )

        print("=" * 72)

        if detected_pairs != len(DEMO_PAIRS):
            raise RuntimeError(
                f"Only {detected_pairs}/{len(DEMO_PAIRS)} pairs were "
                "detected. Check the NLI model output before the demo."
            )

        logger.info(
            "All %d contradictory Statements were stored successfully.",
            detected_pairs,
        )

    except Exception:
        db.rollback()
        logger.exception("Demo contradiction seeding failed.")
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()