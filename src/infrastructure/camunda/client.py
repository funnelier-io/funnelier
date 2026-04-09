"""
Camunda REST API Client

Async HTTP client for Camunda 7 Platform REST API.
Provides methods for process management, message correlation,
external task handling, and deployment operations.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx

from .config import CamundaSettings

logger = logging.getLogger(__name__)


class CamundaError(Exception):
    """Base exception for Camunda client errors."""

    def __init__(self, message: str, status_code: int | None = None, detail: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail


class CamundaConnectionError(CamundaError):
    """Raised when Camunda engine is unreachable."""
    pass


class CamundaProcessNotFoundError(CamundaError):
    """Raised when a process definition or instance is not found."""
    pass


# ─── Data classes for Camunda responses ──────────────────────────────────────


class ProcessInstance:
    """Represents a running BPMN process instance."""

    def __init__(self, data: dict[str, Any]):
        self.id: str = data.get("id", "")
        self.definition_id: str = data.get("definitionId", "")
        self.business_key: str | None = data.get("businessKey")
        self.tenant_id: str | None = data.get("tenantId")
        self.ended: bool = data.get("ended", False)
        self.suspended: bool = data.get("suspended", False)
        self._raw = data

    def __repr__(self) -> str:
        return f"ProcessInstance(id={self.id!r}, business_key={self.business_key!r})"


class ProcessDefinition:
    """Represents a deployed BPMN process definition."""

    def __init__(self, data: dict[str, Any]):
        self.id: str = data.get("id", "")
        self.key: str = data.get("key", "")
        self.name: str | None = data.get("name")
        self.version: int = data.get("version", 0)
        self.deployment_id: str | None = data.get("deploymentId")
        self.tenant_id: str | None = data.get("tenantId")
        self.suspended: bool = data.get("suspended", False)
        self._raw = data

    def __repr__(self) -> str:
        return f"ProcessDefinition(key={self.key!r}, version={self.version})"


class Deployment:
    """Represents a Camunda deployment."""

    def __init__(self, data: dict[str, Any]):
        self.id: str = data.get("id", "")
        self.name: str | None = data.get("name")
        self.deployment_time: str | None = data.get("deploymentTime")
        self.source: str | None = data.get("source")
        self._raw = data

    def __repr__(self) -> str:
        return f"Deployment(id={self.id!r}, name={self.name!r})"


class ExternalTask:
    """Represents an external task fetched from Camunda."""

    def __init__(self, data: dict[str, Any]):
        self.id: str = data.get("id", "")
        self.worker_id: str | None = data.get("workerId")
        self.topic_name: str = data.get("topicName", "")
        self.process_instance_id: str = data.get("processInstanceId", "")
        self.process_definition_key: str = data.get("processDefinitionKey", "")
        self.activity_id: str = data.get("activityId", "")
        self.business_key: str | None = data.get("businessKey")
        self.tenant_id: str | None = data.get("tenantId")
        self.retries: int | None = data.get("retries")
        self.priority: int = data.get("priority", 0)
        self.variables: dict[str, Any] = data.get("variables", {})
        self._raw = data

    def get_variable(self, name: str) -> Any:
        """Get a process variable value by name."""
        var = self.variables.get(name, {})
        return var.get("value") if isinstance(var, dict) else var

    def __repr__(self) -> str:
        return f"ExternalTask(id={self.id!r}, topic={self.topic_name!r})"


class HumanTask:
    """Represents a human/user task in Camunda."""

    def __init__(self, data: dict[str, Any]):
        self.id: str = data.get("id", "")
        self.name: str | None = data.get("name")
        self.assignee: str | None = data.get("assignee")
        self.process_instance_id: str = data.get("processInstanceId", "")
        self.process_definition_key: str = data.get("processDefinitionKey", "")
        self.task_definition_key: str = data.get("taskDefinitionKey", "")
        self.created: str | None = data.get("created")
        self.due: str | None = data.get("due")
        self.tenant_id: str | None = data.get("tenantId")
        self._raw = data

    def __repr__(self) -> str:
        return f"HumanTask(id={self.id!r}, name={self.name!r})"


# ─── Main Client ─────────────────────────────────────────────────────────────


class CamundaClient:
    """
    Async REST API client for Camunda 7 Platform.

    Usage:
        client = CamundaClient(settings)
        # Start a process
        instance = await client.start_process("campaign_lifecycle", business_key="abc")
        # Correlate a message
        await client.correlate_message("sms_delivered", business_key="abc")
    """

    def __init__(self, settings: CamundaSettings | None = None):
        if settings is None:
            settings = CamundaSettings()
        self._settings = settings
        self._http: httpx.AsyncClient | None = None

    @property
    def settings(self) -> CamundaSettings:
        return self._settings

    @property
    def enabled(self) -> bool:
        return self._settings.enabled

    async def _get_http(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                base_url=self._settings.engine_url,
                timeout=httpx.Timeout(
                    connect=self._settings.connect_timeout,
                    read=self._settings.read_timeout,
                    write=self._settings.read_timeout,
                    pool=self._settings.connect_timeout,
                ),
                headers={"Content-Type": "application/json"},
            )
        return self._http

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._http and not self._http.is_closed:
            await self._http.aclose()
            self._http = None

    async def _request(
        self,
        method: str,
        path: str,
        json: Any = None,
        params: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """Make an HTTP request to Camunda REST API."""
        if not self._settings.enabled:
            raise CamundaError("Camunda integration is disabled (CAMUNDA_ENABLED=false)")

        try:
            http = await self._get_http()
            kwargs: dict[str, Any] = {"params": params}

            if files:
                kwargs["files"] = files
                kwargs["headers"] = {}  # Let httpx set multipart boundary
            else:
                kwargs["json"] = json
                if headers:
                    kwargs["headers"] = headers

            response = await http.request(method, path, **kwargs)

            if response.status_code == 404:
                raise CamundaProcessNotFoundError(
                    f"Not found: {path}",
                    status_code=404,
                    detail=response.text,
                )

            if response.status_code >= 400:
                detail = response.text
                try:
                    detail = response.json()
                except Exception:
                    pass
                raise CamundaError(
                    f"Camunda API error ({response.status_code}): {path}",
                    status_code=response.status_code,
                    detail=detail,
                )

            if response.status_code == 204:
                return None

            if response.headers.get("content-type", "").startswith("application/json"):
                return response.json()

            return response.text

        except httpx.ConnectError as e:
            raise CamundaConnectionError(
                f"Cannot connect to Camunda at {self._settings.base_url}: {e}"
            ) from e
        except httpx.TimeoutException as e:
            raise CamundaConnectionError(
                f"Timeout connecting to Camunda: {e}"
            ) from e
        except CamundaError:
            raise
        except Exception as e:
            raise CamundaError(f"Unexpected Camunda client error: {e}") from e

    # ─── Engine Health ────────────────────────────────────────────────────────

    async def check_health(self) -> bool:
        """Check if Camunda engine is reachable and healthy."""
        try:
            result = await self._request("GET", "/engine")
            return isinstance(result, list) and len(result) > 0
        except CamundaError:
            return False

    async def get_engine_info(self) -> dict[str, Any]:
        """Get Camunda engine version and info."""
        return await self._request("GET", "/version")

    # ─── Process Definitions ──────────────────────────────────────────────────

    async def list_process_definitions(
        self,
        key: str | None = None,
        latest_version: bool = True,
    ) -> list[ProcessDefinition]:
        """List deployed process definitions."""
        params: dict[str, Any] = {}
        if key:
            params["key"] = key
        if latest_version:
            params["latestVersion"] = "true"

        data = await self._request("GET", "/process-definition", params=params)
        return [ProcessDefinition(d) for d in data]

    async def get_process_definition(self, key: str) -> ProcessDefinition:
        """Get the latest version of a process definition by key."""
        data = await self._request("GET", f"/process-definition/key/{key}")
        return ProcessDefinition(data)

    # ─── Process Instances ────────────────────────────────────────────────────

    async def start_process(
        self,
        process_key: str,
        business_key: str | None = None,
        variables: dict[str, Any] | None = None,
        tenant_id: str | None = None,
    ) -> ProcessInstance:
        """
        Start a new process instance.

        Args:
            process_key: BPMN process definition key
            business_key: Business key for correlation (e.g., campaign_id)
            variables: Process variables (auto-wrapped in Camunda format)
            tenant_id: Tenant ID as process variable for multi-tenant isolation
        """
        payload: dict[str, Any] = {}
        if business_key:
            payload["businessKey"] = business_key

        # Build variables in Camunda format: {"name": {"value": x, "type": "String"}}
        camunda_vars: dict[str, Any] = {}
        if variables:
            for k, v in variables.items():
                camunda_vars[k] = _to_camunda_variable(v)

        # Always inject tenant_id if provided
        if tenant_id and "tenant_id" not in camunda_vars:
            camunda_vars["tenant_id"] = {"value": tenant_id, "type": "String"}

        if camunda_vars:
            payload["variables"] = camunda_vars

        data = await self._request(
            "POST",
            f"/process-definition/key/{process_key}/start",
            json=payload,
        )
        logger.info(
            "Started process %s (business_key=%s, instance=%s)",
            process_key, business_key, data.get("id"),
        )
        return ProcessInstance(data)

    async def get_process_instance(self, instance_id: str) -> ProcessInstance:
        """Get a process instance by ID."""
        data = await self._request("GET", f"/process-instance/{instance_id}")
        return ProcessInstance(data)

    async def list_process_instances(
        self,
        process_key: str | None = None,
        business_key: str | None = None,
        tenant_variable: str | None = None,
        active: bool | None = None,
    ) -> list[ProcessInstance]:
        """List process instances with optional filters."""
        payload: dict[str, Any] = {}
        if process_key:
            payload["processDefinitionKey"] = process_key
        if business_key:
            payload["businessKey"] = business_key
        if active is not None:
            payload["active"] = active

        # Filter by tenant_id variable
        if tenant_variable:
            payload["variables"] = [
                {"name": "tenant_id", "value": tenant_variable, "operator": "eq"}
            ]

        data = await self._request("POST", "/process-instance", json=payload)
        return [ProcessInstance(d) for d in data]

    async def delete_process_instance(
        self,
        instance_id: str,
        reason: str = "Cancelled by user",
    ) -> None:
        """Delete (cancel) a process instance."""
        await self._request(
            "DELETE",
            f"/process-instance/{instance_id}",
            params={"skipCustomListeners": "true", "skipIoMappings": "true"},
        )
        logger.info("Deleted process instance %s: %s", instance_id, reason)

    async def suspend_process_instance(self, instance_id: str) -> None:
        """Suspend (pause) a process instance."""
        await self._request(
            "PUT",
            f"/process-instance/{instance_id}/suspended",
            json={"suspended": True},
        )
        logger.info("Suspended process instance %s", instance_id)

    async def activate_process_instance(self, instance_id: str) -> None:
        """Activate (resume) a suspended process instance."""
        await self._request(
            "PUT",
            f"/process-instance/{instance_id}/suspended",
            json={"suspended": False},
        )
        logger.info("Activated process instance %s", instance_id)

    async def get_process_variables(
        self, instance_id: str
    ) -> dict[str, Any]:
        """Get all variables of a process instance."""
        data = await self._request(
            "GET", f"/process-instance/{instance_id}/variables"
        )
        return {k: v.get("value") for k, v in data.items()}

    async def set_process_variable(
        self,
        instance_id: str,
        name: str,
        value: Any,
    ) -> None:
        """Set a variable on a process instance."""
        await self._request(
            "PUT",
            f"/process-instance/{instance_id}/variables/{name}",
            json=_to_camunda_variable(value),
        )

    # ─── Message Correlation ──────────────────────────────────────────────────

    async def correlate_message(
        self,
        message_name: str,
        business_key: str | None = None,
        process_instance_id: str | None = None,
        variables: dict[str, Any] | None = None,
        tenant_id: str | None = None,
        all_instances: bool = False,
    ) -> Any:
        """
        Correlate a BPMN message event.

        This is the primary mechanism for advancing process instances when
        external events occur (e.g., SMS delivered, call answered, payment received).

        Args:
            message_name: BPMN message name (e.g., "sms_delivered")
            business_key: Business key to correlate to (e.g., contact phone number)
            process_instance_id: Specific process instance to target
            variables: Variables to set on the process instance
            tenant_id: Tenant ID for filtering (added as correlation variable)
            all_instances: If True, correlate to all matching instances
        """
        payload: dict[str, Any] = {"messageName": message_name}

        if business_key:
            payload["businessKey"] = business_key
        if process_instance_id:
            payload["processInstanceId"] = process_instance_id

        # Correlation keys (used to find the right process instance)
        correlation_keys: dict[str, Any] = {}
        if tenant_id:
            correlation_keys["tenant_id"] = {"value": tenant_id, "type": "String"}
        if correlation_keys:
            payload["correlationKeys"] = correlation_keys

        # Process variables to set
        if variables:
            payload["processVariables"] = {
                k: _to_camunda_variable(v) for k, v in variables.items()
            }

        if all_instances:
            payload["all"] = True

        endpoint = "/message" if not all_instances else "/message"
        result = await self._request("POST", endpoint, json=payload)

        logger.info(
            "Correlated message %s (business_key=%s)",
            message_name, business_key,
        )
        return result

    # ─── External Tasks ───────────────────────────────────────────────────────

    async def fetch_and_lock(
        self,
        topic: str,
        max_tasks: int | None = None,
        lock_duration_ms: int | None = None,
        variables: list[str] | None = None,
    ) -> list[ExternalTask]:
        """
        Fetch and lock external tasks for a specific topic.

        Args:
            topic: External task topic name
            max_tasks: Maximum tasks to fetch (default from settings)
            lock_duration_ms: Lock duration in ms (default from settings)
            variables: Specific variable names to include
        """
        payload: dict[str, Any] = {
            "workerId": self._settings.worker_id,
            "maxTasks": max_tasks or self._settings.worker_max_tasks,
            "topics": [
                {
                    "topicName": topic,
                    "lockDuration": lock_duration_ms or self._settings.worker_lock_duration_ms,
                }
            ],
        }

        if variables:
            payload["topics"][0]["variables"] = variables

        data = await self._request("POST", "/external-task/fetchAndLock", json=payload)
        return [ExternalTask(d) for d in data]

    async def complete_external_task(
        self,
        task_id: str,
        variables: dict[str, Any] | None = None,
    ) -> None:
        """Mark an external task as completed with optional output variables."""
        payload: dict[str, Any] = {
            "workerId": self._settings.worker_id,
        }
        if variables:
            payload["variables"] = {
                k: _to_camunda_variable(v) for k, v in variables.items()
            }

        await self._request("POST", f"/external-task/{task_id}/complete", json=payload)

    async def fail_external_task(
        self,
        task_id: str,
        error_message: str,
        error_details: str = "",
        retries: int | None = None,
        retry_timeout_ms: int | None = None,
    ) -> None:
        """Report an external task failure (will retry if retries > 0)."""
        payload: dict[str, Any] = {
            "workerId": self._settings.worker_id,
            "errorMessage": error_message[:500],
            "errorDetails": error_details[:4000],
            "retries": retries if retries is not None else self._settings.task_max_retries,
            "retryTimeout": retry_timeout_ms or self._settings.task_retry_timeout_ms,
        }
        await self._request("POST", f"/external-task/{task_id}/failure", json=payload)

    async def bpmn_error_external_task(
        self,
        task_id: str,
        error_code: str,
        error_message: str = "",
        variables: dict[str, Any] | None = None,
    ) -> None:
        """Throw a BPMN error from an external task (triggers error boundary event)."""
        payload: dict[str, Any] = {
            "workerId": self._settings.worker_id,
            "errorCode": error_code,
            "errorMessage": error_message,
        }
        if variables:
            payload["variables"] = {
                k: _to_camunda_variable(v) for k, v in variables.items()
            }
        await self._request("POST", f"/external-task/{task_id}/bpmnError", json=payload)

    # ─── Human/User Tasks ─────────────────────────────────────────────────────

    async def list_tasks(
        self,
        process_instance_id: str | None = None,
        assignee: str | None = None,
        candidate_group: str | None = None,
        process_definition_key: str | None = None,
    ) -> list[HumanTask]:
        """List human tasks with optional filters."""
        params: dict[str, Any] = {}
        if process_instance_id:
            params["processInstanceId"] = process_instance_id
        if assignee:
            params["assignee"] = assignee
        if candidate_group:
            params["candidateGroup"] = candidate_group
        if process_definition_key:
            params["processDefinitionKey"] = process_definition_key

        data = await self._request("GET", "/task", params=params)
        return [HumanTask(d) for d in data]

    async def complete_task(
        self,
        task_id: str,
        variables: dict[str, Any] | None = None,
    ) -> None:
        """Complete a human task with optional variables."""
        payload: dict[str, Any] = {}
        if variables:
            payload["variables"] = {
                k: _to_camunda_variable(v) for k, v in variables.items()
            }
        await self._request("POST", f"/task/{task_id}/complete", json=payload)

    async def claim_task(self, task_id: str, user_id: str) -> None:
        """Assign a task to a specific user."""
        await self._request(
            "POST", f"/task/{task_id}/claim", json={"userId": user_id}
        )

    # ─── Deployment ───────────────────────────────────────────────────────────

    async def deploy_bpmn(
        self,
        name: str,
        bpmn_xml: str | bytes,
        filename: str = "process.bpmn",
        enable_duplicate_filtering: bool = True,
        tenant_id: str | None = None,
    ) -> Deployment:
        """
        Deploy a BPMN process definition to Camunda.

        Args:
            name: Deployment name
            bpmn_xml: BPMN XML content (str or bytes)
            filename: BPMN filename
            enable_duplicate_filtering: Skip if identical BPMN already deployed
            tenant_id: Optional Camunda tenant for deployment scoping
        """
        if isinstance(bpmn_xml, str):
            bpmn_xml = bpmn_xml.encode("utf-8")

        files: dict[str, Any] = {
            "deployment-name": (None, name),
            "enable-duplicate-filtering": (None, str(enable_duplicate_filtering).lower()),
            "deploy-changed-only": (None, "true"),
            filename: (filename, bpmn_xml, "application/octet-stream"),
        }

        if tenant_id:
            files["tenant-id"] = (None, tenant_id)

        data = await self._request("POST", "/deployment/create", files=files)
        deployment = Deployment(data)
        logger.info("Deployed BPMN: %s (deployment_id=%s)", name, deployment.id)
        return deployment

    async def deploy_bpmn_file(
        self,
        filepath: str | Path,
        name: str | None = None,
        tenant_id: str | None = None,
    ) -> Deployment:
        """Deploy a BPMN file from disk."""
        path = Path(filepath)
        if not path.exists():
            raise CamundaError(f"BPMN file not found: {path}")

        bpmn_xml = path.read_bytes()
        deployment_name = name or path.stem
        return await self.deploy_bpmn(
            name=deployment_name,
            bpmn_xml=bpmn_xml,
            filename=path.name,
            tenant_id=tenant_id,
        )

    async def list_deployments(self) -> list[Deployment]:
        """List all deployments."""
        data = await self._request("GET", "/deployment")
        return [Deployment(d) for d in data]

    # ─── History (for audit/monitoring) ───────────────────────────────────────

    async def get_process_instance_history(
        self,
        instance_id: str | None = None,
        business_key: str | None = None,
        process_key: str | None = None,
        finished: bool | None = None,
    ) -> list[dict[str, Any]]:
        """Query historic process instances."""
        payload: dict[str, Any] = {}
        if instance_id:
            payload["processInstanceId"] = instance_id
        if business_key:
            payload["processInstanceBusinessKey"] = business_key
        if process_key:
            payload["processDefinitionKey"] = process_key
        if finished is not None:
            payload["finished"] = finished

        return await self._request("POST", "/history/process-instance", json=payload)

    async def get_activity_instance_history(
        self,
        process_instance_id: str,
    ) -> list[dict[str, Any]]:
        """Get activity (node) history for a process instance."""
        return await self._request(
            "GET",
            "/history/activity-instance",
            params={"processInstanceId": process_instance_id, "sortBy": "startTime", "sortOrder": "asc"},
        )


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _to_camunda_variable(value: Any) -> dict[str, Any]:
    """Convert a Python value to Camunda variable format."""
    if isinstance(value, dict) and "value" in value and "type" in value:
        # Already in Camunda format
        return value

    if isinstance(value, bool):
        return {"value": value, "type": "Boolean"}
    elif isinstance(value, int):
        return {"value": value, "type": "Long"}
    elif isinstance(value, float):
        return {"value": value, "type": "Double"}
    elif isinstance(value, str):
        return {"value": value, "type": "String"}
    elif isinstance(value, UUID):
        return {"value": str(value), "type": "String"}
    elif isinstance(value, datetime):
        return {"value": value.isoformat(), "type": "String"}
    elif isinstance(value, (list, dict)):
        import json
        return {"value": json.dumps(value, default=str), "type": "Json"}
    elif value is None:
        return {"value": None, "type": "Null"}
    else:
        return {"value": str(value), "type": "String"}


# ─── Singleton ───────────────────────────────────────────────────────────────

_client: CamundaClient | None = None


def get_camunda_client() -> CamundaClient:
    """Get the singleton Camunda client instance."""
    global _client
    if _client is None:
        _client = CamundaClient()
    return _client


async def close_camunda_client() -> None:
    """Close the singleton Camunda client."""
    global _client
    if _client:
        await _client.close()
        _client = None

