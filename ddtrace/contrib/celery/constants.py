from os import getenv

# Celery Context key
CTX_KEY = '__dd_task_span'

# Span names
PRODUCER_ROOT_SPAN = 'celery.apply'
WORKER_ROOT_SPAN = 'celery.run'

# Task operations
TASK_TAG_KEY = 'celery.action'
TASK_APPLY = 'apply'
TASK_APPLY_ASYNC = 'apply_async'
TASK_RUN = 'run'

# Service info
APP = 'celery'
PRODUCER_SERVICE = getenv('DATADOG_SERVICE_NAME') or 'celery-producer'
WORKER_SERVICE = getenv('DATADOG_SERVICE_NAME') or 'celery-worker'