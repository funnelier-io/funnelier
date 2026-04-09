"""
Camunda BPMS Configuration

Settings for connecting to the Camunda 7 Platform REST API.
Controlled via environment variables with CAMUNDA_ prefix.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class CamundaSettings(BaseSettings):
    """Camunda 7 Platform connection settings."""

    model_config = SettingsConfigDict(env_prefix="CAMUNDA_", env_file=".env", extra="ignore")

    # REST API base URL (Camunda container internal port is 8080, mapped to 8085 externally)
    base_url: str = "http://localhost:8085/engine-rest"

    # Engine name (default engine in Camunda 7)
    engine_name: str = "default"

    # Enable/disable Camunda integration (graceful fallback when container not running)
    enabled: bool = False

    # Connection timeouts (seconds)
    connect_timeout: float = 5.0
    read_timeout: float = 30.0

    # External task worker configuration
    worker_id: str = "funnelier-worker"
    worker_max_tasks: int = 10
    worker_lock_duration_ms: int = 30_000  # 30 seconds
    worker_long_polling_timeout_ms: int = 20_000  # 20 seconds

    # Retry policy for failed external tasks
    task_max_retries: int = 3
    task_retry_timeout_ms: int = 10_000  # 10 seconds

    # BPMN deployment settings
    auto_deploy: bool = True  # Auto-deploy BPMN files on startup

    @property
    def engine_url(self) -> str:
        """Full engine-scoped REST API base URL."""
        return f"{self.base_url}"

    @property
    def process_definition_url(self) -> str:
        return f"{self.engine_url}/process-definition"

    @property
    def process_instance_url(self) -> str:
        return f"{self.engine_url}/process-instance"

    @property
    def deployment_url(self) -> str:
        return f"{self.engine_url}/deployment"

    @property
    def external_task_url(self) -> str:
        return f"{self.engine_url}/external-task"

    @property
    def message_url(self) -> str:
        return f"{self.engine_url}/message"

    @property
    def task_url(self) -> str:
        return f"{self.engine_url}/task"

