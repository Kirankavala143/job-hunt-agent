
import re
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


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
    "git", "github", "rest api", "fastapi",
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


def normalize(text: str) -> str:
    text = str(text or "").lower()

    for alias, canonical in SYNONYMS.items():
        text = re.sub(
            r"(?<!\w)" + re.escape(alias) + r"(?!\w)",
            canonical,
            text
        )

    return re.sub(r"[^\w+#.\s-]", " ", text)


def contains_skill(text: str, skill: str) -> bool:
    pattern = r"(?<!\w)" + re.escape(skill) + r"(?!\w)"
    return bool(re.search(pattern, text))


def extract_skills(text: str) -> set:
    normalized = normalize(text)

    return {
        skill
        for skill in SKILLS_VOCAB
        if contains_skill(normalized, skill)
    }


def ats_score(resume_text: str, job_text: str) -> float:
    resume_skills = extract_skills(resume_text)

    if not resume_skills:
        return 0.0

    job_skills = extract_skills(job_text)

    matched = resume_skills & job_skills

    return round(
        len(matched) / len(resume_skills) * 100,
        1
    )


def semantic_score_bulk(
    resume_text: str,
    job_texts: List[str]
) -> List[float]:

    if not resume_text.strip():
        return [0.0] * len(job_texts)

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        docs = [resume_text] + job_texts

        vectorizer = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2),
            max_features=8000,
            sublinear_tf=True
        )

        matrix = vectorizer.fit_transform(docs)

        similarities = cosine_similarity(
            matrix[0:1],
            matrix[1:]
        )[0]

        return [
            round(float(score) * 100, 1)
            for score in similarities
        ]

    except Exception as error:
        logger.error("Semantic scoring failed: %s", error)
        return [0.0] * len(job_texts)


def score_all_jobs(
    resume_text: str,
    jobs: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:

    if not jobs:
        return []

    resume_skills = extract_skills(resume_text)

    job_texts = [
        f"{job.get('title', '')} "
        f"{job.get('company', '')} "
        f"{job.get('description', '')}"
        for job in jobs
    ]

    semantic_scores = semantic_score_bulk(
        resume_text,
        job_texts
    )

    scored = []

    for index, job in enumerate(jobs):

        job_skills = extract_skills(job_texts[index])

        matched = sorted(resume_skills & job_skills)
        missing = sorted(resume_skills - job_skills)

        keyword_score = (
            round(len(matched) / len(resume_skills) * 100, 1)
            if resume_skills else None
        )

        semantic_score = semantic_scores[index]

        combined_score = (
            round(0.7 * keyword_score + 0.3 * semantic_score, 1)
            if keyword_score is not None else None
        )

        job_copy = dict(job)

        job_copy["ats_score"] = keyword_score
        job_copy["semantic_score"] = semantic_score
        job_copy["combined_score"] = combined_score
        job_copy["matched_skills"] = matched
        job_copy["missing_skills"] = missing
        job_copy["resume_skill_count"] = len(resume_skills)

        scored.append(job_copy)

    scored.sort(
        key=lambda item: (
            item["combined_score"]
            if item["combined_score"] is not None
            else -1
        ),
        reverse=True
    )

    logger.info(
        "ATS scoring complete: %s resume skills detected, %s jobs scored",
        len(resume_skills),
        len(scored)
    )

    return scored
