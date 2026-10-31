
from fastapi import FastAPI, UploadFile, File, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from io import BytesIO
import logging
import os
import uuid
import uvicorn
import pdfplumber

logger = logging.getLogger(__name__)

app = FastAPI(title="Job Hunt AI Agent API")

# Configure frontend origins.
allowed_origins = os.getenv(
    "FRONTEND_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in allowed_origins],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Session-ID"],
)

# Session-specific resume storage.
USER_CONTEXT = {}


class ChatRequest(BaseModel):
    message: str


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


@app.get("/")
async def root():
    return {
        "message": "Job Hunt AI Agent API is running."
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.post("/api/chat")
def chat(
    request: ChatRequest,
    session_id: Optional[str] = Header(
        default=None,
        alias="X-Session-ID"
    )
):
    session_id = validate_session_id(session_id)

    try:
        from agent import run_agent

        resume_text = USER_CONTEXT.get(
            session_id,
            {}
        ).get("resume_text", "")

        reply, jobs_list, raw_jobs_list = run_agent(
            request.message,
            resume_text
        )

        return {
            "reply": reply,
            "jobs": jobs_list,
            "raw_jobs": raw_jobs_list
        }

    except Exception as e:
        logger.exception("Chat endpoint failed: %s", e)

        return {
            "reply": "The job search failed. Please try again.",
            "jobs": [],
            "raw_jobs": []
        }


@app.post("/api/upload_resume")
async def upload_resume(
    file: UploadFile = File(...),
    session_id: Optional[str] = Header(
        default=None,
        alias="X-Session-ID"
    )
):
    session_id = validate_session_id(session_id)

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported."
        )

    content = await file.read()

    # Basic upload-size protection: 5 MB.
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
                detail="No readable text found. Please upload a text-based PDF."
            )

        USER_CONTEXT[session_id] = {
            "resume_text": text
        }

        return {
            "filename": file.filename,
            "status": "Parsed successfully",
            "text_length": len(text),
            "preview": text[:200]
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


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=True
    )
