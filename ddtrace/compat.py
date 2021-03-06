import platform
import sys
import textwrap

import six

__all__ = [
    'httplib',
    'iteritems',
    'PY2',
    'Queue',
    'stringify',
    'StringIO',
    'urlencode',
    'parse',
    'reraise',
]

PYTHON_VERSION_INFO = sys.version_info
PY2 = sys.version_info[0] == 2

# Infos about python passed to the trace agent through the header
PYTHON_VERSION = platform.python_version()
PYTHON_INTERPRETER = platform.python_implementation()

try:
    StringIO = six.moves.cStringIO
except ImportError:
    StringIO = six.StringIO

httplib = six.moves.http_client
urlencode = six.moves.urllib.parse.urlencode
parse = six.moves.urllib.parse
Queue = six.moves.queue.Queue
iteritems = six.iteritems
reraise = six.reraise

stringify = six.text_type
string_type = six.string_types[0]
msgpack_type = six.binary_type
# DEV: `six` doesn't have `float` in `integer_types`
numeric_types = six.integer_types + (float, )


if PYTHON_VERSION_INFO[0:2] >= (3, 4):
    from asyncio import iscoroutinefunction

    # Execute from a string to get around syntax errors from `yield from`
    # DEV: The idea to do this was stolen from `six`
    #   https://github.com/benjaminp/six/blob/15e31431af97e5e64b80af0a3f598d382bcdd49a/six.py#L719-L737
    six.exec_(textwrap.dedent("""
    import functools
    import asyncio


    def make_async_decorator(tracer, coro, *params, **kw_params):
        \"\"\"
        Decorator factory that creates an asynchronous wrapper that yields
        a coroutine result. This factory is required to handle Python 2
        compatibilities.

        :param object tracer: the tracer instance that is used
        :param function f: the coroutine that must be executed
        :param tuple params: arguments given to the Tracer.trace()
        :param dict kw_params: keyword arguments given to the Tracer.trace()
        \"\"\"
        @functools.wraps(coro)
        @asyncio.coroutine
        def func_wrapper(*args, **kwargs):
            with tracer.trace(*params, **kw_params):
                result = yield from coro(*args, **kwargs)  # noqa: E999
                return result

        return func_wrapper
    """))

else:
    # asyncio is missing so we can't have coroutines; these
    # functions are used only to ensure code executions in case
    # of an unexpected behavior
    def iscoroutinefunction(fn):
        return False

    def make_async_decorator(tracer, fn, *params, **kw_params):
        return fn


# DEV: There is `six.u()` which does something similar, but doesn't have the guard around `hasattr(s, 'decode')`
def to_unicode(s):
    """ Return a unicode string for the given bytes or string instance. """
    # No reason to decode if we already have the unicode compatible object we expect
    # DEV: `six.text_type` will be a `str` for python 3 and `unicode` for python 2
    # DEV: Double decoding a `unicode` can cause a `UnicodeEncodeError`
    #   e.g. `'\xc3\xbf'.decode('utf-8').decode('utf-8')`
    if isinstance(s, six.text_type):
        return s

    # If the object has a `decode` method, then decode into `utf-8`
    #   e.g. Python 2 `str`, Python 2/3 `bytearray`, etc
    if hasattr(s, 'decode'):
        return s.decode('utf-8')

    # Always try to coerce the object into the `six.text_type` object we expect
    #   e.g. `to_unicode(1)`, `to_unicode(dict(key='value'))`
    return six.text_type(s)


def get_connection_response(conn):
    """Returns the response for a connection.

    If using Python 2 enable buffering.

    Python 2 does not enable buffering by default resulting in many recv
    syscalls.

    See:
    https://bugs.python.org/issue4879
    https://github.com/python/cpython/commit/3c43fcba8b67ea0cec4a443c755ce5f25990a6cf
    """
    if PY2:
        return conn.getresponse(buffering=True)
    else:
        return conn.getresponse()
