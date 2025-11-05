# server/main.py
from dotenv import load_dotenv
import os
import logging
import json
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI, APIError
import httpx

from models import Panel, PromptsRequest, PromptsResponse

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

# --- Health check ---
@app.get("/health")
def health():
    return {"ok": True}

# --- Your endpoint: POST /api/prompts ---
@app.post("/api/prompts", response_model=PromptsResponse)
def create_prompts(req: PromptsRequest):
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not set")

    try:
        # Ask the model for structured JSON (background + eight panel prompts)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    # Root cause: the new OpenAI SDK expects message content to be structured as
                    # objects (e.g. {"type": "text", "text": "..."}). We previously sent raw
                    # strings which triggered a 400 "Invalid type" error. Wrap the text in the
                    # required object format so the request is accepted.
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "You are a service that extracts a concise background and exactly "
                                "eight numbered illustration prompts from a story. "
                                "Return strict JSON with the shape {\"background\": string, "
                                "\"panels\": [{\"n\": number, \"title\": string, \"prompt\": string} x8]}. "
                                "Titles should be short and descriptive. Prompts must be richly "
                                "detailed and self-contained."
                            ),
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Story:\n" + req.story.strip(),
                        }
                    ],
                },
            ],
            n=1,
        )
        content = resp.choices[0].message.content or ""

        try:
            payload = json.loads(content)
        except json.JSONDecodeError as e:
            log.error("Model returned invalid JSON: %s", content)
            raise HTTPException(status_code=502, detail="Model returned invalid JSON") from e

        background = str(payload.get("background", "")).strip()
        raw_panels = payload.get("panels", [])

        if not isinstance(raw_panels, list):
            raise HTTPException(status_code=502, detail="Model returned invalid panel list")

        panels: List[Panel] = []
        for idx in range(8):
            raw = raw_panels[idx] if idx < len(raw_panels) else {}
            if not isinstance(raw, dict):
                raw = {}
            n = raw.get("n", idx + 1)
            try:
                n = int(n)
            except (TypeError, ValueError):
                n = idx + 1
            title = str(raw.get("title") or f"Panel {n}").strip()
            prompt_text = str(raw.get("prompt") or "").strip()
            if not prompt_text:
                prompt_text = "(placeholder)"
            panels.append(Panel(n=n, title=title, prompt=prompt_text))

        model_used = getattr(resp, "model", "gpt-4o-mini")

        return PromptsResponse(background=background, panels=panels, model=model_used)

    except APIError as e:
        log.exception("OpenAI API error")
        raise HTTPException(status_code=502, detail=f"Upstream OpenAI error: {e}")
    except httpx.HTTPError as e:
        log.exception("Network error to OpenAI")
        raise HTTPException(status_code=502, detail=f"Network error: {e}")
    except Exception as e:
        log.exception("Unhandled server error")
        raise HTTPException(status_code=500, detail=f"Server error: {e}")
