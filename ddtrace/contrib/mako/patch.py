import logging

# project
from ddtrace import Pin
from ...ext import http

# 3p
import mako
from mako.template import Template

log = logging.getLogger(__name__)


def patch():
    # FIXME:currently, just patch template.render*, should support other module later
    if getattr(mako, '_datadog_patch', False):
        return
    setattr(mako, '_datadog_patch', True)

    pin = Pin(service="mako", app="mako", app_type=http.TEMPLATE)  # .onto(mako.template.Template)
    tracer = pin.tracer
    patch_template_render(tracer)
    patch_template_render_unicode(tracer)
    patch_template_render_context(tracer)


def unpatch():
    if getattr(mako, '_datadog_patch', False):
        setattr(mako, '_datadog_patch', False)

        if getattr(Template, '_datadog_original_render', None):
            Template.render = Template._datadog_original_render

        if getattr(Template, '_datadog_original_render_unicode', None):
            Template.render_unicode = Template._datadog_original_render_unicode

        if getattr(Template, '_datadog_original_render_context', None):
            Template.render_context = Template._datadog_original_render_context


def patch_template_render(tracer):
    attr = '_datadog_original_render'

    if getattr(Template, attr, None):
        log.debug("already patched")
        return
    setattr(Template, attr, Template.render)

    def traced_render(self, *args, **data):
        with tracer.trace('mako.template.render', span_type=http.TEMPLATE) as span:
            try:
                return Template._datadog_original_render(self, *args, **data)
            finally:
                template_name = getattr(self, 'filename', None) or 'unknown'
                span.resource = template_name
                span.set_tag('mako.template_name', template_name)

    Template.render = traced_render


def patch_template_render_unicode(tracer):
    attr = '_datadog_original_render_unicode'

    if getattr(Template, attr, None):
        log.debug("already patched")
        return
    setattr(Template, attr, Template.render_unicode)

    def traced_render_unicode(self, *args, **data):
        with tracer.trace('mako.template.render_unicode', span_type=http.TEMPLATE) as span:
            try:
                return Template._datadog_original_render_unicode(self, *args, **data)
            finally:
                template_name = getattr(self, 'filename', None) or 'unknown'
                span.resource = template_name
                span.set_tag('mako.template_name', template_name)

    Template.render_unicode = traced_render_unicode


def patch_template_render_context(tracer):
    attr = '_datadog_original_render_context'

    if getattr(Template, attr, None):
        log.debug("already patched")
        return
    setattr(Template, attr, Template.render_context)

    def traced_render_context(self, context, *args, **data):
        with tracer.trace('mako.template.render_context', span_type=http.TEMPLATE) as span:
            try:
                return Template._datadog_original_render_context(self, context, *args, **data)
            finally:
                template_name = getattr(self, 'filename', None) or 'unknown'
                span.resource = template_name
                span.set_tag('mako.template_name', template_name)

    Template.render_context = traced_render_context
