"""
BPMN Deployment Manager

Auto-deploys BPMN process definitions to Camunda on application startup.
Also provides a helper to generate per-tenant funnel BPMN dynamically.
"""

import logging
from pathlib import Path
from typing import Any

from .client import CamundaClient, CamundaConnectionError, Deployment

logger = logging.getLogger(__name__)

# Directory containing BPMN files
BPMN_DIR = Path(__file__).parent / "bpmn"


async def deploy_all_bpmn(client: CamundaClient) -> list[Deployment]:
    """
    Deploy all BPMN files from the bpmn/ directory.

    Camunda's duplicate-filtering ensures unchanged files aren't re-deployed.
    Returns list of successful deployments.
    """
    if not client.enabled:
        logger.info("Camunda disabled — skipping BPMN deployment")
        return []

    if not BPMN_DIR.exists():
        logger.warning("BPMN directory not found: %s", BPMN_DIR)
        return []

    bpmn_files = sorted(BPMN_DIR.glob("*.bpmn"))
    if not bpmn_files:
        logger.info("No BPMN files to deploy in %s", BPMN_DIR)
        return []

    deployments: list[Deployment] = []
    for bpmn_file in bpmn_files:
        try:
            deployment = await client.deploy_bpmn_file(bpmn_file)
            deployments.append(deployment)
            logger.info("Deployed %s → deployment_id=%s", bpmn_file.name, deployment.id)
        except CamundaConnectionError:
            logger.warning("Camunda not reachable — skipping deployment of %s", bpmn_file.name)
            break
        except Exception as e:
            logger.error("Failed to deploy %s: %s", bpmn_file.name, e)

    return deployments


def generate_funnel_bpmn(
    stages: list[dict[str, Any]],
    process_key: str = "funnel_journey",
    process_name: str = "Funnel Journey",
) -> str:
    """
    Generate a BPMN XML for a funnel journey process from stage configuration.

    Each stage becomes a receive-task waiting for a message event.
    This enables per-tenant custom funnel workflows.

    Args:
        stages: List of stage dicts with 'name', 'display_name', 'order' keys
        process_key: BPMN process definition key
        process_name: Human-readable process name

    Returns:
        BPMN 2.0 XML string
    """
    sorted_stages = sorted(stages, key=lambda s: s.get("order", 0))

    # Build BPMN elements
    flow_nodes = []
    sequence_flows = []

    # Start event
    start_id = "start_event"
    flow_nodes.append(
        f'    <bpmn:startEvent id="{start_id}" name="Lead Acquired">\n'
        f'      <bpmn:outgoing>flow_start_to_0</bpmn:outgoing>\n'
        f'    </bpmn:startEvent>'
    )

    prev_id = start_id
    for i, stage in enumerate(sorted_stages):
        stage_name = stage.get("name", f"stage_{i}")
        display_name = stage.get("display_name", stage_name)
        node_id = f"receive_{stage_name}"
        flow_id = f"flow_{prev_id.split('_', 1)[-1] if '_' in prev_id else prev_id}_to_{i}"

        # Sequence flow from previous node
        sequence_flows.append(
            f'    <bpmn:sequenceFlow id="{flow_id}" '
            f'sourceRef="{prev_id}" targetRef="{node_id}" />'
        )

        # Receive task (waits for message correlation)
        flow_nodes.append(
            f'    <bpmn:receiveTask id="{node_id}" name="{display_name}" '
            f'messageRef="msg_{stage_name}">\n'
            f'      <bpmn:incoming>{flow_id}</bpmn:incoming>\n'
            f'      <bpmn:outgoing>flow_{i}_to_{i + 1}</bpmn:outgoing>\n'
            f'    </bpmn:receiveTask>'
        )

        prev_id = node_id

    # End event
    end_id = "end_event"
    end_flow_id = f"flow_{len(sorted_stages) - 1}_to_{len(sorted_stages)}"
    sequence_flows.append(
        f'    <bpmn:sequenceFlow id="{end_flow_id}" '
        f'sourceRef="{prev_id}" targetRef="{end_id}" />'
    )
    flow_nodes.append(
        f'    <bpmn:endEvent id="{end_id}" name="Converted">\n'
        f'      <bpmn:incoming>{end_flow_id}</bpmn:incoming>\n'
        f'    </bpmn:endEvent>'
    )

    # Message definitions
    messages = "\n".join(
        f'  <bpmn:message id="msg_{s.get("name", f"stage_{i}")}" '
        f'name="{s.get("name", f"stage_{i}")}" />'
        for i, s in enumerate(sorted_stages)
    )

    # Assemble XML
    nodes_xml = "\n".join(flow_nodes)
    flows_xml = "\n".join(sequence_flows)

    bpmn_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
                  xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
                  id="Definitions_1"
                  targetNamespace="http://funnelier.ir/bpmn">
{messages}
  <bpmn:process id="{process_key}" name="{process_name}" isExecutable="true">
{nodes_xml}
{flows_xml}
  </bpmn:process>
</bpmn:definitions>"""

    return bpmn_xml

