# Backend (FastAPI)

## What it does

- **/api/prompts**: Accepts a story (any language), returns strict JSON:
  - `background`: global style + Character Bible + consistency rules
  - `panels`: 8 structured prompts `{n,title,prompt}`
  - `model`: the text model used
- **/api/generate**: Accepts a single edited block (the right-panel text), parses it into `background + 8 prompts`, then generates 8 images via `gpt-image-1`.
  - Optional `useImageReferences`: if true, from panel 2 onward the API passes the **previous image** to the **image edits** endpoint as a visual reference for consistency.

## Setup

1. Create and activate a venv, install deps:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
```
