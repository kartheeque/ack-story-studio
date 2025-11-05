# server/main.py
from dotenv import load_dotenv
import os
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI, APIError
import httpx
import time

log = logging.getLogger("uvicorn.error")

#Load .env
load_dotenv()  # <--- this reads .env automatically
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# --- FastAPI app ---
app = FastAPI()

# --- CORS (dev) ---
# Tighten origins later; "*" is fine for local debugging
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- OpenAI client ---
if not OPENAI_API_KEY:
    log.warning("OPENAI_API_KEY is not set in the environment.")

# Build our own httpx client so the SDK doesn't construct one with deprecated args
http_client = httpx.Client(timeout=60.0, trust_env=False)  # add proxy=... if you really need it
client = OpenAI(api_key=OPENAI_API_KEY, http_client=http_client)

# --- Models ---
class PromptRequest(BaseModel):
    story: str

class PromptResponse(BaseModel):
    prompts: list[str]

# --- Health check ---
@app.get("/health")
def health():
    return {"ok": True}

# --- Your endpoint: POST /api/prompts ---
@app.post("/api/prompts", response_model=PromptResponse)
def create_prompts(req: PromptRequest):
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not set")

    try:
        log.info("Preparing to call OpenAI", extra={
            "story_length": len(req.story or ""),
        })
        start_time = time.monotonic()
        # Keep it simple; replace with your actual prompt later
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Return exactly 8 short image prompts."},
                {"role": "user", "content": req.story},
            ],
            n=1,
        )
        duration = time.monotonic() - start_time
        log.info(
            "OpenAI call completed",
            extra={
                "duration_seconds": round(duration, 3),
                "response_id": getattr(resp, "id", None),
                "finish_reason": resp.choices[0].finish_reason if resp.choices else None,
                "prompt_tokens": getattr(resp, "usage", {}).prompt_tokens if getattr(resp, "usage", None) else None,
                "completion_tokens": getattr(resp, "usage", {}).completion_tokens if getattr(resp, "usage", None) else None,
            },
        )
        content = resp.choices[0].message.content or ""
        # naive split for demo; adjust to how your prompt formats results
        lines = [s.strip("- •\t ").strip() for s in content.split("\n") if s.strip()]
        prompts = [l for l in lines if l][:8]
        if len(prompts) < 8:
            # pad to avoid FE crashing on length assumptions
            prompts += ["(placeholder)"] * (8 - len(prompts))
        return {"prompts": prompts}

    except APIError as e:
        log.exception(
            "OpenAI API error",
            extra={
                "error_type": getattr(e, "type", None),
                "error_code": getattr(e, "code", None),
                "error_param": getattr(e, "param", None),
                "error_message": str(e),
            },
        )
        raise HTTPException(status_code=502, detail=f"Upstream OpenAI error: {e}")
    except httpx.HTTPError as e:
        log.exception(
            "Network error to OpenAI",
            extra={
                "error_message": str(e),
                "request": getattr(e, "request", None).url if getattr(e, "request", None) else None,
            },
        )
        raise HTTPException(status_code=502, detail=f"Network error: {e}")
    except Exception as e:
        log.exception(
            "Unhandled server error",
            extra={
                "error_message": str(e),
            },
        )
        raise HTTPException(status_code=500, detail=f"Server error: {e}")
