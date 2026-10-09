"""Diagrams and mind maps in lessons and slides, written as Mermaid text and drawn in the browser.

The AI writes diagrams as text (https://mermaid.js.org). Before anything is
saved, each diagram is checked here: it must be one of the kinds we draw, short,
and free of the parts of Mermaid that could change the page (init directives,
click handlers, raw HTML). A diagram that fails is dropped, not the whole path:
the lesson still reads fine without it. The browser draws them with the
self-hosted mermaid script in strict mode, and hides any it can't draw.
"""
import re

KINDS = ('mindmap', 'flowchart', 'graph', 'sequenceDiagram', 'erDiagram', 'classDiagram', 'stateDiagram-v2',
         'stateDiagram', 'timeline')
MAX_CHARS = 2000
MAX_LINES = 40
_FORBIDDEN = re.compile(r'%%\{|<\s*/?\s*[a-z]|javascript:|^\s*(?:click|style|classDef|linkStyle)\b',
                        re.IGNORECASE | re.MULTILINE)
_FENCE = re.compile(r'```mermaid[ \t]*\n(.*?)```', re.DOTALL)


def clean_diagram(text):
    """The diagram text if it is safe and one of the kinds we draw, else ''."""
    if not isinstance(text, str):
        return ''
    text = text.strip()
    match = re.fullmatch(r'```(?:mermaid)?\s*\n(.*?)\n?```', text, re.DOTALL)
    if match:
        text = match.group(1).strip()
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    if not lines or len(lines) > MAX_LINES or len(text) > MAX_CHARS:
        return ''
    if lines[0].split()[0] not in KINDS or _FORBIDDEN.search(text):
        return ''
    return '\n'.join(lines)


def clean_lesson(lesson, limit=2):
    """Keep up to `limit` safe ```mermaid blocks in a Markdown lesson and drop the rest."""
    kept = 0

    def keep(match):
        nonlocal kept
        diagram = clean_diagram(match.group(1))
        if not diagram or kept >= limit:
            return ''
        kept += 1
        return f'```mermaid\n{diagram}\n```'

    return _FENCE.sub(keep, lesson)
