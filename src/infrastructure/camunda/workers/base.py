"""
Base External Task Worker

Provides a polling loop that fetches external tasks from Camunda,
dispatches them to registered handlers, and reports completion/failure.
Designed to run as a standalone asyncio process alongside the FastAPI app.
"""

import asyncio
import logging
from typing import Any, Callable, Awaitable

from src.infrastructure.camunda.client import (
    CamundaClient,
    CamundaConnectionError,
    CamundaError,
    ExternalTask,
)
from src.infrastructure.camunda.config import CamundaSettings

logger = logging.getLogger(__name__)

# Type for external task handler functions
TaskHandler = Callable[[ExternalTask, CamundaClient], Awaitable[dict[str, Any] | None]]


class ExternalTaskWorkerRunner:
    """
    Async external task worker that polls Camunda for work.

    Usage:
        runner = ExternalTaskWorkerRunner(client)
        runner.register("send-campaign-sms", handle_send_sms)
        runner.register("check-delivery", handle_check_delivery)
        await runner.run()  # Blocking poll loop
    """

    def __init__(
        self,
        client: CamundaClient | None = None,
        settings: CamundaSettings | None = None,
        poll_interval: float = 5.0,
    ):
        self._settings = settings or CamundaSettings()
        self._client = client or CamundaClient(self._settings)
        self._handlers: dict[str, TaskHandler] = {}
        self._poll_interval = poll_interval
        self._running = False

    def register(self, topic: str, handler: TaskHandler) -> None:
        """Register a handler for an external task topic."""
        self._handlers[topic] = handler
        logger.info("Registered external task handler: topic=%s", topic)

    async def run(self) -> None:
        """Start the polling loop. Runs until stopped."""
        if not self._settings.enabled:
            logger.info("Camunda disabled — external task worker not starting")
            return

        if not self._handlers:
            logger.warning("No external task handlers registered — nothing to poll")
            return

        self._running = True
        logger.info(
            "External task worker starting (topics=%s, poll_interval=%.1fs)",
            list(self._handlers.keys()),
            self._poll_interval,
        )

        while self._running:
            try:
                for topic, handler in self._handlers.items():
                    await self._poll_topic(topic, handler)
            except CamundaConnectionError:
                logger.warning(
                    "Camunda not reachable — retrying in %.0fs", self._poll_interval * 2
                )
                await asyncio.sleep(self._poll_interval * 2)
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Worker poll error: %s", e, exc_info=True)

            await asyncio.sleep(self._poll_interval)

        logger.info("External task worker stopped")

    def stop(self) -> None:
        """Signal the worker to stop polling."""
        self._running = False

    async def _poll_topic(self, topic: str, handler: TaskHandler) -> None:
        """Poll and process tasks for a single topic."""
        tasks = await self._client.fetch_and_lock(
            topic=topic,
            max_tasks=self._settings.worker_max_tasks,
            lock_duration_ms=self._settings.worker_lock_duration_ms,
        )

        for task in tasks:
            try:
                logger.info(
                    "Processing external task: topic=%s, id=%s, business_key=%s",
                    topic, task.id, task.business_key,
                )
                result_vars = await handler(task, self._client)

                # Complete the task with output variables
                await self._client.complete_external_task(
                    task_id=task.id,
                    variables=result_vars,
                )
                logger.info("Completed external task: %s", task.id)

            except CamundaError as e:
                logger.error(
                    "BPMN error in task %s: %s", task.id, e,
                )
                # Report as BPMN error (triggers error boundary event in BPMN)
                try:
                    await self._client.bpmn_error_external_task(
                        task_id=task.id,
                        error_code="HANDLER_ERROR",
                        error_message=str(e),
                    )
                except Exception:
                    pass

            except Exception as e:
                logger.error(
                    "Failed external task %s: %s", task.id, e, exc_info=True,
                )
                # Report failure (Camunda will retry based on retries count)
                retries = (task.retries or self._settings.task_max_retries) - 1
                try:
                    await self._client.fail_external_task(
                        task_id=task.id,
                        error_message=str(e)[:500],
                        error_details=f"topic={topic}, activity={task.activity_id}",
                        retries=max(retries, 0),
                        retry_timeout_ms=self._settings.task_retry_timeout_ms,
                    )
                except Exception as fail_err:
                    logger.error("Could not report task failure: %s", fail_err)

