"""
Camunda BPMS Infrastructure Module

REST API client, external task workers, and BPMN deployment
for Camunda 7 Platform integration.
"""

from .client import CamundaClient
from .config import CamundaSettings

__all__ = ["CamundaClient", "CamundaSettings"]

