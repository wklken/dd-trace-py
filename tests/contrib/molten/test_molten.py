# flake8: noqa
# DEV: Skip linting, we lint with Python 2, we'll get SyntaxErrors from annotations
from unittest import TestCase

import molten
from molten.testing import TestClient

from ddtrace import Pin
from ddtrace.ext import errors
from ddtrace.propagation.http import HTTP_HEADER_TRACE_ID, HTTP_HEADER_PARENT_ID
from ddtrace.contrib.molten import patch, unpatch
from ddtrace.contrib.molten.patch import MOLTEN_VERSION

from ...test_tracer import get_dummy_tracer
from ...util import override_config


# NOTE: Type annotations required by molten otherwise parameters cannot be coerced
def hello(name: str, age: int) -> str:
    return f'Hello {age} year old named {name}!'


def molten_client(headers=None):
    app = molten.App(routes=[molten.Route('/hello/{name}/{age}', hello)])
    client = TestClient(app)
    uri = app.reverse_uri('hello', name='Jim', age=24)
    if headers:
        return client.request('GET', uri, headers=headers)
    return client.get(uri)


class TestMolten(TestCase):
    """"Ensures Molten is properly instrumented."""

    TEST_SERVICE = 'molten-patch'

    def setUp(self):
        patch()
        self.tracer = get_dummy_tracer()
        Pin.override(molten, tracer=self.tracer)

    def tearDown(self):
        unpatch()
        self.tracer.writer.pop()
        delattr(self, 'tracer')

    def test_route_success(self):
        """ Tests request was a success with the expected span tags """
        response = molten_client()
        spans = self.tracer.writer.pop()
        self.assertEqual(response.status_code, 200)
        # TestResponse from TestClient is wrapper around Response so we must
        # access data property
        self.assertEqual(response.data, '"Hello 24 year old named Jim!"')
        span = spans[0]
        self.assertEqual(span.service, 'molten')
        self.assertEqual(span.name, 'molten.request')
        self.assertEqual(span.resource, 'GET /hello/{name}/{age}')
        self.assertEqual(span.get_tag('http.method'), 'GET')
        self.assertEqual(span.get_tag('http.url'), '/hello/Jim/24')
        self.assertEqual(span.get_tag('http.status_code'), '200')

        # See test_resources below for specifics of this difference
        if MOLTEN_VERSION >= (0, 7, 2):
            self.assertEqual(len(spans), 18)
        else:
            self.assertEqual(len(spans), 16)

        # test override of service name
        Pin.override(molten, service=self.TEST_SERVICE)
        response = molten_client()
        spans = self.tracer.writer.pop()
        self.assertEqual(spans[0].service, 'molten-patch')

    def test_route_failure(self):
        app = molten.App(routes=[molten.Route('/hello/{name}/{age}', hello)])
        client = TestClient(app)
        response = client.get('/goodbye')
        spans = self.tracer.writer.pop()
        self.assertEqual(response.status_code, 404)
        span = spans[0]
        self.assertEqual(span.service, 'molten')
        self.assertEqual(span.name, 'molten.request')
        self.assertEqual(span.resource, 'GET 404')
        self.assertEqual(span.get_tag('http.url'), '/goodbye')
        self.assertEqual(span.get_tag('http.method'), 'GET')
        self.assertEqual(span.get_tag('http.status_code'), '404')

    def test_route_exception(self):
        def route_error() -> str:
            raise Exception('Error message')
        app = molten.App(routes=[molten.Route('/error', route_error)])
        client = TestClient(app)
        response = client.get('/error')
        spans = self.tracer.writer.pop()
        self.assertEqual(response.status_code, 500)
        span = spans[0]
        route_error_span = spans[-1]
        self.assertEqual(span.service, 'molten')
        self.assertEqual(span.name, 'molten.request')
        self.assertEqual(span.resource, 'GET /error')
        self.assertEqual(span.error, 1)
        # error tags only set for route function span and not root span
        self.assertIsNone(span.get_tag(errors.ERROR_MSG))
        self.assertEqual(route_error_span.get_tag(errors.ERROR_MSG), 'Error message')

    def test_resources(self):
        """ Tests request has expected span resources """
        response = molten_client()
        spans = self.tracer.writer.pop()

        # `can_handle_parameter` appears twice since two parameters are in request
        # TODO[tahir]: missing ``resolve` method for components

        expected = [
            'GET /hello/{name}/{age}',
            'molten.middleware.ResponseRendererMiddleware',
            'molten.components.HeaderComponent.can_handle_parameter',
            'molten.components.CookiesComponent.can_handle_parameter',
            'molten.components.QueryParamComponent.can_handle_parameter',
            'molten.components.RequestBodyComponent.can_handle_parameter',
            'molten.components.RequestDataComponent.can_handle_parameter',
            'molten.components.SchemaComponent.can_handle_parameter',
            'molten.components.UploadedFileComponent.can_handle_parameter',
            'molten.components.HeaderComponent.can_handle_parameter',
            'molten.components.CookiesComponent.can_handle_parameter',
            'molten.components.QueryParamComponent.can_handle_parameter',
            'molten.components.RequestBodyComponent.can_handle_parameter',
            'molten.components.RequestDataComponent.can_handle_parameter',
            'molten.components.SchemaComponent.can_handle_parameter',
            'molten.components.UploadedFileComponent.can_handle_parameter',
            'tests.contrib.molten.test_molten.hello',
            'molten.renderers.JSONRenderer.render'
        ]

        # Addition of `UploadedFileComponent` in 0.7.2 changes expected spans
        if MOLTEN_VERSION < (0, 7, 2):
            expected = [
                r
                for r in expected
                if not r.startswith('molten.components.UploadedFileComponent')
            ]

        self.assertEqual(len(spans), len(expected))
        self.assertEqual([s.resource for s in spans], expected)

    def test_distributed_tracing(self):
        """ Tests whether span IDs are propogated when distributed tracing is on """
        with override_config('molten', dict(distributed_tracing=True)):
            response = molten_client(headers={
                HTTP_HEADER_TRACE_ID: '100',
                HTTP_HEADER_PARENT_ID: '42',
            })
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), 'Hello 24 year old named Jim!')

        spans = self.tracer.writer.pop()
        span = spans[0]
        self.assertEqual(span.name, 'molten.request')
        self.assertEqual(span.trace_id, 100)
        self.assertEqual(span.parent_id, 42)

        # Now without tracing on
        with override_config('molten', dict(distributed_tracing=False)):
            response = molten_client(headers={
                HTTP_HEADER_TRACE_ID: '100',
                HTTP_HEADER_PARENT_ID: '42',
            })
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), 'Hello 24 year old named Jim!')

        spans = self.tracer.writer.pop()
        span = spans[0]
        self.assertEqual(span.name, 'molten.request')
        self.assertNotEqual(span.trace_id, 100)
        self.assertNotEqual(span.parent_id, 42)

    def test_unpatch_patch(self):
        """ Tests unpatch-patch cycle """
        unpatch()
        self.assertIsNone(Pin.get_from(molten))
        molten_client()
        spans = self.tracer.writer.pop()
        self.assertEqual(len(spans), 0)

        patch()
        # Need to override Pin here as we do in setUp
        Pin.override(molten, tracer=self.tracer)
        self.assertTrue(Pin.get_from(molten) is not None)
        molten_client()
        spans = self.tracer.writer.pop()
        self.assertTrue(len(spans) > 0)

    def test_patch_unpatch(self):
        """ Tests repatch-unpatch cycle """
        # Already call patch in setUp
        self.assertTrue(Pin.get_from(molten) is not None)
        molten_client()
        spans = self.tracer.writer.pop()
        self.assertTrue(len(spans) > 0)

        # Test unpatch
        unpatch()
        self.assertTrue(Pin.get_from(molten) is None)
        molten_client()
        spans = self.tracer.writer.pop()
        self.assertEqual(len(spans), 0)

    def test_patch_idempotence(self):
        """ Tests repatching """
        # Already call patch in setUp but patch again
        patch()
        molten_client()
        spans = self.tracer.writer.pop()
        self.assertTrue(len(spans) > 0)
