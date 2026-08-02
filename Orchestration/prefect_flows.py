import logging
import os
import sys

from prefect import flow, get_run_logger


# Add the project root to Python's import path.
PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


from main import EnhancedPipeline
from platform_agent import run_multi_user_cron


logger = logging.getLogger(__name__)


@flow(
    name="news-ingestion-pipeline",
    description=(
        "Fetches, stores, preprocesses, enriches, embeds, "
        "models topics, recommends and deduplicates articles."
    ),
    log_prints=True,
    retries=1,
    retry_delay_seconds=60,
)
def ingestion_flow() -> dict:
    """
    Run the News Intelligence ingestion pipeline.

    This flow will eventually run every three hours.
    It does not generate the daily briefing.
    """

    prefect_logger = get_run_logger()

    prefect_logger.info(
        "Starting the News Intelligence ingestion flow."
    )

    pipeline = EnhancedPipeline()

    try:
        pipeline.run()

        result = {
            "status": "completed",
            "statistics": dict(pipeline.stats),
        }

        prefect_logger.info(
            "Ingestion flow completed. Statistics: %s",
            result["statistics"],
        )

        return result

    except Exception:
        prefect_logger.exception(
            "The ingestion flow failed."
        )

        # Re-raising is important because Prefect must mark
        # the flow as failed and apply its retry policy.
        raise

    finally:
        pipeline.close()


@flow(
    name="daily-news-briefing",
    description=(
        "Runs the LangGraph platform agent and generates "
        "the daily briefing for the configured mock user."
    ),
    log_prints=True,
    retries=1,
    retry_delay_seconds=60,
)
def daily_briefing_flow() -> dict:
    """
    Run the daily briefing agent.

    This flow will eventually run once every day.
    """

    prefect_logger = get_run_logger()

    prefect_logger.info(
        "Starting the daily briefing flow."
    )

    try:
        run_multi_user_cron()

        prefect_logger.info(
            "Daily briefing flow completed."
        )

        return {
            "status": "completed",
        }

    except Exception:
        prefect_logger.exception(
            "The daily briefing flow failed."
        )

        raise


if __name__ == "__main__":
    from prefect import serve
    from prefect.schedules import Cron

    ingestion_deployment = ingestion_flow.to_deployment(
        name="news-ingestion-every-3-hours",
        schedule=Cron(
            "0 */3 * * *",
            timezone="Asia/Kolkata",
        ),
        tags=["ingestion", "news-pipeline"],
        description=(
            "Runs the news ingestion pipeline every three hours."
        ),
    )

    briefing_deployment = daily_briefing_flow.to_deployment(
        name="daily-news-briefing-7am",
        schedule=Cron(
            "0 7 * * *",
            timezone="Asia/Kolkata",
        ),
        tags=["briefing", "langgraph"],
        description=(
            "Generates and stores the daily briefing "
            "for the configured mock user."
        ),
    )

    serve(
        ingestion_deployment,
        briefing_deployment,
    )