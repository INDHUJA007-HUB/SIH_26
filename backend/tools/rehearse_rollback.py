"""Restore a real ECS service to an immutable task definition and verify convergence.

This does not certify database compatibility or a traffic-weighted canary. Run in
staging with the approved previous task definition, then retain the JSON result.
"""

from __future__ import annotations

import argparse
import json
from typing import Any

import boto3


def restore_service(client: Any, cluster: str, service: str, baseline: str) -> dict[str, Any]:
    before = client.describe_services(cluster=cluster, services=[service])
    if before.get("failures") or not before.get("services"):
        raise ValueError("Service is not available")
    client.update_service(
        cluster=cluster,
        service=service,
        taskDefinition=baseline,
        deploymentConfiguration={"deploymentCircuitBreaker": {"enable": True, "rollback": True}},
    )
    client.get_waiter("services_stable").wait(
        cluster=cluster, services=[service], WaiterConfig={"Delay": 15, "MaxAttempts": 40}
    )
    after = client.describe_services(cluster=cluster, services=[service])
    state = after["services"][0]
    if (
        state["taskDefinition"] != baseline
        or state["runningCount"] != state["desiredCount"]
        or state["desiredCount"] == 0
    ):
        raise RuntimeError(
            "Baseline service did not converge to the requested running task definition"
        )
    return {
        "service": service,
        "task_definition": baseline,
        "running_count": state["runningCount"],
        "rollback_status": "VERIFIED_SERVICE_STABILITY",
        "database_compatibility": "UNMEASURED",
        "traffic_weighted_canary": "NOT_EXECUTED",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cluster", required=True)
    parser.add_argument("--service", required=True)
    parser.add_argument("--baseline-task-definition", required=True)
    parser.add_argument("--region", default="ap-south-1")
    args = parser.parse_args()
    result = restore_service(
        boto3.client("ecs", region_name=args.region),
        args.cluster,
        args.service,
        args.baseline_task_definition,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
