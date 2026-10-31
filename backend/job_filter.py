
import re
import logging
from typing import Any

logger = logging.getLogger(__name__)


SENIOR_TERMS = {
    "senior", "sr.", "sr ", "staff", "principal",
    "director", "vice president", "vp ",
    "architect", "engineering manager"
}

NON_TECHNICAL_TERMS = {
    "marketing", "sales executive", "telecaller",
    "recruiter", "human resources", "hr executive",
    "business development", "account executive"
}

ENTRY_LEVEL_TERMS = {
    "intern", "internship", "fresher", "entry level",
    "junior", "graduate", "trainee", "associate"
}

ROLE_CONFIG = {
    "python": {
        "roles": {
            "python developer",
            "python engineer",
            "python backend developer",
            "python development",
        },
        "related": {
            "backend developer",
            "software developer",
            "software engineer",
        },
        "skills": {
            "python", "fastapi", "flask", "django",
            "sql", "rest api",
        },
        "exclude_roles": {
            "data scientist", "data science",
            "data analyst", "data analytics",
            "machine learning engineer",
            "ai engineer", "artificial intelligence",
            "generative ai",
        },
    },

    "generative ai": {
        "roles": {
            "generative ai", "genai", "llm",
            "rag developer", "prompt engineer",
            "ai agent developer",
        },
        "related": {
            "python developer", "ai engineer",
            "machine learning engineer",
        },
        "skills": {
            "python", "llm", "rag", "langchain",
            "generative ai", "genai",
            "prompt engineering", "llm api",
        },
        "exclude_roles": set(),
    },

    "machine learning": {
        "roles": {
            "machine learning", "ml engineer",
            "ai engineer", "artificial intelligence",
        },
        "related": {
            "data scientist", "python developer",
        },
        "skills": {
            "python", "machine learning",
            "deep learning", "scikit-learn",
            "tensorflow", "pytorch", "pandas",
        },
        "exclude_roles": set(),
    },

    "full stack": {
        "roles": {
            "full stack", "fullstack",
            "react developer", "web developer",
        },
        "related": {
            "frontend developer", "backend developer",
            "software developer",
        },
        "skills": {
            "react", "javascript", "typescript",
            "node.js", "express", "mongodb",
            "html", "css", "rest api",
        },
        "exclude_roles": set(),
    },

    "data analyst": {
        "roles": {
            "data analyst", "data analytics",
            "business analyst",
        },
        "related": {
            "sql analyst", "reporting analyst",
        },
        "skills": {
            "sql", "python", "excel",
            "power bi", "tableau", "pandas",
        },
        "exclude_roles": set(),
    },

    "software engineer": {
        "roles": {
            "software engineer", "software developer",
            "sde", "application developer",
        },
        "related": {
            "backend developer", "frontend developer",
            "full stack developer",
        },
        "skills": {
            "python", "java", "javascript",
            "sql", "api", "data structures",
        },
        "exclude_roles": set(),
    },
}

EXPERIENCE_PATTERNS = [
    r"\b(\d+)\s*[-–]\s*(\d+)\s*years?\s+(?:of\s+)?experience\b",
    r"\b(\d+)\+?\s*years?\s+(?:of\s+)?experience\b",
    r"\bminimum\s+(\d+)\s+years?\b",
    r"\bat\s+least\s+(\d+)\s+years?\b",
]

MAX_ENTRY_LEVEL_EXPERIENCE = 1


def normalize(text: str) -> str:
    return re.sub(
        r"[^a-z0-9+#.\s]",
        " ",
        str(text).lower()
    )


def contains_term(text: str, term: str) -> bool:
    pattern = (
        r"(?<!\w)"
        + re.escape(term.lower())
        + r"(?!\w)"
    )
    return bool(re.search(pattern, text))


def get_required_experience(text: str):
    for pattern in EXPERIENCE_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)

        if matches:
            values = []

            for match in matches:
                if isinstance(match, tuple):
                    values.extend(
                        int(value)
                        for value in match
                        if value
                    )
                else:
                    values.append(int(match))

            if values:
                return min(values)

    return None


def filter_and_rank_jobs(
    jobs: list[dict[str, Any]],
    keywords_list: list[str],
    location: str = "Remote India"
) -> list[dict[str, Any]]:

    if not jobs:
        return []

    query = normalize(" ".join(keywords_list))

    # Identify the primary requested domain.
    config = None

    for domain, settings in ROLE_CONFIG.items():
        if contains_term(query, domain):
            config = settings
            break

    # Handle common variations.
    if config is None:
        if contains_term(query, "python"):
            config = ROLE_CONFIG["python"]
        elif any(
            contains_term(query, term)
            for term in ["genai", "llm", "rag"]
        ):
            config = ROLE_CONFIG["generative ai"]
        elif any(
            contains_term(query, term)
            for term in ["ai", "machine learning"]
        ):
            config = ROLE_CONFIG["machine learning"]
        elif any(
            contains_term(query, term)
            for term in ["react", "node", "frontend", "backend"]
        ):
            config = ROLE_CONFIG["full stack"]
        elif contains_term(query, "data"):
            config = ROLE_CONFIG["data analyst"]
        else:
            config = ROLE_CONFIG["software engineer"]

    requested_roles = {
        normalize(term) for term in config["roles"]
    }

    related_roles = {
        normalize(term) for term in config["related"]
    }

    requested_skills = {
        normalize(term) for term in config["skills"]
    }

    excluded_roles = {
        normalize(term) for term in config["exclude_roles"]
    }

    requested_location = normalize(location)

    is_india_search = "india" in requested_location
    is_remote_search = "remote" in requested_location

    foreign_locations = {
        "united states", "usa", "boston",
        "new york", "california", "texas",
        "seattle", "chicago", "united kingdom",
        "london", "canada", "toronto",
        "vancouver", "australia", "sydney"
    }

    results = []
    rejected = 0

    for original_job in jobs:

        job = dict(original_job)

        title = normalize(job.get("title", ""))
        description = normalize(
            job.get("description", "")
        )
        job_location = normalize(
            job.get("location", "")
        )

        if not title.strip():
            rejected += 1
            continue

        # Reject senior positions.
        if any(
            contains_term(title, term)
            for term in SENIOR_TERMS
        ):
            rejected += 1
            continue

        # Reject non-technical positions.
        if any(
            contains_term(title, term)
            for term in NON_TECHNICAL_TERMS
        ):
            rejected += 1
            continue

        # Match primary and related job roles.
        title_matches = [
            role for role in requested_roles
            if contains_term(title, role)
        ]

        related_matches = [
            role for role in related_roles
            if contains_term(title, role)
        ]

        # Reject unrelated job categories.
        excluded_match = any(
            contains_term(title, role)
            for role in excluded_roles
        )

        if excluded_match and not title_matches:
            rejected += 1
            continue

                # Require a matching primary or approved related job title.
        # Description skills alone cannot qualify an unrelated job.
        if not title_matches and not related_matches:
            rejected += 1
            continue

        # For GenAI and AI/ML searches, don't accept generic
        # Python Developer roles based only on shared technical skills.
        if config in (
            ROLE_CONFIG["generative ai"],
            ROLE_CONFIG["machine learning"],
        ):
            generic_python_roles = [
                "python developer",
                "python engineer",
                "python development",
            ]

            if (
                not title_matches
                and any(contains_term(title, role) for role in generic_python_roles)
            ):
                rejected += 1
                continue

        # Ignore placeholder descriptions.
        placeholder_phrases = [
            "description not fetched",
            "no public description available",
            "no description available",
            "scraped via playwright",
            "hackerrank job posting",
        ]

        usable_description = (
            description.strip()
            and not any(
                phrase in description
                for phrase in placeholder_phrases
            )
        )

        description_matches = []

        if usable_description:
            description_matches = [
                skill for skill in requested_skills
                if contains_term(description, skill)
            ]

        # Role-based scoring.
        title_score = 50 if title_matches else 30

        description_score = min(
            len(description_matches) * 5,
            25
        )

        entry_level = any(
            contains_term(title, term)
            for term in ENTRY_LEVEL_TERMS
        )

        experience_score = 15 if entry_level else 0

        # Explicit experience requirements.
        required_experience = get_required_experience(
            f"{title} {description}"
        )

        if (
            required_experience is not None
            and required_experience > MAX_ENTRY_LEVEL_EXPERIENCE
        ):
            rejected += 1
            continue

        # Location filtering.
        location_score = 0

        foreign_match = any(
            contains_term(job_location, term)
            for term in foreign_locations
        )

        if is_india_search and foreign_match:
            rejected += 1
            continue

        has_remote = (
            "remote" in job_location
            or "work from home" in job_location
        )

        india_cities = [
            "india", "bangalore", "bengaluru",
            "hyderabad", "chennai", "pune",
            "mumbai", "delhi", "noida",
            "gurgaon", "gurugram"
        ]

        if is_india_search:
            if has_remote or any(
                contains_term(job_location, city)
                for city in india_cities
            ):
                location_score = 5
            else:
                rejected += 1
                continue

        elif requested_location:
            if contains_term(
                job_location,
                requested_location
            ):
                location_score = 5
            else:
                rejected += 1
                continue

        total_score = min(
            title_score
            + description_score
            + experience_score
            + location_score,
            100
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

    results.sort(
        key=lambda item: item["relevance_score"],
        reverse=True
    )

    logger.info(
        "Role-based filter: %s retained, %s rejected from %s jobs",
        len(results), rejected, len(jobs)
    )

    return results
