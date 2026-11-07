
from ats_scorer import calculate_skill_match, score_all_jobs


resume = """
I have experience with Python, SQL, React, Flask, and Git.
I developed web applications using Python and React.
"""


job_description = """
We are looking for a developer with Python, SQL, React,
Node.js, and TypeScript skills.

Experience with REST API development is preferred.
"""


result = calculate_skill_match(
    resume,
    job_description,
)

print("\n--- Skill Match Result ---")

for key, value in result.items():
    print(f"{key}: {value}")


jobs = [
    {
        "title": "Full Stack Developer Intern",
        "company": "Example Technologies",
        "description": job_description,
        "location": "Remote",
    }
]

scored_jobs = score_all_jobs(resume, jobs)

print("\n--- Scored Job ---")

print("ATS Score:", scored_jobs[0]["ats_score"])
print("Semantic Score:", scored_jobs[0]["semantic_score"])
print("Combined Score:", scored_jobs[0]["combined_score"])
