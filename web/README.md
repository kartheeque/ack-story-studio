# Frontend (React + Vite)

## What it does
- Left: Story input (any language).
- Right: A single editable block:
  - `[BASIC BACKGROUND / CONTEXT]` → global style, character bible, consistency rules
  - `[PROMPT 1] ...` → eight prompts, each one a detailed image prompt
- Buttons:
  - **Generate Background + 8 Prompts** → calls the backend `/api/prompts`
  - **Generate Images (ZIP)** → posts the **entire block** to `/api/generate`, optionally with “Use previous images as references” enabled.

## Dev setup
```bash
npm install
npm run dev
# Opens the app (usually http://localhost:5173)
