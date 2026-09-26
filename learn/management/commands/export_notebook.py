"""Export the notebook pages as one HTML file (uploads to Google Drive as a Google Doc).

    python manage.py export_notebook [--output materials/out/notes/00-my-learning-journal.html]
"""
import html
import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from learn.exercises import load_exercises
from learn.models import ExerciseProgress, NotebookEntry

CSS = """
body { font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.55; color: #1c2330; max-width: 820px; }
code, pre { font-family: Consolas, monospace; }
pre { background: #f3f4f6; padding: 8px 12px; border-radius: 6px; }
"""


def esc(text):
    """Escape text, turning `code` spans into <code>."""
    return re.sub(r'`([^`]+)`', r'<code>\1</code>', html.escape(str(text or '')))


class Command(BaseCommand):
    help = 'Export the learning notebook as one HTML page.'

    def add_arguments(self, parser):
        default = Path(settings.BASE_DIR) / 'materials' / 'out' / 'notes' / '00-my-learning-journal.html'
        parser.add_argument('--output', default=str(default))

    def handle(self, *args, **options):
        entries = {e.slug: e for e in NotebookEntry.objects.all()}
        progress = {p.slug: p for p in ExerciseProgress.objects.all()}
        sections = []
        for exercise in load_exercises():
            entry = entries.get(exercise.slug)
            if not entry:
                continue
            page = entry.data
            parts = [f'<h1>#{exercise.number:02d} {esc(exercise.title)}</h1>', f'<p>{esc(page.get("summary"))}</p>']
            parts.append('<h2>Tools I learned</h2>')
            for tool in page.get('tools', []):
                parts.append(f'<h3>{esc(tool.get("name"))}</h3><p>{esc(tool.get("what_it_does"))}</p>')
                if tool.get('example'):
                    parts.append(f'<pre>{html.escape(tool["example"])}</pre>')
                if tool.get('output'):
                    parts.append(f'<p>Output:</p><pre>{html.escape(tool["output"])}</pre>')
            parts.append(f'<h2>Where it\'s used</h2><p>{esc(page.get("use_case"))}</p>')
            if page.get('difficulties'):
                parts.append('<h2>What I found difficult, and how I solved it</h2>')
                for d in page['difficulties']:
                    parts.append(f'<h3>{esc(d.get("what"))}</h3><p>{esc(d.get("why_it_was_hard"))}</p>'
                                 f'<p><strong>How I solved it:</strong> {esc(d.get("how_you_solved_it"))}</p>')
            parts.append('<h2>Takeaways</h2><ul>' + ''.join(f'<li>{esc(t)}</li>' for t in page.get('takeaways', [])) + '</ul>')
            parts.append(f'<h2>Next step</h2><p>{esc(page.get("next_step"))}</p>')
            code = progress.get(exercise.slug).code if progress.get(exercise.slug) else ''
            if code:
                parts.append(f'<h2>My final code</h2><pre>{html.escape(code)}</pre>')
            sections.append('\n'.join(parts))

        output = Path(options['output'])
        output.parent.mkdir(parents=True, exist_ok=True)
        body = '<hr>'.join(sections) or '<p>No notebook pages yet. Pass an exercise and write its page first.</p>'
        output.write_text(
            f'<!doctype html><html><head><meta charset="utf-8"><title>My learning journal</title>'
            f'<style>{CSS}</style></head><body><p><strong>Backend Lab · My learning journal</strong></p>{body}</body></html>',
            encoding='utf-8',
        )
        self.stdout.write(f'Wrote {len(sections)} page(s) to {output}')
