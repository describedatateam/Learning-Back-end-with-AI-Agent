"""My project: turn a learner's own project into an SRS and a milestone walkthrough.

A learner either describes a project (what it does, who it's for, the tech) and the
AI writes a Software Requirements Specification for it, or uploads an SRS they
already have (PDF, Word, Markdown or text) and the AI maps it into the same shape,
listing what's missing (no data models, no "done" checks...) as gaps to fill in.

Either way the SRS ends with milestones: ordered steps with tasks to tick off,
each linked to the catalog chapters that teach what it needs. Gemini is asked
through generator.ask, and the reply is checked like a generated path: a reply
that doesn't pass is sent back once with the problems listed.
"""
import io
import json
import os
import re
import zipfile
from datetime import timedelta
from xml.etree import ElementTree

from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext

from . import generator
from .generator import GenerationError, parse_json
from .models import Chapter, LearningEvent, Project

DAILY_LIMIT = int(os.environ.get('LEARN_PROJECT_DAILY_LIMIT', 5))  # SRS writes per learner per day
MAX_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_SRS_CHARS = 30000      # text of an uploaded SRS sent to the model
MAX_FIELD_CHARS = 1500     # each box of the describe form
UPLOAD_TYPES = ('.pdf', '.docx', '.md', '.markdown', '.txt')
PRIORITIES = ('must', 'should', 'could')
METHODS = ('GET', 'POST', 'PUT', 'PATCH', 'DELETE')
# The sections a full SRS has; an uploaded one missing any of them gets a gap for it.
SECTIONS = ('goals', 'users', 'stories', 'data_models', 'endpoints', 'done_checks')

SRS_PROMPT = """\
You help beginner and junior web developers on Describe, a learning platform (Python, Django, \
HTML, CSS, JavaScript, SQL), plan a project of their own. You write or read a Software \
Requirements Specification (SRS) and turn it into a step-by-step walkthrough they can tick off.

Reply with a single JSON object and nothing else, in exactly this shape:
{
  "title": "the project's name, under 60 characters",
  "summary": "two sentences: what it does and who it is for",
  "goals": ["one measurable goal per item", "..."],
  "users": [{"name": "a type of user", "needs": "one sentence on what they need from the app"}],
  "stories": [{"role": "a type of user", "want": "what they want to do", "benefit": "why",
               "priority": "must" | "should" | "could"}],
  "data_models": [{"name": "ModelName", "fields": ["field_name: type", "..."], "relations": "one sentence, or empty"}],
  "endpoints": [{"method": "GET" | "POST" | "PUT" | "PATCH" | "DELETE", "path": "/api/...", "purpose": "one sentence"}],
  "done_checks": ["a check anyone can try to see a feature works", "..."],
  "gaps": [{"section": "goals" | "users" | "stories" | "data_models" | "endpoints" | "done_checks" | "other",
            "note": "one sentence on what is missing or unclear and the question the learner should answer"}],
  "milestones": [{"title": "...", "goal": "one sentence on what works at the end of this step",
                  "tasks": ["a small task of 1 to 3 hours", "..."],
                  "chapters": ["chapter slugs from the list below that teach what this step needs"]}]
}

Rules:
- 3 to 6 goals, 1 to 4 users, 4 to 12 stories, 1 to 8 data models, 0 to 15 endpoints, 3 to 10 done checks.
- 4 to 7 milestones in build order (set up, data models, core features, pages, tests, deploy), each with 2 to 6 tasks.
- Keep it small enough for one learner to build in 2 to 6 weeks; put extras in "could" stories.
- "chapters": 0 to 3 slugs per milestone, copied exactly from the chapter list. Use [] when none fits.
- Plain, friendly language, sentence-case titles, no emojis, no HTML, no links.
- Write all prose in {language}. Code, model, field and file names, paths and technical names stay in English.
{mode_rules}

Chapters the learner can study (slug: title):
{chapters}\
"""

DESCRIBE_RULES = """\
- You are writing the SRS from the learner's description. Fill in sensible details they left out, \
and use "gaps" (0 to 4 items) only for real decisions they must make themselves."""

UPLOAD_RULES = """\
- You are reading an SRS the learner wrote. Keep their goals, users, features and names; don't invent \
new features. Where their document has no data models, endpoints or done checks, propose them from what \
it does say, and add a gap for each section you had to fill in or found unclear (0 to 8 gaps). \
Leave "endpoints" empty if the project has no API."""


class UploadError(Exception):
    """A file the learner can fix: wrong type, too big, or no readable text."""


# --- Reading an uploaded SRS ---------------------------------------------------

def _pdf_text(data):
    from pypdf import PdfReader
    try:
        reader = PdfReader(io.BytesIO(data))
        return '\n'.join(page.extract_text() or '' for page in reader.pages[:60])
    except Exception:  # pypdf raises many kinds of error for broken files
        raise UploadError(gettext('This PDF could not be read. Try saving it again, or upload it as Word or text.'))


def _docx_text(data):
    """The paragraphs of a Word file, without a library: a .docx is a zip with word/document.xml inside."""
    w = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            root = ElementTree.fromstring(archive.read('word/document.xml'))
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError):
        raise UploadError(gettext('This Word file could not be read. Save it as .docx (not .doc) and try again.'))
    lines = []
    for para in root.iter(f'{w}p'):
        text = ''.join(node.text or '' for node in para.iter() if node.tag in (f'{w}t', f'{w}tab'))
        if text.strip():
            lines.append(text)
    return '\n'.join(lines)


def read_upload(upload):
    """The text of an uploaded SRS file. Raises UploadError."""
    name = (upload.name or '').lower()
    if not name.endswith(UPLOAD_TYPES):
        raise UploadError(gettext('Upload a PDF, Word (.docx), Markdown or text file.'))
    if upload.size > MAX_UPLOAD_BYTES:
        raise UploadError(gettext('This file is bigger than 2 MB. Upload a smaller one.'))
    data = upload.read()
    if name.endswith('.pdf'):
        text = _pdf_text(data)
    elif name.endswith('.docx'):
        text = _docx_text(data)
    else:
        text = data.decode('utf-8', errors='replace')
    text = re.sub(r'[ \t]+', ' ', re.sub(r'\n\s*\n+', '\n\n', text)).strip()
    if len(text) < 80:
        raise UploadError(gettext('No readable text was found in this file. If it is a scanned PDF, '
                                  'upload it as Word or text instead.'))
    return text[:MAX_SRS_CHARS]


# --- Asking the model ----------------------------------------------------------

def written_today(user):
    since = timezone.now() - timedelta(days=1)
    return LearningEvent.objects.filter(user=user, kind=LearningEvent.PROJECT_SRS, created_at__gte=since).count()


def study_chapters(user):
    """Catalog chapters and the learner's own generated ones, in catalog order."""
    return list(Chapter.objects.filter(Q(course__path__owner__isnull=True) | Q(course__path__owner=user))
                .select_related('course__path').order_by('course__path__order', 'course__path_id',
                                                         'course__order', 'order'))


def build_system(user, mode, language='en'):
    chapters = '\n'.join(f'{c.slug}: {c.title}' for c in study_chapters(user)) or '(none yet)'
    return (SRS_PROMPT.replace('{language}', 'Arabic' if language == 'ar' else 'English')
            .replace('{mode_rules}', UPLOAD_RULES if mode == Project.UPLOADED else DESCRIBE_RULES)
            .replace('{chapters}', chapters))


def describe_prompt(brief):
    return (f'Project name: {brief.get("title") or "(not named yet)"}\n'
            f'What it does: {brief.get("what", "")}\n'
            f'Who it is for: {brief.get("who") or "(not said)"}\n'
            f'Tech they want to use: {brief.get("tech") or "(not said; suggest Django with HTML, CSS and JavaScript)"}\n'
            'Write the SRS and the walkthrough.')


def upload_prompt(text, filename=''):
    return (f'Here is the SRS the learner uploaded{f" ({filename})" if filename else ""}:\n'
            f'<srs>\n{text}\n</srs>\n'
            'Map it into the JSON shape, list the gaps, and write the walkthrough.')


def update_prompt(project, answers):
    return ('Here is the current SRS of the learner\'s project as JSON:\n'
            f'{json.dumps(project.srs, ensure_ascii=False)}\n\n'
            f'The learner answered the gaps or added these details:\n<answers>\n{answers}\n</answers>\n'
            'Reply with the whole updated JSON object. Keep everything that still holds, work their answers in, '
            'remove the gaps they answered, and keep the milestone order unless their answers change it.')


def write_srs(user, mode, prompt, language='en'):
    """Ask the model for an SRS and return it checked and cleaned. Raises GenerationError."""
    system = build_system(user, mode, language)
    valid = {c.slug for c in study_chapters(user)}
    messages = [{'role': 'user', 'content': prompt}]
    errors = []
    for _ in range(2):
        reply = generator.ask(system, messages)
        try:
            data = parse_json(reply)
        except ValueError as exc:
            errors = [str(exc)]
        else:
            cleaned, errors = clean_srs(data, valid)
            if not errors:
                if mode == Project.UPLOADED:
                    add_missing_gaps(cleaned)
                return cleaned
        messages += [
            {'role': 'assistant', 'content': reply},
            {'role': 'user', 'content': 'Your reply had these problems:\n- ' + '\n- '.join(errors[:15])
                + '\nReply again with the whole corrected JSON object.'},
        ]
    raise GenerationError(gettext('The AI\'s SRS didn\'t pass the checks, so nothing was saved. Please try again.')
                          + f' ({"; ".join(errors[:3])})')


# --- Checking the JSON ---------------------------------------------------------

def _text(value, where, errors, limit=400, required=True):
    if not isinstance(value, str) or (required and not value.strip()):
        if required or value not in (None, ''):
            errors.append(f'{where} must be {"non-empty " if required else ""}text.')
        return ''
    return ' '.join(value.split())[:limit]


def _list(value, where, errors, low, high):
    if not isinstance(value, list) or not low <= len(value) <= high:
        errors.append(f'{where} must be a list of {low} to {high} items.')
        return []
    return value


def _dict(value, where, errors):
    if not isinstance(value, dict):
        errors.append(f'{where} must be an object.')
        return {}
    return value


def clean_srs(data, valid_chapters=()):
    """(cleaned SRS, problems). The cleaned SRS is only usable when there are no problems."""
    errors = []
    data = _dict(data, 'The reply', errors)
    srs = {
        'title': _text(data.get('title'), 'title', errors, 80),
        'summary': _text(data.get('summary'), 'summary', errors, 500),
        'goals': [_text(g, f'goals[{i}]', errors) for i, g in enumerate(_list(data.get('goals'), 'goals', errors, 1, 8))],
        'users': [], 'stories': [], 'data_models': [], 'endpoints': [], 'gaps': [], 'milestones': [],
        'done_checks': [_text(c, f'done_checks[{i}]', errors)
                        for i, c in enumerate(_list(data.get('done_checks'), 'done_checks', errors, 0, 12))],
    }
    for i, u in enumerate(_list(data.get('users'), 'users', errors, 1, 6)):
        u = _dict(u, f'users[{i}]', errors)
        srs['users'].append({'name': _text(u.get('name'), f'users[{i}].name', errors, 80),
                             'needs': _text(u.get('needs'), f'users[{i}].needs', errors)})
    for i, s in enumerate(_list(data.get('stories'), 'stories', errors, 1, 16)):
        s = _dict(s, f'stories[{i}]', errors)
        priority = str(s.get('priority', '')).lower()
        if priority not in PRIORITIES:
            errors.append(f'stories[{i}].priority must be one of {", ".join(PRIORITIES)}.')
        srs['stories'].append({'role': _text(s.get('role'), f'stories[{i}].role', errors, 80),
                               'want': _text(s.get('want'), f'stories[{i}].want', errors),
                               'benefit': _text(s.get('benefit'), f'stories[{i}].benefit', errors, 400, False),
                               'priority': priority})
    for i, m in enumerate(_list(data.get('data_models'), 'data_models', errors, 0, 10)):
        m = _dict(m, f'data_models[{i}]', errors)
        fields = _list(m.get('fields'), f'data_models[{i}].fields', errors, 1, 15)
        srs['data_models'].append({'name': _text(m.get('name'), f'data_models[{i}].name', errors, 60),
                                   'fields': [_text(f, f'data_models[{i}].fields', errors, 120) for f in fields],
                                   'relations': _text(m.get('relations'), f'data_models[{i}].relations', errors, 300, False)})
    for i, e in enumerate(_list(data.get('endpoints'), 'endpoints', errors, 0, 20)):
        e = _dict(e, f'endpoints[{i}]', errors)
        method = str(e.get('method', '')).upper()
        if method not in METHODS:
            errors.append(f'endpoints[{i}].method must be one of {", ".join(METHODS)}.')
        srs['endpoints'].append({'method': method, 'path': _text(e.get('path'), f'endpoints[{i}].path', errors, 120),
                                 'purpose': _text(e.get('purpose'), f'endpoints[{i}].purpose', errors)})
    for i, g in enumerate(_list(data.get('gaps', []), 'gaps', errors, 0, 10)):
        g = _dict(g, f'gaps[{i}]', errors)
        section = str(g.get('section', 'other'))
        srs['gaps'].append({'section': section if section in SECTIONS else 'other',
                            'note': _text(g.get('note'), f'gaps[{i}].note', errors)})
    valid_chapters = set(valid_chapters)
    for i, m in enumerate(_list(data.get('milestones'), 'milestones', errors, 2, 8), 1):
        m = _dict(m, f'milestones[{i}]', errors)
        tasks = _list(m.get('tasks'), f'milestones[{i}].tasks', errors, 1, 8)
        chapters = m.get('chapters') if isinstance(m.get('chapters'), list) else []
        srs['milestones'].append({
            'id': f'm{i}',
            'title': _text(m.get('title'), f'milestones[{i}].title', errors, 100),
            'goal': _text(m.get('goal'), f'milestones[{i}].goal', errors, 300, False),
            'tasks': [{'id': f'm{i}-t{n}', 'text': _text(t, f'milestones[{i}].tasks', errors, 300)}
                      for n, t in enumerate(tasks, 1)],
            # Unknown slugs are dropped rather than sent back: a missing link is better than a retry.
            'chapters': [c for c in dict.fromkeys(chapters) if isinstance(c, str) and c in valid_chapters][:3],
        })
    return srs, errors


def add_missing_gaps(srs):
    """An uploaded SRS gets a gap for each empty section, even if the model forgot to list it."""
    noted = {g['section'] for g in srs['gaps']}
    notes = {
        'data_models': gettext('Your SRS has no data models. Which things does the app store, and what does each one hold?'),
        'done_checks': gettext('Your SRS has no "done" checks. How will you know each feature works?'),
    }
    for section, note in notes.items():
        if not srs[section] and section not in noted:
            srs['gaps'].append({'section': section, 'note': note})


# --- Walkthrough progress --------------------------------------------------------

def task_ids(srs):
    return [t['id'] for m in srs.get('milestones', []) for t in m['tasks']]


def carry_ticks(old_srs, done, new_srs):
    """After an update, a task stays ticked if a task with the same text is still there (ids can shift)."""
    ticked = {t['text'] for m in old_srs.get('milestones', []) for t in m['tasks'] if t['id'] in set(done)}
    return [t['id'] for m in new_srs.get('milestones', []) for t in m['tasks'] if t['text'] in ticked]


def progress(project):
    ids = task_ids(project.srs)
    done = len(set(project.done) & set(ids))
    return {'done': done, 'total': len(ids), 'percent': round(100 * done / len(ids)) if ids else 0}


def toggle(project, task_id, checked):
    if task_id not in task_ids(project.srs):
        return False
    done = [t for t in project.done if t != task_id] + ([task_id] if checked else [])
    project.done = done
    project.save(update_fields=['done', 'updated_at'])
    return True


def chapter_link(chapter):
    """Where a milestone's chapter opens: its lesson, its first exercise, or its path."""
    if chapter.content:
        return reverse('learn:chapter', args=[chapter.course.path.slug, chapter.slug])
    if chapter.exercises:
        return reverse('learn:exercise', args=[chapter.exercises[0]])
    return reverse('learn:path', args=[chapter.course.path.slug])


def milestones(project):
    """The milestones with their tasks ticked or not, and links to their chapters."""
    slugs = {s for m in project.srs.get('milestones', []) for s in m['chapters']}
    chapters = {c.slug: c for c in Chapter.objects.filter(slug__in=slugs).select_related('course__path')}
    done, current, rows = set(project.done), None, []
    for number, m in enumerate(project.srs.get('milestones', []), 1):
        tasks = [{**t, 'done': t['id'] in done} for t in m['tasks']]
        finished = all(t['done'] for t in tasks)
        if not finished and current is None:
            current = number
        rows.append({**m, 'number': number, 'tasks': tasks, 'finished': finished, 'current': current == number,
                     'links': [{'title': chapters[s].title, 'url': chapter_link(chapters[s])}
                               for s in m['chapters'] if s in chapters]})
    return rows


def tutor_context(project):
    """What the tutor knows about the learner's project."""
    srs, done = project.srs, set(project.done)
    lines = [f'<project title="{project.title}">',
             'Right now the learner is working on their own project, described by the SRS below. Help them '
             'plan and build it step by step: explain what a milestone needs, suggest how to start a task, '
             'review their approach, and point them to the linked chapters. Give hints and small examples rather '
             'than writing the whole project for them. Reply in the language the learner writes in; code and '
             'technical names stay in English.',
             f'Summary: {srs.get("summary", "")}',
             'Goals: ' + '; '.join(srs.get('goals', [])),
             'Users: ' + '; '.join(f'{u["name"]} ({u["needs"]})' for u in srs.get('users', [])),
             'Stories:'] + [f'- [{s["priority"]}] As {s["role"]}, I want {s["want"]}' + (f', so that {s["benefit"]}' if s['benefit'] else '')
                            for s in srs.get('stories', [])]
    lines.append('Data models:')
    lines += [f'- {m["name"]}: ' + ', '.join(m['fields']) + (f' ({m["relations"]})' if m['relations'] else '')
              for m in srs.get('data_models', [])]
    if srs.get('endpoints'):
        lines.append('Endpoints:')
        lines += [f'- {e["method"]} {e["path"]}: {e["purpose"]}' for e in srs['endpoints']]
    lines.append('Done checks: ' + '; '.join(srs.get('done_checks', [])))
    if srs.get('gaps'):
        lines.append('Open gaps: ' + '; '.join(g['note'] for g in srs['gaps']))
    lines.append('Milestones (x = ticked by the learner):')
    for m in srs.get('milestones', []):
        lines.append(f'{m["id"]}. {m["title"]}: {m["goal"]}')
        lines += [f'  [{"x" if t["id"] in done else " "}] {t["text"]}' for t in m['tasks']]
    lines.append('</project>')
    return '\n'.join(lines)
