
import logging
import re

logger = logging.getLogger(__name__)


# --------------------------------------------------
# ROLE CONFIGURATION
# --------------------------------------------------

ROLE_CONFIG = {
    "Generative AI": {
        "terms": [
            "generative ai",
            "genai",
            "llm",
            "llms",
            "rag",
            "langchain",
            "agentic ai",
            "prompt engineer",
        ],
        "titles": [
            "Generative AI Intern",
            "Generative AI Engineer Fresher",
            "LLM Developer Intern",
            "LLM Engineer Fresher",
            "RAG Developer Intern",
            "AI Agent Developer Intern",
        ],
    },

    "AI/ML": {
        "terms": [
            "artificial intelligence",
            "machine learning",
            "ml engineer",
            "deep learning",
            "ai engineer",
            "ai/ml",
            "aiml",
            "computer vision",
            "nlp engineer",
            "machine learning engineer",
            "ai developer",
            "artificial intelligence developer",
        ],
        "titles": [
            "AI Developer Intern",
            "AI Developer Fresher",
            "Junior AI Developer",
            "Artificial Intelligence Developer Intern",
            "AI/ML Engineer Intern",
            "AI/ML Engineer Fresher",
            "AI Engineer Intern",
            "AI Engineer Fresher",
            "Machine Learning Intern",
            "Machine Learning Engineer Fresher",
            "ML Engineer Intern",
            "ML Engineer Fresher",
            "Deep Learning Intern",
            "Computer Vision Intern",
            "NLP Engineer Intern",
            "Junior Machine Learning Engineer",
        ],
    },

    "Data Science": {
        "terms": [
            "data science",
            "data scientist",
            "data science intern",
        ],
        "titles": [
            "Data Science Intern",
            "Junior Data Scientist",
            "Data Scientist Fresher",
        ],
    },

    "Data Analytics": {
        "terms": [
            "data analyst",
            "data analytics",
            "business analyst",
            "power bi",
            "tableau",
        ],
        "titles": [
            "Data Analyst Intern",
            "Business Analyst Intern",
            "SQL Analyst Fresher",
            "Junior Data Analyst",
        ],
    },

    "SQL": {
        "terms": [
            "sql developer",
            "sql",
            "mysql",
            "postgresql",
            "database developer",
        ],
        "titles": [
            "SQL Developer Fresher",
            "SQL Developer Intern",
            "Junior Database Developer",
        ],
    },

    "Python": {
        "terms": [
            "python developer",
            "python engineer",
            "python",
            "django",
            "fastapi",
            "flask",
        ],
        "titles": [
            "Python Developer Intern",
            "Python Developer Fresher",
            "Junior Python Developer",
        ],
    },

    "Full Stack": {
        "terms": [
            "full stack",
            "fullstack",
            "mern",
            "react",
            "node.js",
            "frontend",
            "backend",
            "web developer",
        ],
        "titles": [
            "React Developer Intern",
            "Full Stack Developer Intern",
            "Frontend Developer Fresher",
            "Backend Developer Intern",
        ],
    },

    "Salesforce": {
        "terms": [
            "salesforce",
            "salesforce developer",
            "salesforce administrator",
            "salesforce admin",
            "apex developer",
            "salesforce crm",
        ],
        "titles": [
            "Salesforce Developer Intern",
            "Salesforce Developer Fresher",
            "Junior Salesforce Developer",
            "Salesforce Admin Intern",
            "Salesforce Administrator Fresher",
            "Salesforce CRM Developer",
            "Apex Developer Intern",
        ],
    },

    "Software Development": {
        "terms": [
            "software engineer",
            "software developer",
            "sde",
            "developer",
        ],
        "titles": [
            "Software Developer Intern",
            "Software Engineer Fresher",
            "Junior Software Engineer",
        ],
    },
}


# --------------------------------------------------
# TEXT HELPERS
# --------------------------------------------------

def normalize_text(text: str) -> str:
    """
    Normalize text for reliable keyword matching.
    """

    text = str(text or "").lower()

    text = re.sub(
        r"[^a-z0-9+#./\s-]",
        " ",
        text,
    )

    return re.sub(r"\s+", " ", text).strip()


def contains_phrase(text: str, phrase: str) -> bool:
    """
    Check for a phrase using word boundaries.
    """

    text = normalize_text(text)
    phrase = normalize_text(phrase)

    if not text or not phrase:
        return False

    pattern = (
        r"(?<!\w)"
        + re.escape(phrase)
        + r"(?!\w)"
    )

    return bool(re.search(pattern, text))


# --------------------------------------------------
# LOCATION EXTRACTION
# --------------------------------------------------

def extract_location(text: str) -> str:
    text = normalize_text(text)

    # Explicit remote searches
    if re.search(r"\bremote\s+india\b", text):
        return "Remote India"

    if re.search(
        r"\bremote\b|\bwork\s+from\s+home\b|\bwfh\b",
        text,
    ):
        return "Remote India"

    cities = [
        "bangalore",
        "bengaluru",
        "hyderabad",
        "chennai",
        "pune",
        "mumbai",
        "delhi",
        "noida",
        "gurgaon",
        "gurugram",
        "kolkata",
        "visakhapatnam",
        "kakinada",
        "rajahmundry",
        "rajahmahendravaram",
        "vizianagaram",
    ]

    for city in cities:
        if contains_phrase(text, city):
            return city.title()

    if contains_phrase(text, "india"):
        return "India"

    return "Remote India"


# --------------------------------------------------
# DOMAIN DETECTION
# --------------------------------------------------

def detect_domains(text: str) -> list[str]:
    """
    Detect job domains requested by the user.

    Important:
    AI/ML searches should not automatically become
    Python Developer searches.
    """

    text = normalize_text(text)

    detected_domains = []

    # Check more specific domains first.
    domain_priority = [
        "Generative AI",
        "Salesforce",
        "AI/ML",
        "Data Science",
        "Data Analytics",
        "Full Stack",
        "SQL",
        "Python",
        "Software Development",
    ]

    for domain in domain_priority:
        config = ROLE_CONFIG[domain]

        if any(
            contains_phrase(text, term)
            for term in config["terms"]
        ):
            detected_domains.append(domain)

    # Remove generic software development when a
    # specific domain has already been detected.
    specific_domains = {
        "Generative AI",
        "Salesforce",
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

    # Remove Python from an AI/ML query when Python
    # was mentioned only as a supporting technology.
    if "AI/ML" in detected_domains:
        if not contains_phrase(text, "python developer"):
            detected_domains = [
                domain
                for domain in detected_domains
                if domain != "Python"
            ]

    # A GenAI search should not become a generic Python search.
    if "Generative AI" in detected_domains:
        if not contains_phrase(text, "python developer"):
            detected_domains = [
                domain
                for domain in detected_domains
                if domain != "Python"
            ]

    return detected_domains


# --------------------------------------------------
# SEARCH DETAIL EXTRACTION
# --------------------------------------------------

def extract_search_details(
    message: str,
    resume_text: str = "",
):
    """
    Extract job domains, search titles, and location.

    This function uses deterministic Python and does not
    require an external AI API.
    """

    text = normalize_text(message)

    location = extract_location(text)

    detected_domains = detect_domains(text)

    # Do not silently default unknown queries to Python.
    if not detected_domains:
        detected_domains = ["Software Development"]

    job_titles = []

    for domain in detected_domains:
        job_titles.extend(
            ROLE_CONFIG[domain]["titles"]
        )

    # Remove duplicate titles while preserving order.
    job_titles = list(
        dict.fromkeys(job_titles)
    )

    logger.info(
        "Detected domains: %s | Job titles: %s | Location: %s",
        detected_domains,
        job_titles,
        location,
    )

    return job_titles, location


# --------------------------------------------------
# MAIN AGENT
# --------------------------------------------------

def run_agent(
    message: str,
    resume_text: str = "",
) -> tuple:

    """
    1. Extract job keywords.
    2. Execute job scrapers.
    3. Return job results.
    """

    try:
        keywords_list, location = extract_search_details(
            message,
            resume_text,
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
            f"`{keyword}`"
            for keyword in keywords_list
        )

        reply = (
            "### Job Hunt Complete\n"
            f"**Searched:** {keywords_display} in `{location}`\n"
            f"**Matched jobs:** {len(jobs_list)} relevant postings found\n\n"
            f"{markdown_summary}"
        )

        return reply, jobs_list, raw_jobs_list

    except Exception as error:
        logger.error(
            "Job Hunt Agent error: %s",
            error,
            exc_info=True,
        )

        return (
            f"The job search encountered an execution error: {str(error)}",
            [],
            [],
        )
