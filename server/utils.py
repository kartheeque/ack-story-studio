import re
from typing import List, Tuple
from models import Panel

PROMPT_HEADER_RE = re.compile(r"^\[PROMPT\s*(\d{1,2})\]\s*(.*)$", re.IGNORECASE)

def parse_block_to_background_and_panels(text: str) -> Tuple[str, List[Panel]]:
    """
    Split a single text block into:
      - background (string above the first [PROMPT 1] header)
      - 8 panels (list of Panel)
    The format expected:

    [BASIC BACKGROUND / CONTEXT]
    ...anything...

    [PROMPT 1] Optional Title
    ...prompt text 1...

    [PROMPT 2] Optional Title
    ...prompt text 2...
    ...
    [PROMPT 8] Optional Title
    ...prompt text 8...
    """
    lines = text.splitlines()
    indices = []
    for i, line in enumerate(lines):
        m = PROMPT_HEADER_RE.match(line.strip())
        if m:
            n = int(m.group(1))
            title = (m.group(2) or "").strip()
            indices.append((i, n, title))

    if not indices:
        # No prompt headers found; treat all as background and 0 panels
        return text.strip(), []

    # background: everything before first header
    first_idx, _, _ = indices[0]
    background = "\n".join(lines[:first_idx]).strip()

    panels: List[Panel] = []
    for idx, (start_line, n, title) in enumerate(indices):
        end_line = indices[idx + 1][0] if idx + 1 < len(indices) else len(lines)
        body_lines = lines[start_line + 1:end_line]
        body = "\n".join(body_lines).strip()
        if not title:
            title = f"Panel {n}"
        panels.append(Panel(n=n, title=title, prompt=body))

    return background, panels


def render_block_from_background_and_panels(background: str, panels: List[Panel]) -> str:
    """
    Build a single right-panel text block from background + 8 panels.
    """
    parts = []
    if background.strip():
        parts.append("[BASIC BACKGROUND / CONTEXT]")
        parts.append(background.strip())
        parts.append("")  # spacer line

    for p in sorted(panels, key=lambda x: x.n):
        parts.append(f"[PROMPT {p.n}] {p.title}".rstrip())
        parts.append(p.prompt.strip())
        parts.append("")

    return "\n".join(parts).rstrip()
