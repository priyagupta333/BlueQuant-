from django import template

register = template.Library()

@register.filter(name='add_class')
def add_class(field, css):
    """Add class and optional extra attributes to a form field.

    Usage in templates:
      {{ field|add_class:"classes here" }}
      {{ field|add_class:"classes here|id=pincode" }}
      {{ field|add_class:"classes|id=myid|placeholder=Enter" }}
    """
    try:
        # allow passing extra attrs after a '|' separator, e.g. 'cls1 cls2|id=pincode|data-x=1'
        class_part = css
        extra_attrs = {}
        if '|' in css:
            parts = css.split('|')
            class_part = parts[0]
            for seg in parts[1:]:
                if '=' in seg:
                    k, v = seg.split('=', 1)
                    extra_attrs[k.strip()] = v.strip().strip('"\'')
        attrs = {**field.field.widget.attrs, 'class': class_part}
        attrs.update(extra_attrs)
        return field.as_widget(attrs=attrs)
    except Exception:
        return field
