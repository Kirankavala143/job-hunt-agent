import re
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


# --------------------------------------------------
# SKILLS VOCABULARY
# --------------------------------------------------

SKILLS_VOCAB = {
    "python", "javascript", "typescript", "java", "c++", "c#",
    "html", "css", "react", "next.js", "node.js", "express",
    "fastapi", "flask", "django", "tailwind",
    "sql", "mysql", "postgresql", "mongodb", "redis",
    "machine learning", "deep learning", "artificial intelligence",
    "generative ai", "llm", "rag", "nlp",
    "langchain", "langgraph", "prompt engineering",
    "computer vision", "tensorflow", "pytorch",
    "scikit-learn", "pandas", "numpy", "matplotlib", "seaborn",
    "power bi", "tableau", "excel",
    "docker", "kubernetes", "aws", "azure", "gcp",
    "git", "github", "rest api",
    "data science", "data analytics", "data analysis",
    "statistics", "data visualization",
}

SYNONYMS = {
    "reactjs": "react",
    "react.js": "react",
    "nodejs": "node.js",
    "node": "node.js",
    "genai": "generative ai",
    "ml": "machine learning",
    "dl": "deep learning",
    "llms": "llm",
    "postgres": "postgresql",
    "sklearn": "scikit-learn",
    "powerbi": "power bi",
}

# Specialized skills are weighted higher than general tools.
SKILL_WEIGHTS = {
    "python": 1.0, "javascript": 1.0, "typescript": 1.0,
    "java": 1.0, "sql": 1.0,
    "html": 0.5, "css": 0.5, "git": 0.5,
    "github": 0.5, "excel": 0.5,
    "machine learning": 1.5, "deep learning": 1.5,
    "artificial intelligence": 1.5, "generative ai": 1.5,
    "llm": 1.5, "rag": 1.5, "nlp": 1.5,
    "computer vision": 1.5, "tensorflow": 1.5,
    "pytorch": 1.5, "scikit-learn": 1.5,
    "langchain": 1.5, "langgraph": 1.5,
    "prompt engineering": 1.5,
}

DESCRIPTION_FIELDS = (
    "description", "job_description", "jobDescription",
    "snippet", "summary", "details", "requirements",
    "qualifications", "responsibilities", "content",
)


# --------------------------------------------------
# TEXT NORMALIZATION AND SKILL EXTRACTION
# --------------------------------------------------

def normalize(text: str) -> str:
    text = str(text or "").lower()
    for alias, canonical in SYNONYMS.items():
        text = re.sub(
            r"(?<!\w)" + re.escape(alias) + r"(?!\w)",
            canonical,
            text,
        )
    return re.sub(r"[^\w+#.\s-]", " ", text)


def contains_skill(text: str, skill: str) -> bool:
    return bool(re.search(
        r"(?<!\w)" + re.escape(skill) + r"(?!\w)",
        text,
    ))


def extract_skills(text: str) -> set:
    normalized = normalize(text)
    return {
        skill for skill in SKILLS_VOCAB
        if contains_skill(normalized, skill)
    }


def get_skill_weight(skill: str) -> float:
    return SKILL_WEIGHTS.get(skill, 1.0)


# --------------------------------------------------
# DESCRIPTION EXTRACTION
# --------------------------------------------------

def value_to_text(value: Any) -> str:
    """Convert strings, lists, and dictionaries to readable text."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return " ".join(
            value_to_text(item) for item in value if item is not None
        )
    if isinstance(value, dict):
        return " ".join(
            value_to_text(item) for item in value.values()
            if item is not None
        )
    return str(value)


def get_job_description(job: Dict[str, Any]) -> str:
    """Combine available description-related fields from scraper output."""
    parts = []
    for field in DESCRIPTION_FIELDS:
        value = value_to_text(job.get(field))
        if value:
            parts.append(value)
    return " ".join(dict.fromkeys(parts)).strip()


def get_job_text(job: Dict[str, Any]) -> str:
    title = value_to_text(job.get("title"))
    description = get_job_description(job)
    return " ".join(part for part in (title, description) if part).strip()


def has_job_description(job: Dict[str, Any]) -> bool:
    description = get_job_description(job)
    if not description:
        return False

    normalized = normalize(description)
    placeholder_phrases = (
        "description not fetched",
        "no public description available",
        "no description available",
        "scraped via playwright",
        "hackerrank job posting",
    )
    if any(phrase in normalized for phrase in placeholder_phrases):
        return False

    # Short fragments often contain too little information to score reliably.
    return len(description.split()) >= 15


def classify_job_skills(job_text: str, job_skills: set):
    normalized_text = normalize(job_text)

    # Split description into individual sentences.
    sentences = re.split(r"[.!?;\n]+", normalized_text)

    required_skills = set()
    preferred_skills = set()

    preferred_patterns = [
        r"\bpreferred\b",
        r"\bpreferably\b",
        r"\bnice to have\b",
        r"\bgood to have\b",
        r"\bbonus\b",
        r"\boptional\b",
        r"\bplus\b",
        r"\bdesired\b",
        r"\bfamiliarity with\b",
    ]

    for skill in job_skills:
        skill_sentences = [
            sentence
            for sentence in sentences
            if contains_skill(sentence, skill)
        ]

        is_preferred = any(
            any(
                re.search(pattern, sentence)
                for pattern in preferred_patterns
            )
            for sentence in skill_sentences
        )

        if is_preferred:
            preferred_skills.add(skill)
        else:
            required_skills.add(skill)

    return required_skills, preferred_skills


# --------------------------------------------------
# SKILL MATCHING
# --------------------------------------------------

def calculate_skill_match(
    resume_text: str,
    job_text: str,
) -> Dict[str, Any]:

    # Extract skills from resume and job description.
    resume_skills = extract_skills(resume_text)
    job_skills = extract_skills(job_text)

    # Classify job skills as required or preferred.
    required_skills, preferred_skills = classify_job_skills(
        job_text,
        job_skills,
    )

    # Find matched and missing skills.
    matched_skills = sorted(resume_skills & job_skills)
    missing_skills = sorted(job_skills - resume_skills)
    other_resume_skills = sorted(resume_skills - job_skills)

    matched_required_skills = sorted(
        resume_skills & required_skills
    )

    matched_preferred_skills = sorted(
        resume_skills & preferred_skills
    )

    missing_required_skills = sorted(
        required_skills - resume_skills
    )

    missing_preferred_skills = sorted(
        preferred_skills - resume_skills
    )

    # Required skills receive full weight.
    # Preferred skills receive half weight.
    required_weight = sum(
        get_skill_weight(skill)
        for skill in required_skills
    )

    preferred_weight = sum(
        get_skill_weight(skill) * 0.5
        for skill in preferred_skills
    )

    matched_required_weight = sum(
        get_skill_weight(skill)
        for skill in matched_required_skills
    )

    matched_preferred_weight = sum(
        get_skill_weight(skill) * 0.5
        for skill in matched_preferred_skills
    )

    # Calculate total job and matched weights.
    total_job_weight = required_weight + preferred_weight

    matched_job_weight = (
        matched_required_weight
        + matched_preferred_weight
    )

    # Calculate total resume weight.
    total_resume_weight = sum(
        get_skill_weight(skill)
        for skill in resume_skills
    )

    # Overall job requirement coverage.
    job_requirement_coverage = (
        round(
            matched_job_weight / total_job_weight * 100,
            1,
        )
        if total_job_weight > 0
        else None
    )

    # Candidate skill coverage.
    candidate_skill_coverage = (
        round(
            matched_job_weight / total_resume_weight * 100,
            1,
        )
        if total_resume_weight > 0
        else None
    )

    # Required skill coverage.
    required_skill_coverage = (
        round(
            matched_required_weight / required_weight * 100,
            1,
        )
        if required_weight > 0
        else None
    )

    # Preferred skill coverage.
    preferred_skill_coverage = (
        round(
            matched_preferred_weight / preferred_weight * 100,
            1,
        )
        if preferred_weight > 0
        else None
    )

    return {
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "other_resume_skills": other_resume_skills,

        "required_skills": sorted(required_skills),
        "preferred_skills": sorted(preferred_skills),

        "matched_required_skills": matched_required_skills,
        "matched_preferred_skills": matched_preferred_skills,

        "missing_required_skills": missing_required_skills,
        "missing_preferred_skills": missing_preferred_skills,

        "resume_skill_count": len(resume_skills),
        "job_skill_count": len(job_skills),

        "required_skill_coverage": required_skill_coverage,
        "preferred_skill_coverage": preferred_skill_coverage,

        "job_requirement_coverage": job_requirement_coverage,
        "candidate_skill_coverage": candidate_skill_coverage,
    }


# --------------------------------------------------
# SEMANTIC SCORE
# --------------------------------------------------

def semantic_score_bulk(
    resume_text: str,
    job_texts: List[str],
) -> List[float]:
    if not resume_text.strip():
        return [0.0] * len(job_texts)
    if not job_texts:
        return []

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        docs = [resume_text] + job_texts
        vectorizer = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2),
            max_features=8000,
            sublinear_tf=True,
        )
        matrix = vectorizer.fit_transform(docs)
        similarities = cosine_similarity(matrix[0:1], matrix[1:])[0]
        return [round(float(score) * 100, 1) for score in similarities]

    except Exception as error:
        logger.exception("Semantic scoring failed: %s", error)
        return [0.0] * len(job_texts)


# --------------------------------------------------
# SCORE ALL JOBS
# --------------------------------------------------

def _coverage_reliability(job_skill_count: int) -> float:
    """
    Reduce trust in skill coverage when only a few skills were detected.
    This multiplier affects combined ranking, not the displayed coverage.
    """
    if job_skill_count <= 0:
        return 0.0
    if job_skill_count == 1:
        return 0.35
    if job_skill_count == 2:
        return 0.55
    if job_skill_count == 3:
        return 0.70
    if job_skill_count == 4:
        return 0.82
    if job_skill_count == 5:
        return 0.90
    return 1.0


def score_all_jobs(
    resume_text: str,
    jobs: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not jobs:
        return []

    job_texts = [get_job_text(job) for job in jobs]
    semantic_scores = semantic_score_bulk(resume_text, job_texts)
    scored = []

    for index, job in enumerate(jobs):
        description = get_job_description(job)
        description_available = has_job_description(job)

        # Skill coverage is computed from the description only, not title.
        skill_match = calculate_skill_match(resume_text, description)
        keyword_score = skill_match["job_requirement_coverage"]
        semantic_value = semantic_scores[index]
        job_skill_count = skill_match["job_skill_count"]

        if not description_available:
            ats_value = None
            # Semantic similarity from a title/fragment alone is weak evidence.
            combined_score = round(semantic_value * 0.25, 1)
            score_status = "missing_description"

        elif job_skill_count < 3 or keyword_score is None:
            ats_value = None
            # Keep partial results visible, but substantially lower confidence.
            combined_score = round(semantic_value * 0.35, 1)
            score_status = "partial"

        else:
            ats_value = keyword_score
            reliability = _coverage_reliability(job_skill_count)
            reliable_coverage = keyword_score * reliability

            combined_score = round(
                0.65 * reliable_coverage + 0.35 * semantic_value,
                1,
            )
            score_status = "complete"

        job_copy = dict(job)
        job_copy["ats_score"] = ats_value
        job_copy["semantic_score"] = semantic_value
        job_copy["combined_score"] = combined_score
        job_copy["score_status"] = score_status

        job_copy["matched_skills"] = skill_match["matched_skills"]
        job_copy["missing_skills"] = skill_match["missing_skills"]
        job_copy["other_resume_skills"] = skill_match["other_resume_skills"]

        job_copy["resume_skill_count"] = skill_match["resume_skill_count"]
        job_copy["job_skill_count"] = skill_match["job_skill_count"]

        job_copy["job_requirement_coverage"] = (
            skill_match["job_requirement_coverage"]
        )
        job_copy["candidate_skill_coverage"] = (
            skill_match["candidate_skill_coverage"]
        )
        job_copy["has_job_description"] = description_available

        scored.append(job_copy)

    scored.sort(key=lambda item: item["combined_score"], reverse=True)

    logger.info("Job matching complete: %s jobs scored", len(scored))
    return scored
