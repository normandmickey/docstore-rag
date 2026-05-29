from django import template
from django.utils.safestring import mark_safe

import bleach
import markdown

register = template.Library()

_ALLOWED_TAGS = [
    'p', 'br', 'strong', 'em', 'code', 'pre', 'blockquote',
    'ul', 'ol', 'li', 'a', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'hr'
]
_ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title', 'target', 'rel'],
}
_ALLOWED_PROTOCOLS = ['http', 'https', 'mailto']


@register.filter(name='render_markdown')
def render_markdown(value):
    text = (value or '').strip()
    if not text:
        return ''
    rendered = markdown.markdown(
        text,
        extensions=['extra', 'sane_lists', 'nl2br', 'fenced_code'],
        output_format='html5',
    )
    cleaned = bleach.clean(
        rendered,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRIBUTES,
        protocols=_ALLOWED_PROTOCOLS,
        strip=True,
    )
    cleaned = bleach.linkify(cleaned)
    return mark_safe(cleaned)
