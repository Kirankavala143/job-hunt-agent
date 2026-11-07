
from fastapi import (
    FastAPI,
    UploadFile,
    File,
    HTTPException,
    Header,
    Depends,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import Literal, Optional
from io import BytesIO
import logging
import os
import json
from datetime import datetime, timezone
from google import genai
import re
import uuid
import uvicorn
import pdfplumber
from dotenv import load_dotenv
load_dotenv()

from auth import (
    RegisterRequest,
    LoginRequest,
    register_user,
    authenticate_user,
    create_access_token,
    get_user_from_token,
    get_connection,
)

logger = logging.getLogger(__name__)

app = FastAPI(title="Job Hunt AI Agent API")

# ---------------- CORS CONFIGURATION ----------------

allowed_origins = os.getenv(
    "FRONTEND_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in allowed_origins],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=[
        "Content-Type",
        "X-Session-ID",
        "Authorization",
    ],
)

# ---------------- SESSION STORAGE ----------------

USER_CONTEXT = {}

# ---------------- MODELS ----------------

class ChatRequest(BaseModel):
    message: str

class ResumeMatchRequest(BaseModel):
    job_description: str


class ProfileUpdateRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    role: str = Field(min_length=2, max_length=100)
    location: str = Field(min_length=2, max_length=120)


class AlertRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=1000)
    status: Literal["Enabled", "Paused"] = "Enabled"
    last_run: str = Field(default="", max_length=120)
    next_run: str = Field(default="", max_length=120)


# ---------------- SKILL KEYWORDS ----------------

SKILL_KEYWORDS = [
    "Python", "Java", "C", "C++", "C#", "JavaScript",
    "TypeScript", "SQL", "HTML", "CSS", "React",
    "Angular", "Vue", "Node.js", "Express.js", "FastAPI",
    "Flask", "Django", "REST API", "MongoDB", "MySQL",
    "PostgreSQL", "SQLite", "Git", "GitHub", "Docker",
    "Kubernetes", "AWS", "Azure", "Google Cloud",
    "Power BI", "Tableau", "Excel", "Pandas", "NumPy",
    "Matplotlib", "Seaborn", "Scikit-learn", "TensorFlow",
    "PyTorch", "Machine Learning", "Deep Learning",
    "Artificial Intelligence", "Generative AI",
    "Natural Language Processing", "NLP", "Computer Vision",
    "Data Analysis", "Data Analytics", "Data Visualization",
    "Statistics", "Data Structures", "Algorithms",
    "Object-Oriented Programming", "OOP", "MERN Stack",
    "Agile", "Linux", "Bash", "Jupyter Notebook",
    "Streamlit", "OpenCV", "MCP",
]

# ---------------- HELPERS ----------------

def validate_session_id(session_id: Optional[str]) -> str:
    """Validate the browser session identifier."""

    if not session_id:
        raise HTTPException(
            status_code=400,
            detail="Session ID is required."
        )

    try:
        return str(uuid.UUID(session_id))
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid session ID."
        )


def extract_skills(resume_text: str) -> list[str]:
    """Detect listed skills from resume text."""

    normalized_text = resume_text.lower()
    detected_skills = []

    for skill in SKILL_KEYWORDS:
        normalized_skill = skill.lower()

        pattern = (
            r"(?<![a-z0-9])"
            + re.escape(normalized_skill)
            + r"(?![a-z0-9])"
        )

        if re.search(pattern, normalized_text):
            detected_skills.append(skill)

    return detected_skills


# ---------------- BASIC ROUTES ----------------

@app.get("/")
async def root():
    return {
        "message": "Job Hunt AI Agent API is running."
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


# ---------------- AUTHENTICATION ----------------

security = HTTPBearer()


@app.post("/api/auth/register", status_code=201)
def auth_register(request: RegisterRequest):
    try:
        user = register_user(request)

        token = create_access_token(
            user["id"],
            user["email"]
        )

        return {
            "message": "Account created successfully.",
            "user": user,
            "access_token": token,
            "token_type": "bearer",
        }

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


@app.post("/api/auth/login")
def auth_login(request: LoginRequest):
    user = authenticate_user(request)

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password."
        )

    token = create_access_token(
        user["id"],
        user["email"]
    )

    return {
        "message": "Login successful.",
        "user": user,
        "access_token": token,
        "token_type": "bearer",
    }


@app.get("/api/auth/me")
def auth_me(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    user = get_user_from_token(credentials.credentials)

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token."
        )

    return {"user": user}


def get_authenticated_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = get_user_from_token(credentials.credentials)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token.",
        )
    return user


def serialize_alert(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "status": row["status"],
        "last_run": row["last_run"],
        "next_run": row["next_run"],
    }


@app.get("/api/profile")
def get_profile(user: dict = Depends(get_authenticated_user)):
    return {
        "id": user["id"],
        "full_name": user["full_name"],
        "email": user["email"],
        "role": user["role_title"],
        "location": user["location"],
    }


@app.put("/api/profile")
def update_profile(
    request: ProfileUpdateRequest,
    user: dict = Depends(get_authenticated_user),
):
    full_name = request.full_name.strip()
    role = request.role.strip()
    location = request.location.strip()
    if len(full_name) < 2 or len(role) < 2 or len(location) < 2:
        raise HTTPException(
            status_code=422,
            detail="Full name, role, and location must each contain at least 2 characters.",
        )

    with get_connection() as connection:
        connection.execute(
            """
            UPDATE users
            SET full_name = ?, role_title = ?, location = ?
            WHERE id = ?
            """,
            (full_name, role, location, user["id"]),
        )
        connection.commit()
        updated = connection.execute(
            """
            SELECT id, full_name, email, role_title, location
            FROM users
            WHERE id = ?
            """,
            (user["id"],),
        ).fetchone()

    if not updated:
        raise HTTPException(status_code=404, detail="Profile not found.")

    return {
        "id": updated["id"],
        "full_name": updated["full_name"],
        "email": updated["email"],
        "role": updated["role_title"],
        "location": updated["location"],
    }


@app.get("/api/alerts")
def get_alerts(user: dict = Depends(get_authenticated_user)):
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, name, description, status, last_run, next_run
            FROM alerts
            WHERE user_id = ?
            ORDER BY id
            """,
            (user["id"],),
        ).fetchall()
    return [serialize_alert(row) for row in rows]


@app.post("/api/alerts", status_code=201)
def create_alert(
    request: AlertRequest,
    user: dict = Depends(get_authenticated_user),
):
    name = request.name.strip()
    if len(name) < 2:
        raise HTTPException(
            status_code=422,
            detail="Alert title must contain at least 2 characters.",
        )

    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO alerts (
                user_id, name, description, status, last_run, next_run,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user["id"],
                name,
                request.description.strip(),
                request.status,
                request.last_run.strip(),
                request.next_run.strip(),
                now,
                now,
            ),
        )
        connection.commit()
        row = connection.execute(
            """
            SELECT id, name, description, status, last_run, next_run
            FROM alerts
            WHERE id = ? AND user_id = ?
            """,
            (cursor.lastrowid, user["id"]),
        ).fetchone()
    return serialize_alert(row)


@app.put("/api/alerts/{alert_id}")
def update_alert(
    alert_id: int,
    request: AlertRequest,
    user: dict = Depends(get_authenticated_user),
):
    name = request.name.strip()
    if len(name) < 2:
        raise HTTPException(
            status_code=422,
            detail="Alert title must contain at least 2 characters.",
        )

    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE alerts
            SET name = ?, description = ?, status = ?, last_run = ?,
                next_run = ?, updated_at = ?
            WHERE id = ? AND user_id = ?
            """,
            (
                name,
                request.description.strip(),
                request.status,
                request.last_run.strip(),
                request.next_run.strip(),
                datetime.now(timezone.utc).isoformat(),
                alert_id,
                user["id"],
            ),
        )
        connection.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Alert not found.")
        row = connection.execute(
            """
            SELECT id, name, description, status, last_run, next_run
            FROM alerts
            WHERE id = ? AND user_id = ?
            """,
            (alert_id, user["id"]),
        ).fetchone()
    return serialize_alert(row)


@app.delete("/api/alerts/{alert_id}")
def delete_alert(
    alert_id: int,
    user: dict = Depends(get_authenticated_user),
):
    with get_connection() as connection:
        cursor = connection.execute(
            "DELETE FROM alerts WHERE id = ? AND user_id = ?",
            (alert_id, user["id"]),
        )
        connection.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Alert not found.")
    return {"deleted": True}


# ---------------- ASSISTANT INTENT ROUTING ----------------


def detect_chat_intent(message: str) -> str:
    """Route a user's message to job search or the relevant assistant flow."""
    text = " ".join(message.lower().strip().split())

    # Handle specific intents before broad job-related keywords.
    resume_phrases = (
        "analyze my resume",
        "analyse my resume",
        "resume analysis",
        "review my resume",
        "check my resume",
        "improve my resume",
        "ats score",
        "resume score",
        "resume match",
        "match my resume",
    )
    if any(phrase in text for phrase in resume_phrases):
        return "resume"

    cover_letter_phrases = (
        "cover letter",
        "write a cover letter",
        "generate cover letter",
    )
    if any(phrase in text for phrase in cover_letter_phrases):
        return "cover_letter"

    interview_phrases = (
        "interview preparation",
        "prepare for interview",
        "interview questions",
        "mock interview",
    )
    if any(phrase in text for phrase in interview_phrases):
        return "interview"

    career_phrases = (
        "career roadmap",
        "career advice",
        "what should i learn",
        "learning roadmap",
    )
    if any(phrase in text for phrase in career_phrases):
        return "career"

    # Explicit job-search wording.
    job_search_phrases = (
        "find jobs",
        "search jobs",
        "job search",
        "show jobs",
        "jobs for me",
        "job openings",
        "job opportunities",
        "find vacancies",
        "search vacancies",
        "find internships",
        "search internships",
        "job listings",
        "job alerts",
        "fresher jobs",
        "entry level jobs",
        "entry-level jobs",
    )
    if any(phrase in text for phrase in job_search_phrases):
        return "job_search"

    # Natural-language requests like "find AI developer jobs across India"
    # or "search for GenAI internships in Bangalore".
    search_actions = (
        "find ",
        "search ",
        "search for ",
        "show ",
        "show me ",
        "look for ",
        "get me ",
        "discover ",
        "list ",
    )
    job_terms = (
        "job",
        "jobs",
        "internship",
        "internships",
        "vacancy",
        "vacancies",
        "hiring",
        "developer",
        "engineer",
        "analyst",
        "trainee",
        "fresher",
        "genai",
        "aiml",
        "machine learning",
        "artificial intelligence",
        "software",
        "python",
        "data science",
    )
    if text.startswith(search_actions) and any(term in text for term in job_terms):
        return "job_search"

    # Do not use "assistant" here: /api/chat routes general requests as "chat".
    return "chat"


# ---------------- AI ASSISTANT HELPERS ----------------

def generate_ai_reply(
    message: str,
    resume_text: str = "",
    history: list = None,
) -> str:
    """Generate an assistant response using Gemini."""

    from google import genai

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is missing from the backend environment."
        )

    client = genai.Client(api_key=api_key)

    model = os.getenv(
    "MODEL_NAME",
    "gemini-3.8-flash"
    )

    system_instruction = """
You are JobHunt AI, a helpful career assistant.

You can:
- Analyze resumes and explain strengths, weaknesses, and skill gaps.
- Generate tailored professional cover letters.
- Create practical career roadmaps.
- Prepare users for technical and HR interviews.
- Explain job descriptions and recommend skills.
- Answer general career and programming questions.

Important rules:
1. Use the user's uploaded resume only when provided.
2. Never claim a resume was uploaded if its text is empty.
3. If the user asks for a cover letter and a job description is
   available in recent chat history, generate the letter directly.
4. If important information is missing, ask only for that information.
5. If a job description was pasted in a previous message, use it
   as context for the current request.
6. Do not run job searches unless the user explicitly requests jobs.
7. Be specific, practical, and honest. Do not invent experience.
8. Use Markdown formatting for readable responses.
"""

    context = f"""
UPLOADED RESUME:
{resume_text if resume_text else "No resume uploaded."}

RECENT CONVERSATION:
"""

    for item in (history or [])[-12:]:
        role = item.get("role", "user")
        content = item.get("content", "")
        context += f"\n{role.upper()}: {content}\n"

    context += f"\nCURRENT USER MESSAGE:\n{message}"

    response = client.models.generate_content(
        model=model,
        contents=context,
        config={
            "system_instruction": system_instruction,
            "temperature": 0.4,
        },
    )

    reply = getattr(response, "text", None)

    if not reply:
        raise RuntimeError("Gemini returned an empty response.")

    return reply.strip()


# ---------------- CHAT ----------------

@app.post("/api/chat")
def chat(
    request: ChatRequest,
    session_id: Optional[str] = Header(
        default=None,
        alias="X-Session-ID"
    )
):
    session_id = validate_session_id(session_id)
    message = request.message.strip()

    if not message:
        return {
            "reply": "Please enter a message.",
            "jobs": [],
            "raw_jobs": [],
        }

    try:
        user_context = USER_CONTEXT.setdefault(
            session_id,
            {
                "resume_text": "",
                "skills": [],
                "filename": None,
                "history": [],
            }
        )

        history = user_context.setdefault("history", [])
        resume_text = user_context.get("resume_text", "")

        intent = detect_chat_intent(message)

        # Job search remains connected to the existing agent.
        if intent == "job_search":
            from agent import run_agent

            reply, jobs_list, raw_jobs_list = run_agent(
                message,
                resume_text
            )

            history.append({
                "role": "user",
                "content": message,
            })
            history.append({
                "role": "assistant",
                "content": reply,
            })

            user_context["history"] = history[-20:]

            return {
                "reply": reply,
                "jobs": jobs_list,
                "raw_jobs": raw_jobs_list,
            }

        # Resume analysis requires an uploaded resume.
        if intent == "resume" and not resume_text:
            reply = (
                "I don't see a resume uploaded in this session. "
                "Please upload your resume PDF first, then ask me "
                "to analyze it."
            )

            return {
                "reply": reply,
                "jobs": [],
                "raw_jobs": [],
            }

        # All other requests use Gemini and chat history.
        reply = generate_ai_reply(
            message=message,
            resume_text=resume_text,
            history=history,
        )

        history.append({
            "role": "user",
            "content": message,
        })
        history.append({
            "role": "assistant",
            "content": reply,
        })

        user_context["history"] = history[-20:]

        return {
            "reply": reply,
            "jobs": [],
            "raw_jobs": [],
        }

    except Exception as e:
        logger.exception("Chat endpoint failed: %s", e)

        return {
            "reply": (
                "I couldn't process that request right now. "
                "Please check the backend logs and try again."
            ),
            "jobs": [],
            "raw_jobs": [],
        }

# ---------------- RESUME UPLOAD ----------------

@app.post("/api/upload_resume")
async def upload_resume(
    file: UploadFile = File(...),
    session_id: Optional[str] = Header(
        default=None,
        alias="X-Session-ID"
    )
):
    session_id = validate_session_id(session_id)

    if (
        not file.filename
        or not file.filename.lower().endswith(".pdf")
    ):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported."
        )

    content = await file.read()

    # Upload size limit: 5 MB.
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail="PDF must be smaller than 5 MB."
        )

    try:
        with pdfplumber.open(BytesIO(content)) as pdf:
            pages = [
                page.extract_text() or ""
                for page in pdf.pages
            ]

        text = "\n".join(pages).strip()

        if not text:
            raise HTTPException(
                status_code=422,
                detail=(
                    "No readable text found. Please upload "
                    "a text-based PDF."
                )
            )

        skills = extract_skills(text)

        user_context = USER_CONTEXT.setdefault(
            session_id,
            {"history": []}
        )

        user_context.update({
            "resume_text": text,
            "skills": skills,
            "filename": file.filename,
        })

        return {
            "filename": file.filename,
            "status": "Parsed successfully",
            "text_length": len(text),
            "preview": text[:200],
            "skills": skills,
            "skill_count": len(skills),
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.exception("Resume parsing failed: %s", e)

        raise HTTPException(
            status_code=500,
            detail="Failed to parse PDF."
        )

    finally:
        await file.close()

def normalize_skill(skill: str) -> str:
    skill = skill.strip().lower()

    aliases = {
        "object-oriented programming": "oop",
        "object oriented programming": "oop",
        "oops": "oop",
        "structured query language": "sql",
        "javascript": "javascript",
        "js": "javascript",
        "python programming": "python",
        "rest api": "rest apis",
        "restful api": "rest apis",
        "restful apis": "rest apis",
        "scikit learn": "scikit-learn",
        "sklearn": "scikit-learn",
        "machine-learning": "machine learning",
        "artificial-intelligence": "artificial intelligence",
    }

    return aliases.get(skill, skill)


@app.post("/api/resume/match")
async def match_resume(
    request: ResumeMatchRequest,
    session_id: Optional[str] = Header(
        default=None,
        alias="X-Session-ID"
    ),
):
    session_id = validate_session_id(session_id)

    user_context = USER_CONTEXT.get(session_id, {})
    resume_text = user_context.get("resume_text", "")

    if not resume_text:
        raise HTTPException(
            status_code=400,
            detail="Please upload your resume first."
        )

    job_description = request.job_description.strip()

    if not job_description:
        raise HTTPException(
            status_code=400,
            detail="Please provide a job description."
        )

    resume_skills = {
    normalize_skill(skill)
    for skill in user_context.get("skills", [])
    }

    job_skills = {
        normalize_skill(skill)
        for skill in extract_skills(job_description)
    }

    matched_skills = sorted(
        resume_skills.intersection(job_skills)
    )

    missing_skills = sorted(
        job_skills.difference(resume_skills)
    )

    if job_skills:
        match_score = round(
            len(matched_skills) / len(job_skills) * 100
        )
    else:
        match_score = 0

    return {
        "match_score": match_score,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "resume_skills": sorted(resume_skills),
        "job_skills": sorted(job_skills),
        "message": (
            "Resume matched successfully."
            if job_skills
            else "No recognized skills found in the job description."
        ),
    }
from pydantic import BaseModel

class ResumeAIAnalysisRequest(BaseModel):
    job_description: str


@app.post("/api/resume/ai-analysis")
async def ai_resume_analysis(
    request: ResumeAIAnalysisRequest,
    session_id: Optional[str] = Header(
        default=None,
        alias="X-Session-ID"
    ),
):
    session_id = validate_session_id(session_id)

    user_context = USER_CONTEXT.get(session_id, {})
    resume_text = user_context.get("resume_text", "")

    if not resume_text:
        raise HTTPException(
            status_code=400,
            detail="Please upload your resume first."
        )

    job_description = request.job_description.strip()

    if not job_description:
        raise HTTPException(
            status_code=400,
            detail="Please provide a job description."
        )

    prompt = f"""
You are an expert resume consultant and ATS analyzer.

Analyze the candidate's resume against the job description.

RESUME:
{resume_text[:12000]}

JOB DESCRIPTION:
{job_description[:8000]}

Return ONLY valid JSON with this exact structure:

{{
    "match_score": 0,
    "professional_summary": "",
    "matched_skills": [],
    "missing_skills": [],
    "strengths": [],
    "improvement_suggestions": [],
    "ats_keywords": []
}}

Instructions:
- match_score must be an integer between 0 and 100.
- Evaluate skills, projects, education, and relevance.
- Do not invent experience or skills.
- Missing skills must be based on the job description.
- Give practical and specific improvement suggestions.
- Keep professional_summary concise and truthful.
- Return JSON only.
"""

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config={
                "response_mime_type": "application/json"
            }
        )

        analysis = json.loads(response.text)

        return {
            "status": "success",
            "analysis": analysis
        }

    except json.JSONDecodeError:
        logger.exception("Gemini returned invalid JSON")

        raise HTTPException(
            status_code=502,
            detail="AI returned an invalid analysis format."
        )

    except Exception as e:
        logger.exception("AI resume analysis failed: %s", e)

        raise HTTPException(
            status_code=500,
            detail="Failed to generate AI resume analysis."
        )

# ---------------- RUN SERVER ----------------

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=True
    )
