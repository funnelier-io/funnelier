"""
Celery Application Setup

Configures the Celery app with Redis broker for background task processing.
Supports ETL pipelines, scheduled analytics, and notification delivery.
"""

from celery import Celery
from celery.schedules import crontab

from src.core.config import settings

# Create Celery application
celery_app = Celery(
    "funnelier",
    broker=settings.celery.broker_url,
    backend=settings.celery.result_backend,
)

# Celery configuration
celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Tehran",
    enable_utc=True,

    # Task execution
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    task_track_started=True,

    # Result expiration (24 hours)
    result_expires=86400,

    # Task routing
    task_routes={
        "src.infrastructure.messaging.tasks.import_*": {"queue": "imports"},
        "src.infrastructure.messaging.tasks.calculate_*": {"queue": "analytics"},
        "src.infrastructure.messaging.tasks.send_*": {"queue": "notifications"},
        "src.infrastructure.messaging.tasks.sync_*": {"queue": "sync"},
        "src.infrastructure.messaging.tasks.poll_*": {"queue": "notifications"},
    },

    # Default queue
    task_default_queue="default",

    # Retry policy
    task_default_retry_delay=60,
    task_max_retries=3,

    # Beat schedule for periodic tasks
    beat_schedule={
        # Daily funnel snapshot at 1:00 AM Tehran time
        "daily-funnel-snapshot": {
            "task": "src.infrastructure.messaging.tasks.calculate_daily_funnel_snapshot",
            "schedule": crontab(hour=1, minute=0),
            "args": [],
        },
        # Daily RFM recalculation at 2:00 AM
        "daily-rfm-calculation": {
            "task": "src.infrastructure.messaging.tasks.calculate_rfm_segments",
            "schedule": crontab(hour=2, minute=0),
            "args": [],
        },
        # Hourly alert check
        "hourly-alert-check": {
            "task": "src.infrastructure.messaging.tasks.check_alerts",
            "schedule": crontab(minute=0),
            "args": [],
        },
        # Daily report generation at 6:00 AM
        "daily-report": {
            "task": "src.infrastructure.messaging.tasks.generate_daily_report",
            "schedule": crontab(hour=6, minute=0),
            "args": [],
        },
        # Poll SMS delivery status every 10 minutes (fallback for webhooks)
        "poll-sms-delivery": {
            "task": "src.infrastructure.messaging.tasks.poll_sms_delivery_status",
            "schedule": crontab(minute="*/10"),
            "args": [],
        },
        # Scheduled ERP data-source sync every 15 minutes
        "erp-data-source-sync": {
            "task": "src.infrastructure.messaging.tasks.sync_erp_data_sources",
            "schedule": crontab(minute="*/15"),
            "args": [],
        },
    },
)

# Auto-discover tasks
celery_app.autodiscover_tasks(["src.infrastructure.messaging"])

