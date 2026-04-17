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
    stale_timeouts: dict[str, str] | None = None,
) -> str:
    """
    Generate a BPMN XML for a funnel journey process from stage configuration.

    Each stage becomes a message intermediate catch event followed by an
    external-task service task that updates the contact's stage in the
    database via the ``update-funnel-stage`` worker.

    Optional boundary timer events fire ``notify-stale-stage`` when a
    contact stays too long at a given stage.

    This enables per-tenant custom funnel workflows.

    Args:
        stages: List of stage dicts with 'name', 'display_name', 'order' keys
        process_key: BPMN process definition key
        process_name: Human-readable process name
        stale_timeouts: Optional mapping of stage_name → ISO 8601 duration
                        (e.g. ``{"sms_sent": "P14D", "call_answered": "P7D"}``)

    Returns:
        BPMN 2.0 XML string
    """
    sorted_stages = sorted(stages, key=lambda s: s.get("order", 0))
    stale_timeouts = stale_timeouts or {}

    flow_nodes: list[str] = []
    sequence_flows: list[str] = []
    stale_nodes: list[str] = []
    stale_flows: list[str] = []

    # Start event
    start_id = "start_event"
    flow_nodes.append(
        f'    <bpmn:startEvent id="{start_id}" name="Lead Acquired">\n'
        f'      <bpmn:outgoing>flow_start_to_update_0</bpmn:outgoing>\n'
        f'    </bpmn:startEvent>'
    )

    # First update task (record lead_acquired)
    update_id_0 = "update_stage_0"
    flow_nodes.append(
        f'    <bpmn:serviceTask id="{update_id_0}" name="Update: Lead Acquired"\n'
        f'                      camunda:type="external" camunda:topic="update-funnel-stage">\n'
        f'      <bpmn:incoming>flow_start_to_update_0</bpmn:incoming>\n'
        f'      <bpmn:outgoing>flow_update_0_to_wait_0</bpmn:outgoing>\n'
        f'    </bpmn:serviceTask>'
    )
    sequence_flows.append(
        f'    <bpmn:sequenceFlow id="flow_start_to_update_0" '
        f'sourceRef="{start_id}" targetRef="{update_id_0}" />'
    )

    prev_outgoing = f"flow_update_0_to_wait_0"
    prev_ref = update_id_0

    for i, stage in enumerate(sorted_stages):
        stage_name = stage.get("name", f"stage_{i}")
        display_name = stage.get("display_name", stage_name)
        wait_id = f"wait_{stage_name}"
        update_id = f"update_stage_{stage_name}"

        flow_to_wait = f"flow_{prev_ref}_to_{wait_id}"
        flow_wait_to_update = f"flow_{wait_id}_to_{update_id}"

        # Sequence flow from previous → wait
        if prev_outgoing != flow_to_wait:
            # Already emitted above for first stage
            sequence_flows.append(
                f'    <bpmn:sequenceFlow id="{prev_outgoing}" '
                f'sourceRef="{prev_ref}" targetRef="{wait_id}" />'
            )

        # Message catch event
        flow_nodes.append(
            f'    <bpmn:intermediateCatchEvent id="{wait_id}" name="{display_name}">\n'
            f'      <bpmn:incoming>{prev_outgoing}</bpmn:incoming>\n'
            f'      <bpmn:outgoing>{flow_wait_to_update}</bpmn:outgoing>\n'
            f'      <bpmn:messageEventDefinition messageRef="msg_{stage_name}" />\n'
            f'    </bpmn:intermediateCatchEvent>'
        )

        # Optional boundary timer for stale stages
        if stage_name in stale_timeouts:
            duration = stale_timeouts[stage_name]
            timer_id = f"timer_stale_{stage_name}"
            notify_id = f"notify_stale_{stage_name}"
            end_stale_id = f"end_stale_{stage_name}"
            flow_timer = f"flow_stale_{stage_name}_to_notify"
            flow_stale_end = f"flow_stale_{stage_name}_end"

            stale_nodes.append(
                f'    <bpmn:boundaryEvent id="{timer_id}" name="Stale: {display_name}"\n'
                f'                        attachedToRef="{wait_id}" cancelActivity="false">\n'
                f'      <bpmn:outgoing>{flow_timer}</bpmn:outgoing>\n'
                f'      <bpmn:timerEventDefinition>\n'
                f'        <bpmn:timeDuration>{duration}</bpmn:timeDuration>\n'
                f'      </bpmn:timerEventDefinition>\n'
                f'    </bpmn:boundaryEvent>'
            )
            stale_nodes.append(
                f'    <bpmn:serviceTask id="{notify_id}" name="Notify: Stale {display_name}"\n'
                f'                      camunda:type="external" camunda:topic="notify-stale-stage">\n'
                f'      <bpmn:incoming>{flow_timer}</bpmn:incoming>\n'
                f'      <bpmn:outgoing>{flow_stale_end}</bpmn:outgoing>\n'
                f'    </bpmn:serviceTask>'
            )
            stale_nodes.append(
                f'    <bpmn:endEvent id="{end_stale_id}">\n'
                f'      <bpmn:incoming>{flow_stale_end}</bpmn:incoming>\n'
                f'    </bpmn:endEvent>'
            )
            stale_flows.append(
                f'    <bpmn:sequenceFlow id="{flow_timer}" '
                f'sourceRef="{timer_id}" targetRef="{notify_id}" />'
            )
            stale_flows.append(
                f'    <bpmn:sequenceFlow id="{flow_stale_end}" '
                f'sourceRef="{notify_id}" targetRef="{end_stale_id}" />'
            )

        # Sequence flow wait → update
        sequence_flows.append(
            f'    <bpmn:sequenceFlow id="{flow_wait_to_update}" '
            f'sourceRef="{wait_id}" targetRef="{update_id}" />'
        )

        # External task service task (DB update)
        next_outgoing = f"flow_{update_id}_to_next"
        flow_nodes.append(
            f'    <bpmn:serviceTask id="{update_id}" name="Update: {display_name}"\n'
            f'                      camunda:type="external" camunda:topic="update-funnel-stage">\n'
            f'      <bpmn:incoming>{flow_wait_to_update}</bpmn:incoming>\n'
            f'      <bpmn:outgoing>{next_outgoing}</bpmn:outgoing>\n'
            f'    </bpmn:serviceTask>'
        )

        prev_outgoing = next_outgoing
        prev_ref = update_id

    # End event
    end_id = "end_event"
    sequence_flows.append(
        f'    <bpmn:sequenceFlow id="{prev_outgoing}" '
        f'sourceRef="{prev_ref}" targetRef="{end_id}" />'
    )
    flow_nodes.append(
        f'    <bpmn:endEvent id="{end_id}" name="Converted">\n'
        f'      <bpmn:incoming>{prev_outgoing}</bpmn:incoming>\n'
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
    stale_xml = "\n".join(stale_nodes)
    flows_xml = "\n".join(sequence_flows)
    stale_flows_xml = "\n".join(stale_flows)

    bpmn_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
                  xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
                  xmlns:camunda="http://camunda.org/schema/1.0/bpmn"
                  id="Definitions_1"
                  targetNamespace="http://funnelier.ir/bpmn">
{messages}
  <bpmn:process id="{process_key}" name="{process_name}" isExecutable="true">
{nodes_xml}
{stale_xml}
{flows_xml}
{stale_flows_xml}
  </bpmn:process>
</bpmn:definitions>"""

    return bpmn_xml


async def deploy_tenant_funnel(
    client: CamundaClient,
    tenant_id: str,
    stages: list[dict[str, Any]],
    stale_timeouts: dict[str, str] | None = None,
) -> Deployment | None:
    """
    Generate and deploy a per-tenant funnel journey BPMN process.

    Args:
        client: CamundaClient instance
        tenant_id: Tenant UUID string
        stages: List of stage dicts with 'name', 'display_name', 'order'
        stale_timeouts: Optional stage_name → ISO 8601 duration mapping

    Returns:
        Deployment object or None if Camunda is disabled
    """
    if not client.enabled:
        logger.info("Camunda disabled — skipping tenant funnel deployment")
        return None

    process_key = f"funnel_journey_{tenant_id.replace('-', '_')}"
    bpmn_xml = generate_funnel_bpmn(
        stages=stages,
        process_key=process_key,
        process_name=f"Funnel Journey (Tenant {tenant_id[:8]})",
        stale_timeouts=stale_timeouts,
    )

    try:
        deployment = await client.deploy_bpmn(
            name=f"funnel-journey-{tenant_id[:8]}",
            bpmn_xml=bpmn_xml,
            filename=f"funnel_journey_{tenant_id[:8]}.bpmn",
            tenant_id=tenant_id,
        )
        logger.info(
            "Deployed tenant funnel BPMN: tenant=%s process_key=%s deployment=%s",
            tenant_id[:8], process_key, deployment.id,
        )
        return deployment
    except CamundaConnectionError:
        logger.warning("Camunda unreachable for tenant funnel deployment: %s", tenant_id[:8])
        return None
    except Exception as e:
        logger.error("Failed to deploy tenant funnel: %s", e)
        return None


