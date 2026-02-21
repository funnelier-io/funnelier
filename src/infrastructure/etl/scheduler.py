"""
ETL Scheduler

Provides scheduling capabilities for ETL pipelines using
cron expressions and interval-based scheduling.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Coroutine

from croniter import croniter

from .pipeline import ETLPipeline, PipelineConfig, PipelineManager, PipelineResult, PipelineStatus


class JobStatus(str, Enum):
    """Scheduled job status."""

    ACTIVE = "active"
    PAUSED = "paused"
    DISABLED = "disabled"
    RUNNING = "running"


@dataclass
class ScheduledJob:
    """Represents a scheduled ETL job."""

    job_id: str
    pipeline_name: str
    schedule: str  # Cron expression
    status: JobStatus = JobStatus.ACTIVE
    last_run: datetime | None = None
    next_run: datetime | None = None
    run_count: int = 0
    error_count: int = 0
    last_error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def calculate_next_run(self) -> datetime:
        """Calculate the next run time based on cron expression."""
        base_time = self.last_run or datetime.utcnow()
        cron = croniter(self.schedule, base_time)
        self.next_run = cron.get_next(datetime)
        return self.next_run

    def is_due(self) -> bool:
        """Check if the job is due to run."""
        if self.status != JobStatus.ACTIVE:
            return False
        if not self.next_run:
            self.calculate_next_run()
        return datetime.utcnow() >= self.next_run

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "job_id": self.job_id,
            "pipeline_name": self.pipeline_name,
            "schedule": self.schedule,
            "status": self.status.value,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "run_count": self.run_count,
            "error_count": self.error_count,
            "last_error": self.last_error,
            "metadata": self.metadata,
        }


class ETLScheduler:
    """
    Scheduler for ETL pipelines.
    Supports cron-based and interval-based scheduling.
    """

    def __init__(
        self,
        pipeline_manager: PipelineManager,
        check_interval_seconds: int = 60,
    ):
        self._pipeline_manager = pipeline_manager
        self._check_interval = check_interval_seconds
        self._jobs: dict[str, ScheduledJob] = {}
        self._running = False
        self._task: asyncio.Task | None = None
        self._callbacks: list[Callable[[ScheduledJob, PipelineResult], Coroutine]] = []

    @property
    def is_running(self) -> bool:
        return self._running

    def add_job(
        self,
        job_id: str,
        pipeline_name: str,
        schedule: str,
        metadata: dict[str, Any] | None = None,
    ) -> ScheduledJob:
        """Add a scheduled job."""
        # Validate cron expression
        try:
            croniter(schedule)
        except (KeyError, ValueError) as e:
            raise ValueError(f"Invalid cron expression: {schedule}") from e

        # Validate pipeline exists
        if not self._pipeline_manager.get_pipeline(pipeline_name):
            raise ValueError(f"Pipeline not found: {pipeline_name}")

        job = ScheduledJob(
            job_id=job_id,
            pipeline_name=pipeline_name,
            schedule=schedule,
            metadata=metadata or {},
        )
        job.calculate_next_run()

        self._jobs[job_id] = job
        return job

    def remove_job(self, job_id: str) -> bool:
        """Remove a scheduled job."""
        if job_id in self._jobs:
            del self._jobs[job_id]
            return True
        return False

    def pause_job(self, job_id: str) -> bool:
        """Pause a scheduled job."""
        job = self._jobs.get(job_id)
        if job:
            job.status = JobStatus.PAUSED
            return True
        return False

    def resume_job(self, job_id: str) -> bool:
        """Resume a paused job."""
        job = self._jobs.get(job_id)
        if job and job.status == JobStatus.PAUSED:
            job.status = JobStatus.ACTIVE
            job.calculate_next_run()
            return True
        return False

    def get_job(self, job_id: str) -> ScheduledJob | None:
        """Get a job by ID."""
        return self._jobs.get(job_id)

    def list_jobs(self) -> list[ScheduledJob]:
        """List all scheduled jobs."""
        return list(self._jobs.values())

    def add_callback(
        self,
        callback: Callable[[ScheduledJob, PipelineResult], Coroutine],
    ) -> None:
        """Add a callback to be called after each job execution."""
        self._callbacks.append(callback)

    async def start(self) -> None:
        """Start the scheduler."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._run_scheduler())

    async def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def run_job_now(self, job_id: str) -> PipelineResult | None:
        """Run a job immediately."""
        job = self._jobs.get(job_id)
        if not job:
            return None

        return await self._execute_job(job)

    async def _run_scheduler(self) -> None:
        """Main scheduler loop."""
        while self._running:
            try:
                await self._check_and_run_jobs()
                await asyncio.sleep(self._check_interval)
            except asyncio.CancelledError:
                break
            except Exception:
                # Log error but continue running
                await asyncio.sleep(self._check_interval)

    async def _check_and_run_jobs(self) -> None:
        """Check for due jobs and run them."""
        for job in self._jobs.values():
            if job.is_due():
                # Run in background to not block other jobs
                asyncio.create_task(self._execute_job(job))

    async def _execute_job(self, job: ScheduledJob) -> PipelineResult:
        """Execute a single job."""
        job.status = JobStatus.RUNNING
        job.last_run = datetime.utcnow()

        try:
            result = await self._pipeline_manager.run_pipeline(job.pipeline_name)
            job.run_count += 1

            if result.status == PipelineStatus.FAILED:
                job.error_count += 1
                job.last_error = result.errors[0] if result.errors else "Unknown error"
            else:
                job.last_error = None

        except Exception as e:
            job.error_count += 1
            job.last_error = str(e)
            result = PipelineResult(
                pipeline_name=job.pipeline_name,
                status=PipelineStatus.FAILED,
                started_at=job.last_run,
                completed_at=datetime.utcnow(),
                errors=[str(e)],
            )

        finally:
            job.status = JobStatus.ACTIVE
            job.calculate_next_run()

        # Execute callbacks
        for callback in self._callbacks:
            try:
                await callback(job, result)
            except Exception:
                pass  # Don't let callback errors affect scheduler

        return result


class DailyScheduler:
    """
    Simplified scheduler for daily ETL jobs.
    Runs pipelines at specified times each day.
    """

    def __init__(
        self,
        pipeline_manager: PipelineManager,
    ):
        self._pipeline_manager = pipeline_manager
        self._daily_jobs: dict[str, tuple[int, int]] = {}  # job_id -> (hour, minute)
        self._running = False
        self._task: asyncio.Task | None = None

    def add_daily_job(
        self,
        job_id: str,
        pipeline_name: str,
        hour: int,
        minute: int = 0,
    ) -> None:
        """Add a job to run daily at specified time (UTC)."""
        if not 0 <= hour <= 23:
            raise ValueError("Hour must be between 0 and 23")
        if not 0 <= minute <= 59:
            raise ValueError("Minute must be between 0 and 59")

        if not self._pipeline_manager.get_pipeline(pipeline_name):
            raise ValueError(f"Pipeline not found: {pipeline_name}")

        self._daily_jobs[job_id] = (hour, minute)

    async def start(self) -> None:
        """Start the daily scheduler."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._run_scheduler())

    async def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run_scheduler(self) -> None:
        """Main scheduler loop."""
        last_check_date = None

        while self._running:
            now = datetime.utcnow()
            current_date = now.date()

            # Check if we've moved to a new day
            if last_check_date != current_date:
                last_check_date = current_date

            # Check each job
            for job_id, (hour, minute) in self._daily_jobs.items():
                scheduled_time = datetime(
                    now.year, now.month, now.day, hour, minute
                )

                # If we're within 1 minute of scheduled time and haven't run today
                if abs((now - scheduled_time).total_seconds()) < 60:
                    asyncio.create_task(
                        self._pipeline_manager.run_pipeline(job_id)
                    )

            # Sleep for 30 seconds
            await asyncio.sleep(30)


class BatchScheduler:
    """
    Scheduler for batch processing jobs.
    Useful for processing data in batches at regular intervals.
    """

    def __init__(
        self,
        pipeline_manager: PipelineManager,
        default_interval_minutes: int = 15,
    ):
        self._pipeline_manager = pipeline_manager
        self._default_interval = default_interval_minutes
        self._batch_jobs: dict[str, dict[str, Any]] = {}
        self._running = False
        self._task: asyncio.Task | None = None

    def add_batch_job(
        self,
        job_id: str,
        pipeline_name: str,
        interval_minutes: int | None = None,
    ) -> None:
        """Add a batch processing job."""
        self._batch_jobs[job_id] = {
            "pipeline_name": pipeline_name,
            "interval": interval_minutes or self._default_interval,
            "last_run": None,
        }

    async def start(self) -> None:
        """Start the batch scheduler."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._run_scheduler())

    async def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run_scheduler(self) -> None:
        """Main scheduler loop."""
        while self._running:
            now = datetime.utcnow()

            for job_id, job_config in self._batch_jobs.items():
                last_run = job_config["last_run"]
                interval = timedelta(minutes=job_config["interval"])

                if not last_run or (now - last_run) >= interval:
                    job_config["last_run"] = now
                    asyncio.create_task(
                        self._pipeline_manager.run_pipeline(job_config["pipeline_name"])
                    )

            # Check every minute
            await asyncio.sleep(60)

