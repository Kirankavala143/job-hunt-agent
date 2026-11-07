
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)


def get_jobspy_country(location: str) -> str:
    """Map the requested location to JobSpy's country setting."""

    loc = str(location or "").strip().lower()

    if any(term in loc for term in (
        "india", "bangalore", "bengaluru", "mumbai",
        "delhi", "hyderabad", "pune", "chennai",
        "noida", "gurgaon", "gurugram", "visakhapatnam",
        "kakinada", "vijayawada",
    )):
        return "india"

    if any(term in loc for term in (
        "united kingdom", " uk ", "london", "england",
    )):
        return "uk"

    if any(term in loc for term in (
        "canada", "toronto", "vancouver",
    )):
        return "canada"

    if any(term in loc for term in (
        "australia", "sydney", "melbourne",
    )):
        return "australia"

    # Don't silently default an unspecified location to USA.
    return "india"


def search_jobs(scraper_name, keyword, location):
    """Execute one scraper without requiring an AI agent."""

    try:
        from scraper import (
            JobSpyScraper,
            LinkedInPlaywrightScraper,
            SearxNGCrawl4aiScraper,
            RSSJobScraper,
            YCScraper,
        )

        if scraper_name == "jobspy":
            country = get_jobspy_country(location)
            jobs = []

            for site in ["indeed", "linkedin"]:
                try:
                    results = JobSpyScraper(
                        site_name=site,
                        country=country,
                    ).search(keyword, location)

                    jobs.extend(results or [])

                    logger.info(
                        "JobSpy [%s] '%s': %s jobs",
                        site,
                        keyword,
                        len(results or []),
                    )

                except Exception as e:
                    logger.error("JobSpy %s failed: %s", site, e)

            return jobs

        if scraper_name == "playwright":
            return LinkedInPlaywrightScraper().search(
                keyword, location
            )

        if scraper_name == "searxng":
            return SearxNGCrawl4aiScraper().search(
                keyword, location
            )

        if scraper_name == "rss":
            return RSSJobScraper().search(
                keyword, location
            )

        if scraper_name == "yc":
            return YCScraper().search(
                keyword, location
            )

    except Exception as e:
        logger.exception(
            "Scraper %s failed for keyword %s: %s",
            scraper_name, keyword, e
        )

    return []


def deploy_job_hunt_agency(
    keywords_list: list,
    location: str,
    resume_text: str,
    user_prompt: str = "",
) -> tuple:
    """
    Execute job scrapers directly.

    Pipeline:
        1. Run scrapers concurrently.
        2. Collect job listings.
        3. Remove duplicates.
        4. Apply role and location filtering.
        5. Calculate ATS scores.

    Returns:
        summary, scored_jobs, raw_jobs
    """

    all_scraped_jobs = []

    scraper_names = [
        "jobspy",
        "playwright",
        "rss",
        "yc",
    ]

    tasks = [
        (scraper_name, keyword, location)
        for keyword in keywords_list
        for scraper_name in scraper_names
    ]

    logger.info(
        "Starting %s scraper tasks for %s keywords",
        len(tasks), len(keywords_list)
    )

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(
                search_jobs,
                scraper_name,
                keyword,
                location,
            ): (scraper_name, keyword)
            for scraper_name, keyword, location in tasks
        }

        for future in as_completed(futures):
            scraper_name, keyword = futures[future]

            try:
                jobs = future.result() or []

                if isinstance(jobs, list):
                    all_scraped_jobs.extend(jobs)

                logger.info(
                    "%s completed for '%s': %s jobs",
                    scraper_name,
                    keyword,
                    len(jobs),
                )

            except Exception as e:
                logger.error(
                    "%s failed for '%s': %s",
                    scraper_name,
                    keyword,
                    e,
                )

    # Deduplicate listings.
    seen = set()
    raw_jobs = []

    for job in all_scraped_jobs:
        if not isinstance(job, dict):
            continue

        title = str(job.get("title", "")).strip()
        company = str(job.get("company", "")).strip()

        if not title:
            continue

        key = f"{title.lower()}|{company.lower()}"

        if key not in seen:
            seen.add(key)
            raw_jobs.append(job)

    logger.info(
        "Unique jobs before filtering: %s",
        len(raw_jobs),
    )

    # Apply role, experience, and location filtering.
    from job_filter import filter_and_rank_jobs

    filtered_jobs = filter_and_rank_jobs(
        jobs=raw_jobs,
        keywords_list=keywords_list,
        location=location,
    )

    logger.info(
        "Jobs after balanced filtering: %s",
        len(filtered_jobs),
    )

    if not filtered_jobs:
        return (
            "No relevant jobs were found. Try different keywords "
            "or check scraper availability.",
            [],
            [],
        )

    # Score only filtered jobs.
    from ats_scorer import score_all_jobs

    scored_jobs = score_all_jobs(
        resume_text,
        filtered_jobs,
    )

    logger.info(
        "ATS scoring completed: %s jobs",
        len(scored_jobs),
    )

    summary = (
        f"**{len(scored_jobs)} relevant jobs** found and scored.\n"
        "- Jobs are filtered by role, experience, and location.\n"
        "- Jobs are ranked by resume match score.\n"
    )

    return summary, scored_jobs, filtered_jobs
