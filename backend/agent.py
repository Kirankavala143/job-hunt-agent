
import logging
import re

logger = logging.getLogger(__name__)


ROLE_CONFIG = {
    "Generative AI": {
        "terms": [
            "generative ai", "genai", "llm", "rag",
            "langchain", "agentic ai", "prompt engineer"
        ],
        "titles": [
            "Generative AI Intern",
            "LLM Developer Intern",
            "RAG Developer Intern",
        ],
    },
    "AI/ML": {
        "terms": [
            "artificial intelligence", "machine learning",
            "ml engineer", "deep learning", "ai engineer",
            "ai/ml"
        ],
        "titles": [
            "AI Engineer Intern",
            "Machine Learning Intern",
            "ML Engineer Fresher",
        ],
    },
    "Data Science": {
        "terms": [
            "data science", "data scientist",
            "data science intern"
        ],
        "titles": [
            "Data Science Intern",
            "Junior Data Scientist",
        ],
    },
    "Data Analytics": {
        "terms": [
            "data analyst", "data analytics",
            "business analyst", "power bi", "tableau"
        ],
        "titles": [
            "Data Analyst Intern",
            "Business Analyst Intern",
            "SQL Analyst Fresher",
        ],
    },
    "SQL": {
        "terms": [
            "sql developer", "sql", "mysql",
            "postgresql", "database developer"
        ],
        "titles": [
            "SQL Developer Fresher",
            "SQL Developer Intern",
            "Junior Database Developer",
        ],
    },
    "Python": {
        "terms": [
            "python developer", "python engineer",
            "python", "django", "fastapi", "flask"
        ],
        "titles": [
            "Python Developer Intern",
            "Python Developer Fresher",
        ],
    },
    "Full Stack": {
        "terms": [
            "full stack", "mern", "react", "node.js",
            "frontend", "backend", "web developer"
        ],
        "titles": [
            "React Developer Intern",
            "Full Stack Developer Intern",
            "Frontend Developer Fresher",
        ],
    },
    "Software Development": {
        "terms": [
            "software engineer", "software developer",
            "sde", "developer"
        ],
        "titles": [
            "Software Developer Intern",
            "Software Engineer Fresher",
        ],
    },
}


def contains_phrase(text: str, phrase: str) -> bool:
    pattern = r"(?<!\w)" + re.escape(phrase.lower()) + r"(?!\w)"
    return bool(re.search(pattern, text))


def extract_location(text: str) -> str:
    text = text.lower()

    # Explicit remote searches
    if re.search(r"\bremote\s+india\b", text):
        return "Remote India"

    if re.search(r"\bremote\b|\bwork\s+from\s+home\b|\bwfh\b", text):
        return "Remote India"

    cities = [
        "bangalore", "bengaluru", "hyderabad",
        "chennai", "pune", "mumbai", "delhi",
        "noida", "gurgaon", "gurugram", "kolkata",
        "visakhapatnam", "kakinada", "rajahmundry"
    ]

    for city in cities:
        if contains_phrase(text, city):
            return city.title()

    if contains_phrase(text, "india"):
        return "India"

    return "Remote India"



def extract_search_details(message: str, resume_text: str = ""):
    """
    Extract job domains and location using deterministic Python.
    No external AI API required.
    """

    text = message.lower().strip()
    location = extract_location(text)

    detected_domains = []

    for domain, config in ROLE_CONFIG.items():
        if any(
            contains_phrase(text, term)
            for term in config["terms"]
        ):
            detected_domains.append(domain)

    # Avoid adding generic software roles when a specific
    # developer domain has already been identified.
    specific_domains = {
        "Generative AI",
        "AI/ML",
        "Data Science",
        "Data Analytics",
        "SQL",
        "Python",
        "Full Stack",
    }

    if "Software Development" in detected_domains:
        if any(
            domain in detected_domains
            for domain in specific_domains
        ):
            detected_domains.remove("Software Development")

    if not detected_domains:
        detected_domains = ["Python"]

    job_titles = []

    for domain in detected_domains:
        job_titles.extend(ROLE_CONFIG[domain]["titles"])

    job_titles = list(dict.fromkeys(job_titles))

    logger.info(
        "Detected domains: %s | Job titles: %s | Location: %s",
        detected_domains,
        job_titles,
        location,
    )

    return job_titles, location



def run_agent(message: str, resume_text: str = "") -> tuple:
    """
    1. Extract job keywords.
    2. Execute job scrapers.
    3. Return job results.
    """

    try:
        keywords_list, location = extract_search_details(
            message,
            resume_text
        )

        from crew_agency import deploy_job_hunt_agency

        markdown_summary, jobs_list, raw_jobs_list = (
            deploy_job_hunt_agency(
                keywords_list=keywords_list,
                location=location,
                resume_text=resume_text,
                user_prompt=message,
            )
        )

        keywords_display = ", ".join(
            f"`{keyword}`" for keyword in keywords_list
        )

        reply = (
            "### Job Hunt Complete\n"
            f"**Searched:** {keywords_display} in `{location}`\n"
            f"**Matched jobs:** {len(jobs_list)} relevant postings found\n\n"
            f"{markdown_summary}"
        )

        return reply, jobs_list, raw_jobs_list

    except Exception as e:
        logger.error(
            "Job Hunt Agent error: %s",
            e,
            exc_info=True
        )

        return (
            f"The job search encountered an execution error: {str(e)}",
            [],
            [],
        )
