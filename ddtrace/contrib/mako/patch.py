# import wrapt
import logging

# project
from ddtrace import Pin
from ddtrace.util import unwrap
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

    # _w = wrapt.wrap_function_wrapper
    # _w('mako.template', 'Template.render', traced_render)
    # _w('mako.template', 'Template.render_unicode', traced_render_unicode)
    # _w('mako.template', 'Template.render_context', traced_render_context)
    pin = Pin(service="mako", app="mako", app_type=http.TEMPLATE)  # .onto(mako.template.Template)
    tracer = pin.tracer
    patch_template_render(tracer)
    patch_template_render_unicode(tracer)
    # create tracer, then, use it


def unpatch():
    if getattr(mako, '_datadog_patch', False):
        setattr(mako, '_datadog_patch', False)
        unwrap(mako.template.Template, 'render')
        unwrap(mako.template.Template, 'render_unicode')
        unwrap(mako.template.Template, 'render_context')


# def patch_template(tracer):
    # def traced_render(self, context):
        # with tracer.trace('mako.template', span_type=http.TEMPLATE) as span:
            # try:
                # return Template._datadog_original_render(self, context)
            # finally:
                # template_name = self.name or getattr(context, 'template_name', None) or 'unknown'
                # span.resource = template_name
                # span.set_tag('mako.template_name', template_name)

    # Template.render = traced_render

# function 1, patch object

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
                template_name = self.filename or getattr(self, 'template_name', None) or 'unknown'
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
                template_name = self.filename or getattr(self, 'template_name', None) or 'unknown'
                span.resource = template_name
                span.set_tag('mako.template_name', template_name)

    Template.render_unicode = traced_render_unicode


# function2

# def traced_render(func, instance, args, kwargs):
    # print "call render:", args, kwargs
    # pin = Pin.get_from(instance)
    # print "pin:", pin
    # if not pin or not pin.enabled():
        # return func(*args, **kwargs)

    # with pin.tracer.trace('mako.render', service=pin.service, span_type=http.TEMPLATE) as s:
        # return func(*args, **kwargs)


# def traced_render_unicode(func, instance, args, kwargs):
    # pin = Pin.get_from(instance)
    # if not pin or not pin.enabled():
        # return func(*args, **kwargs)

    # with pin.tracer.trace('mako.render_unicode', service=pin.service, span_type=http.TEMPLATE) as s:
        # return func(*args, **kwargs)


# def traced_render_context(func, instance, args, kwargs):
    # pin = Pin.get_from(instance)
    # if not pin or not pin.enabled():
        # return func(*args, **kwargs)

    # with pin.tracer.trace('mako.render_context', service=pin.service, span_type=http.TEMPLATE) as s:
        # return func(*args, **kwargs)
