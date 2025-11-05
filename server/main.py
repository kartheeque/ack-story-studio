# server/main.py
from dotenv import load_dotenv
import os
import logging
import json
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI, APIError
import httpx

from models import (
    GenerateFromBlockRequest,
    Panel,
    PromptsRequest,
    PromptsResponse,
)
from utils import parse_block_to_background_and_panels

import base64
import io
import re

log = logging.getLogger("uvicorn.error")

#Load .env
load_dotenv()  # <--- this reads .env automatically
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
USE_OPENAI_MOCK = os.getenv("OPENAI_USE_MOCK", "0").lower() in {"1", "true", "yes", "on"}

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
if not OPENAI_API_KEY and not USE_OPENAI_MOCK:
    log.warning("OPENAI_API_KEY is not set in the environment.")


class MockChatCompletions:
    """Mimic the subset of the OpenAI chat.completions interface we rely on."""

    def __init__(self):
        # Capture the last request so tests or debugging sessions can assert on the
        # payload we would have sent to OpenAI without actually making a network
        # call. This mirrors the public attributes a real client exposes when
        # inspecting responses, giving us a convenient hook while the mock is
        # enabled.
        self.last_request = None

    class _ResponseMessage:
        def __init__(self, content: str):
            self.content = content

    class _ResponseChoice:
        def __init__(self, content: str):
            self.message = MockChatCompletions._ResponseMessage(content)

    class _Response:
        def __init__(self, content: str, model: str):
            self.choices = [MockChatCompletions._ResponseChoice(content)]
            self.model = model

    @staticmethod
    def _extract_story(messages):
        story_chunks = []
        for message in messages:
            if message.get("role") != "user":
                continue
            for chunk in message.get("content", []):
                if isinstance(chunk, dict) and chunk.get("type") == "text":
                    story_chunks.append(str(chunk.get("text", "")))
        combined = "\n".join(story_chunks).strip()
        if combined.lower().startswith("story:"):
            combined = combined.split(":", 1)[1].strip()
        return combined or "Mock story content"

    @staticmethod
    def _render_mock_payload(story: str) -> str:
        sentences = [s.strip() for s in story.replace("\n", " ").split(".") if s.strip()]
        if not sentences:
            sentences = ["A placeholder scene for the mock story"]

        background = " ".join(sentences[:2]).strip()
        if not background:
            background = "Mock background generated from the provided story."

        panels = []
        for idx in range(8):
            source_sentence = sentences[idx % len(sentences)]
            panels.append(
                {
                    "n": idx + 1,
                    "title": f"Panel {idx + 1}",
                    "prompt": (
                        f"Mock prompt {idx + 1}: illustrate '{source_sentence}' with vivid colors, "
                        "dynamic lighting, and cinematic composition."
                    ),
                }
            )

        return json.dumps({"background": background, "panels": panels})

    def create(self, *, messages, **kwargs):  # pylint: disable=unused-argument
        self.last_request = {"messages": messages, "params": dict(kwargs)}
        story = self._extract_story(messages)
        content = self._render_mock_payload(story)
        model = kwargs.get("model", "mock-openai")
        return MockChatCompletions._Response(content, model=model)


MOCK_PIXEL = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAAWgmWQ0AAAAASUVORK5CYII="
)


class MockImages:
    """Return a single 1x1 PNG for each requested prompt."""

    def __init__(self):
        self.calls = []

    class _Response:
        def __init__(self, prompt: str):
            payload = base64.b64encode(MOCK_PIXEL).decode("ascii")
            self.data = [
                {
                    "b64_json": payload,
                    "revised_prompt": prompt,
                }
            ]

    def _record(self, *, prompt: str, method: str, **kwargs):
        self.calls.append({"prompt": prompt, "method": method, "params": dict(kwargs)})
        return MockImages._Response(prompt)

    def generate(self, *, prompt: str, **kwargs):  # pylint: disable=unused-argument
        return self._record(prompt=prompt, method="generate", **kwargs)

    def edit(self, *, prompt: str, **kwargs):  # pylint: disable=unused-argument
        return self._record(prompt=prompt, method="edit", **kwargs)


class MockOpenAI:
    def __init__(self):
        self.chat = type("Chat", (), {"completions": MockChatCompletions()})()
        self.images = MockImages()


if USE_OPENAI_MOCK:
    log.info("OPENAI_USE_MOCK enabled; returning mock completions instead of hitting OpenAI.")
    client = MockOpenAI()
else:
    # Build our own httpx client so the SDK doesn't construct one with deprecated args
    http_client = httpx.Client(timeout=300.0, trust_env=False)  # add proxy=... if you really need it
    client = OpenAI(api_key=OPENAI_API_KEY, http_client=http_client)

# --- Health check ---
@app.get("/health")
def health():
    return {"ok": True}

# --- Your endpoint: POST /api/prompts ---
@app.post("/api/prompts", response_model=PromptsResponse)
def create_prompts(req: PromptsRequest):
    if not OPENAI_API_KEY and not USE_OPENAI_MOCK:
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


def _panel_filename(panel: Panel) -> str:
    """Generate a filesystem-safe filename for a panel image."""
    slug = re.sub(r"[^a-z0-9]+", "-", panel.title.strip().lower()).strip("-")
    if not slug:
        slug = f"panel-{panel.n}"
    slug = slug[:40].rstrip("-")
    return f"{panel.n:02d}-{slug}.png"


def _decode_image_b64(payload: Optional[str], panel_index: int) -> bytes:
    if not payload:
        raise HTTPException(status_code=502, detail=f"Image {panel_index + 1} missing data")
    try:
        return base64.b64decode(payload)
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=502, detail=f"Image {panel_index + 1} decode error") from exc


@app.post("/api/generate")
def generate_images(req: GenerateFromBlockRequest):
    if not OPENAI_API_KEY and not USE_OPENAI_MOCK:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not set")

    background, parsed_panels = parse_block_to_background_and_panels(req.block or "")
    if not parsed_panels:
        raise HTTPException(status_code=400, detail="No [PROMPT N] sections found in block")

    # Only keep the first eight prompts; ignore extras to avoid runaway usage.
    panels = sorted(parsed_panels, key=lambda p: p.n)[:8]
    size = (req.image.size if req.image and req.image.size else "1024x1536")
    use_refs = bool(req.useImageReferences)

    if req.panelIndex < 1:
        raise HTTPException(status_code=400, detail="panelIndex must be >= 1")

    if req.panelIndex > len(panels):
        raise HTTPException(status_code=400, detail="panelIndex exceeds available prompts")

    panel_position = req.panelIndex - 1
    target_panel = panels[panel_position]
    previous_panel = panels[panel_position - 1] if panel_position > 0 else None

    prompt_parts = []
    if background.strip():
        prompt_parts.append(background.strip())
    prompt_parts.append(target_panel.prompt.strip())
    if use_refs and previous_panel:
        prompt_parts.append(
            "Consistency note based on previous panel: " + previous_panel.prompt.strip()
        )
    prompt_text = "\n\n".join(part for part in prompt_parts if part)

    prompt_value = prompt_text or "Placeholder prompt"

    reference_image = None
    if use_refs and req.previousImage:
        try:
            reference_bytes = base64.b64decode(req.previousImage.split(",")[-1])
            reference_image = io.BytesIO(reference_bytes)
            reference_image.name = "previous.png"
        except Exception as exc:  # pylint: disable=broad-except
            raise HTTPException(status_code=400, detail="Invalid previous image data") from exc

    try:
        if use_refs and reference_image is not None:
            resp = client.images.edit(
                model="gpt-image-1",
                prompt=prompt_value,
                image=reference_image,
                size=size,
            )
        else:
            resp = client.images.generate(
                model="gpt-image-1",
                prompt=prompt_value,
                size=size,
            )
        data = getattr(resp, "data", None)
        if not data:
            raise HTTPException(status_code=502, detail="Image missing response data")

        def _extract_b64(entry):
            if isinstance(entry, dict):
                return entry.get("b64_json")
            return getattr(entry, "b64_json", None)

        image_bytes = _decode_image_b64(_extract_b64(data[0]), panel_position)
    except HTTPException:
        raise
    except APIError as e:  # OpenAI specific errors
        log.exception("OpenAI image generation error")
        raise HTTPException(status_code=502, detail=f"Upstream OpenAI error: {e}")
    except httpx.HTTPError as e:
        log.exception("Network error to OpenAI during image generation")
        raise HTTPException(status_code=502, detail=f"Network error: {e}")
    except Exception as e:  # pylint: disable=broad-except
        log.exception("Unhandled server error during image generation")
        raise HTTPException(status_code=500, detail=f"Server error: {e}")

    encoded_image = base64.b64encode(image_bytes).decode("ascii")
    filename = _panel_filename(target_panel)

    return {
        "filename": filename,
        "imageBase64": encoded_image,
        "panelIndex": target_panel.n,
        "panelPosition": req.panelIndex,
        "totalPanels": len(panels),
        "size": size,
    }
