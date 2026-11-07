
import re
import logging
from typing import Any

logger = logging.getLogger(__name__)

SENIOR_TERMS = {
    "senior", "sr.", "sr ", "staff", "principal", "director",
    "vice president", "vp ", "architect", "engineering manager",
    "lead engineer", "tech lead", "team lead", "staff engineer",
    "senior engineer", "senior scientist", "lead scientist",
    "distinguished", "fellow",
}

# Common job-grade suffixes used for experienced positions (e.g. Engineer IV).
SENIOR_GRADE_PATTERN = re.compile(
    r"\b(?:engineer|scientist|developer|analyst)\s*[-,]?\s*(?:iii|iv|v|vi|3|4|5|6)\b",
    re.IGNORECASE,
)

NON_TECHNICAL_TERMS = {
    "marketing", "sales executive", "telecaller", "recruiter",
    "human resources", "hr executive", "business development",
    "account executive",
}

ENTRY_LEVEL_TERMS = {
    "intern", "internship", "fresher", "entry level", "junior",
    "graduate", "trainee", "associate",
}

ROLE_CONFIG = {
    "python": {
        "roles": {
            "python developer", "python engineer",
            "python backend developer", "python development",
        },
        "related": {
            "backend developer", "software developer",
            "software engineer", "python programmer",
        },
        "skills": {
            "python", "fastapi", "flask", "django", "sql", "rest api",
        },
        "exclude_roles": {
            "data scientist", "data science", "data analyst",
            "data analytics", "machine learning engineer",
            "ai engineer", "artificial intelligence", "generative ai",
            "ml engineer", "deep learning",
        },
    },

    "generative ai": {
        "roles": {
            "generative ai", "genai", "llm engineer",
            "llm developer", "rag developer", "prompt engineer",
            "ai agent developer", "generative ai engineer",
            "gen ai engineer", "large language model",
        },
        "related": {
            "ai engineer", "machine learning engineer",
            "ml engineer", "nlp engineer",
        },
        "skills": {
            "python", "llm", "rag", "langchain", "generative ai",
            "genai", "prompt engineering", "llm api", "vector database",
            "embedding", "llamaindex",
        },
        "exclude_roles": {
            "python developer", "python engineer",
            "python backend developer",
        },
    },

    "machine learning": {
        "roles": {
            "machine learning", "machine learning engineer",
            "ml engineer", "ai developer", "artificial intelligence developer",
            "ai engineer", "artificial intelligence",
            "ai/ml engineer", "ai ml engineer", "deep learning engineer",
            "computer vision engineer", "nlp engineer",
            "machine learning intern", "ml intern", "ai intern",
            "deep learning intern", "computer vision intern",
            "research engineer", "research scientist",
        },
        "related": {
            "data scientist", "applied scientist",
            "machine learning researcher",
        },
        "skills": {
            "python", "machine learning", "deep learning",
            "scikit-learn", "tensorflow", "pytorch", "pandas",
            "numpy", "computer vision", "nlp", "model training",
        },
        "exclude_roles": {
            "python developer", "python engineer",
            "python backend developer", "python development",
            "backend developer", "software developer",
            "software engineer",
        },
    },

    "full stack": {
        "roles": {
            "full stack", "fullstack", "react developer",
            "web developer", "full stack developer",
        },
        "related": {
            "frontend developer", "backend developer",
            "software developer",
        },
        "skills": {
            "react", "javascript", "typescript", "node.js",
            "express", "mongodb", "html", "css", "rest api",
        },
        "exclude_roles": set(),
    },

    "data analyst": {
        "roles": {
            "data analyst", "data analytics", "business analyst",
        },
        "related": {"sql analyst", "reporting analyst"},
        "skills": {
            "sql", "python", "excel", "power bi", "tableau", "pandas",
        },
        "exclude_roles": set(),
    },

    "salesforce": {
        "roles": {
            "salesforce", "salesforce developer", "salesforce administrator",
            "salesforce admin", "salesforce crm developer", "apex developer",
            "salesforce consultant", "salesforce engineer",
        },
        "related": {
            "salesforce intern", "crm developer", "apex engineer",
        },
        "skills": {
            "salesforce", "apex", "visualforce", "lightning web components",
            "lwc", "salesforce crm", "soql", "sosl", "salesforce flow",
        },
        "exclude_roles": {
            "software developer", "software engineer", "python developer",
            "web developer", "data analyst",
        },
    },

    "software engineer": {
        "roles": {
            "software engineer", "software developer", "sde",
            "application developer",
        },
        "related": {
            "backend developer", "frontend developer",
            "full stack developer",
        },
        "skills": {
            "python", "java", "javascript", "sql", "api",
            "data structures",
        },
        "exclude_roles": set(),
    },
}

EXPERIENCE_PATTERNS = [
    r"\b(\d+)\s*[-–]\s*(\d+)\s*years?\s+(?:of\s+)?experience\b",
    r"\b(\d+)\+?\s*years?\s+(?:of\s+)?experience\b",
    r"\bminimum\s+(\d+)\s+years?\b",
    r"\bat\s+least\s+(\d+)\s+years?\b",
    r"\b(\d+)\+\s*years?\b",
]

MAX_ENTRY_LEVEL_EXPERIENCE = 1

FOREIGN_LOCATIONS = {
    "united states", "usa", "boston", "new york", "california",
    "texas", "seattle", "chicago", "united kingdom", "london",
    "canada", "toronto", "vancouver", "australia", "sydney",
}

INDIA_CITIES = {
    "india", "bangalore", "bengaluru", "hyderabad", "chennai",
    "pune", "mumbai", "delhi", "noida", "gurgaon", "gurugram",
    "vizag", "visakhapatnam", "vijayawada", "vizianagaram",
    "kolkata", "kochi", "coimbatore", "ahmedabad", "jaipur",
}


def normalize(text: str) -> str:
    """Normalize text while retaining common technical symbols."""
    return re.sub(r"[^a-z0-9+#.\s]", " ", str(text or "").lower())


def contains_term(text: str, term: str) -> bool:
    """Match a term at word boundaries."""
    text = normalize(text)
    term = normalize(term).strip()

    if not term:
        return False

    pattern = r"(?<!\w)" + re.escape(term) + r"(?!\w)"
    return bool(re.search(pattern, text))


def get_required_experience(text: str):
    """Return the smallest explicit experience requirement found."""
    for pattern in EXPERIENCE_PATTERNS:
        matches = re.findall(pattern, text or "", re.IGNORECASE)
        values = []

        for match in matches:
            if isinstance(match, tuple):
                values.extend(int(value) for value in match if value)
            else:
                values.append(int(match))

        if values:
            return min(values)

    return None


def _identify_role_config(query: str) -> dict[str, Any]:
    """Identify the requested role; specific AI terms take precedence."""
    q = normalize(query)

    # Prioritize specific role families over generic terms such as developer.
    if any(contains_term(q, term) for term in (
        "salesforce", "apex developer", "salesforce crm",
    )):
        return ROLE_CONFIG["salesforce"]

    if any(contains_term(q, term) for term in (
        "generative ai", "genai", "gen ai", "llm", "rag",
        "prompt engineer", "ai agent",
    )):
        return ROLE_CONFIG["generative ai"]

    if any(contains_term(q, term) for term in (
        "machine learning", "ml engineer", "ai engineer", "ai developer",
        "artificial intelligence developer", "artificial intelligence",
        "ai/ml", "aiml", "deep learning",
        "computer vision", "nlp engineer",
    )):
        return ROLE_CONFIG["machine learning"]

    if any(contains_term(q, term) for term in (
        "full stack", "fullstack", "react", "node", "frontend",
        "backend", "web developer",
    )):
        return ROLE_CONFIG["full stack"]

    if any(contains_term(q, term) for term in (
        "data analyst", "data analytics", "business analyst",
    )):
        return ROLE_CONFIG["data analyst"]

    if contains_term(q, "python"):
        return ROLE_CONFIG["python"]

    if any(contains_term(q, term) for term in (
        "software engineer", "software developer", "sde",
    )):
        return ROLE_CONFIG["software engineer"]

    return ROLE_CONFIG["software engineer"]


def filter_and_rank_jobs(
    jobs: list[dict[str, Any]],
    keywords_list: list[str],
    location: str = "Remote India",
    user_prompt: str = "",
) -> list[dict[str, Any]]:
    """
    Filter jobs by role title, experience, and location, then rank them.

    Important: for AI/ML and GenAI, a generic Python title does not qualify
    unless it also contains a recognized AI/ML or GenAI title.
    """
    if not jobs:
        return []

    # The user's exact request is the source of truth. Generated scraper
    # keywords may contain broad terms or omit the requested role name.
    query = normalize(user_prompt or " ".join(keywords_list))
    config = _identify_role_config(query)

    requested_roles = {normalize(term) for term in config["roles"]}
    related_roles = {normalize(term) for term in config["related"]}
    requested_skills = {normalize(term) for term in config["skills"]}
    excluded_roles = {normalize(term) for term in config["exclude_roles"]}

    requested_location = normalize(location)
    is_india_search = "india" in requested_location
    is_remote_search = "remote" in requested_location

    results = []
    rejected = 0

    for original_job in jobs:
        job = dict(original_job)
        title = normalize(job.get("title", ""))
        description = normalize(job.get("description", ""))
        job_location = normalize(job.get("location", ""))

        if not title.strip():
            rejected += 1
            continue

        # Exclude senior/staff/lead titles and higher job grades such as Engineer IV.
        if (
            any(contains_term(title, term) for term in SENIOR_TERMS)
            or SENIOR_GRADE_PATTERN.search(title)
        ):
            rejected += 1
            continue

        if any(contains_term(title, term) for term in NON_TECHNICAL_TERMS):
            rejected += 1
            continue

        title_matches = [
            role for role in requested_roles if contains_term(title, role)
        ]

        related_matches = [
            role for role in related_roles if contains_term(title, role)
        ]

        # A title in an excluded category is rejected unless it also directly
        # matches a requested primary title.
        excluded_match = any(
            contains_term(title, role) for role in excluded_roles
        )

        if excluded_match and not title_matches:
            rejected += 1
            continue

        # Job title must match the requested role or an approved related role.
        if not title_matches and not related_matches:
            rejected += 1
            continue

        # Explicitly prevent generic Python jobs from being treated as AI/ML.
        if config is ROLE_CONFIG["machine learning"]:
            has_ai_ml_title = any(
                contains_term(title, role) for role in requested_roles
            )

            if not has_ai_ml_title:
                rejected += 1
                continue

        if config is ROLE_CONFIG["generative ai"]:
            has_genai_title = any(
                contains_term(title, role) for role in requested_roles
            )

            if not has_genai_title:
                rejected += 1
                continue

        placeholder_phrases = (
            "description not fetched",
            "no public description available",
            "no description available",
            "scraped via playwright",
            "hackerrank job posting",
        )

        usable_description = bool(description.strip()) and not any(
            phrase in description for phrase in placeholder_phrases
        )

        description_matches = []

        if usable_description:
            description_matches = [
                skill for skill in requested_skills
                if contains_term(description, skill)
            ]

        title_score = 50 if title_matches else 30
        description_score = min(len(description_matches) * 5, 25)

        entry_level = any(
            contains_term(title, term) for term in ENTRY_LEVEL_TERMS
        )

        experience_score = 15 if entry_level else 0

        required_experience = get_required_experience(
            f"{title} {description}"
        )

        if (
            required_experience is not None
            and required_experience > MAX_ENTRY_LEVEL_EXPERIENCE
        ):
            rejected += 1
            continue

        location_score = 0

        foreign_match = any(
            contains_term(job_location, term) for term in FOREIGN_LOCATIONS
        )

        if is_india_search and foreign_match:
            rejected += 1
            continue

        has_remote = (
            "remote" in job_location or "work from home" in job_location
        )

        if is_india_search:
            if has_remote or any(
                contains_term(job_location, city) for city in INDIA_CITIES
            ):
                location_score = 5
            else:
                rejected += 1
                continue

        elif is_remote_search:
            if has_remote:
                location_score = 5
            else:
                rejected += 1
                continue

        elif requested_location:
            if contains_term(job_location, requested_location):
                location_score = 5
            else:
                rejected += 1
                continue

        total_score = min(
            title_score + description_score + experience_score + location_score,
            100,
        )

        if total_score < 20:
            rejected += 1
            continue

        job["relevance_score"] = total_score
        job["relevance_reasons"] = {
            "title_matches": title_matches,
            "related_matches": related_matches,
            "description_matches": description_matches,
            "entry_level": entry_level,
            "required_experience": required_experience,
        }

        results.append(job)

    results.sort(key=lambda item: item["relevance_score"], reverse=True)

    logger.info(
        "Role-based filter (%s): %s retained, %s rejected from %s jobs",
        " ".join(config["roles"]),
        len(results),
        rejected,
        len(jobs),
    )

    return results
