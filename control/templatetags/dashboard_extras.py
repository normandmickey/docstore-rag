from django import template

register = template.Library()


@register.filter(name='get_item')
def get_item(value, key):
    if isinstance(value, dict):
        return value.get(key, '')
    return ''
