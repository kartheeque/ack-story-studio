# ACK Story Studio (Context + 8 Prompts → Images)

A simple two-panel UI:

- **Left**: Paste a story (any language).
- **Right**: A single block containing a **BASIC BACKGROUND / CONTEXT** + **eight detailed prompts**.
- Edit anything on the right, then **Generate Images (ZIP)**.

The backend uses OpenAI:

- A text model (default `gpt-4.1`) to create the **Background + 8 Prompts**.
- `gpt-image-1` to generate 8 images **sequentially**.
- Optional: “Use previous images as references” (image-edits with the last panel as a visual reference).

---

## Run locally (quick start)

1. **Backend**

```bash
cd server
python -m venv .venv
# (Windows) .venv\Scripts\activate
# (macOS/Linux) source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env and set OPENAI_API_KEY
uvicorn main:app --reload --port 8080
```
