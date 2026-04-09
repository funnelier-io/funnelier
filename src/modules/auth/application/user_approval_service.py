"""
User Approval Workflow Service

Application service that orchestrates user approval through Camunda BPMS
when enabled, with graceful fallback to direct operations when disabled.
"""

import logging
from typing import Any
from uuid import UUID

from src.infrastructure.camunda.client import (
    CamundaClient,
    CamundaConnectionError,
    CamundaError,
)

logger = logging.getLogger(__name__)


class UserApprovalWorkflowService:
    """
    Manages user registration approval via Camunda BPMS with fallback.

    When Camunda is enabled:
      - register: starts user_approval process
      - approve: completes the admin_review user task with approved=true
      - reject: completes the admin_review user task with approved=false

    When Camunda is disabled:
      - Falls back to direct DB operations (existing behaviour)
    """

    def __init__(self, camunda_client: CamundaClient):
        self._camunda = camunda_client

    async def on_user_registered(
        self,
        user_id: UUID,
        tenant_id: UUID,
        username: str,
        email: str,
    ) -> str | None:
        """
        Start the user_approval Camunda process after registration.

        Returns the process_instance_id if Camunda is used, else None.
        """
        if not self._camunda.enabled:
            return None

        try:
            instance = await self._camunda.start_process(
                process_key="user_approval",
                business_key=str(user_id),
                variables={
                    "user_id": str(user_id),
                    "tenant_id": str(tenant_id),
                    "username": username,
                    "email": email,
                },
                tenant_id=str(tenant_id),
            )
            logger.info(
                "User approval process started for %s (process=%s)",
                username, instance.id,
            )
            return instance.id
        except (CamundaConnectionError, CamundaError) as e:
            logger.warning(
                "Camunda unavailable for user approval %s — skipping: %s",
                username, e,
            )
            return None

    async def on_user_approved(
        self,
        user_id: UUID,
        tenant_id: UUID,
        approval_process_id: str | None = None,
    ) -> bool:
        """
        Complete the approval human task in Camunda.

        Returns True if Camunda task was completed, False otherwise.
        """
        if not self._camunda.enabled or not approval_process_id:
            return False

        try:
            # Find the admin_review task for this process instance
            tasks = await self._camunda.list_tasks(
                process_instance_id=approval_process_id,
            )
            for task in tasks:
                if task.task_definition_key == "admin_review":
                    await self._camunda.complete_task(
                        task_id=task.id,
                        variables={"approved": True},
                    )
                    logger.info(
                        "Completed approval task %s for user %s",
                        task.id, user_id,
                    )
                    return True

            logger.warning(
                "No admin_review task found for process %s", approval_process_id,
            )
            return False
        except (CamundaConnectionError, CamundaError) as e:
            logger.warning(
                "Camunda approve failed for user %s: %s", user_id, e,
            )
            return False

    async def on_user_rejected(
        self,
        user_id: UUID,
        tenant_id: UUID,
        approval_process_id: str | None = None,
        reason: str = "",
    ) -> bool:
        """
        Complete the rejection human task in Camunda.

        Returns True if Camunda task was completed, False otherwise.
        """
        if not self._camunda.enabled or not approval_process_id:
            return False

        try:
            tasks = await self._camunda.list_tasks(
                process_instance_id=approval_process_id,
            )
            for task in tasks:
                if task.task_definition_key == "admin_review":
                    await self._camunda.complete_task(
                        task_id=task.id,
                        variables={
                            "approved": False,
                            "rejection_reason": reason,
                        },
                    )
                    logger.info(
                        "Completed rejection task %s for user %s",
                        task.id, user_id,
                    )
                    return True

            logger.warning(
                "No admin_review task found for process %s", approval_process_id,
            )
            return False
        except (CamundaConnectionError, CamundaError) as e:
            logger.warning(
                "Camunda reject failed for user %s: %s", user_id, e,
            )
            return False

