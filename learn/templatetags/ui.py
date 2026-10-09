from django import template
from django.templatetags.static import static
from django.utils.html import format_html

register = template.Library()


@register.simple_tag
def icon(name, label='', css=''):
    """A Lucide icon from learn/static/learn/icons.svg, coloured by the text around it.

    Icons sit next to a text label, so they are hidden from screen readers unless
    they stand alone, in which case pass a `label`.
    """
    classes = f'icon {css}'.strip()
    href = f"{static('learn/icons.svg')}#{name}"
    if label:
        return format_html(
            '<svg class="{}" role="img" aria-label="{}" fill="none" stroke="currentColor" stroke-linecap="round" '
            'stroke-linejoin="round"><use href="{}"/></svg>', classes, label, href)
    return format_html(
        '<svg class="{}" aria-hidden="true" fill="none" stroke="currentColor" stroke-linecap="round" '
        'stroke-linejoin="round"><use href="{}"/></svg>', classes, href)


@register.inclusion_tag('learn/_art.html')
def path_art(path):
    """The small capstone mock-up at the top of a path card."""
    from learn.languages import art_for
    return {'art': art_for(path)}


@register.inclusion_tag('learn/_practice.html')
def practice_tag(path, exercise_count=0):
    """The hands-on / hands-on soon / reading badge on a path card, from learn/languages.py."""
    from learn.languages import practice
    return {'practice': practice(path, exercise_count)}
