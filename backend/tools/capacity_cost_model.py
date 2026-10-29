"""Capacity and AWS Infrastructure Cost Model Calculator (Subphase 13.4).

Calculates:
1. Worker equivalents: W = ceil(lambda * S / target_utilization).
2. Throughput capacity across peak regulatory submission window (10,000 applications in 30 days).
3. AWS infrastructure cost breakdown (ECS tasks, RDS multi-AZ, S3, KMS, CloudWatch).
4. Unit economics: cost per page and cost per application packet.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass


@dataclass
class WorkloadProfile:
    total_applications: int = 10_000
    peak_window_days: int = 30
    working_hours_per_day: float = 12.0
    pages_per_application: int = 50
    avg_service_time_sec_per_page: float = 1.2
    target_utilization: float = 0.70  # 70% target utilization to absorb M/M/c queueing bursts


@dataclass
class CostBreakdown:
    ecs_fargate_monthly_usd: float
    rds_aurora_monthly_usd: float
    s3_storage_monthly_usd: float
    kms_requests_monthly_usd: float
    cloudwatch_monthly_usd: float
    total_monthly_usd: float
    total_monthly_inr: float
    cost_per_application_usd: float
    cost_per_application_inr: float
    cost_per_page_usd: float
    cost_per_page_inr: float


def calculate_capacity_and_cost(
    profile: WorkloadProfile,
    inr_per_usd: float = 85.0,
) -> dict[str, object]:
    """Compute worker equivalents and cost breakdown for the regulatory workload."""
    # 1. Arrival Rate Calculations
    total_pages = profile.total_applications * profile.pages_per_application
    total_seconds = profile.peak_window_days * profile.working_hours_per_day * 3600.0

    lambda_apps_per_sec = profile.total_applications / total_seconds
    lambda_pages_per_sec = total_pages / total_seconds

    # Peak arrival factor (assumes 2.5x peak burst during final 7 days)
    peak_multiplier = 2.5
    lambda_peak_pages_per_sec = lambda_pages_per_sec * peak_multiplier

    # 2. Worker Equivalents Calculation: W = ceil(lambda * S / u)
    service_time = profile.avg_service_time_sec_per_page
    u = profile.target_utilization

    sustained_workers = math.ceil((lambda_pages_per_sec * service_time) / u)
    peak_burst_workers = math.ceil((lambda_peak_pages_per_sec * service_time) / u)

    # 3. AWS Infrastructure Pricing (us-east-1 / ap-south-1 baseline)
    # ECS Fargate: 2 vCPU, 4 GB RAM worker tasks
    # $0.04048 per vCPU-hr, $0.004445 per GB-hr
    task_vcpu = 2
    task_gb = 4
    hourly_cost_per_task = (task_vcpu * 0.04048) + (task_gb * 0.004445)  # $0.09874 / task-hr
    hours_in_month = 730.0

    # Auto-scaling model: average pool size halfway between sustained and peak
    avg_pool_size = (sustained_workers + peak_burst_workers) / 2.0
    ecs_monthly = avg_pool_size * hourly_cost_per_task * hours_in_month

    # RDS Aurora PostgreSQL Multi-AZ (db.r6g.xlarge: 4 vCPU, 32 GB RAM): $0.52/hr * 2 (Multi-AZ)
    rds_hourly = 0.52 * 2.0
    rds_monthly = rds_hourly * hours_in_month  # ~$759.20/mo

    # S3 Storage & API: 10,000 apps * 50 pages * 500 KB/page = 250 GB
    storage_gb = (total_pages * 500.0) / (1024.0 * 1024.0)
    s3_storage = storage_gb * 0.023
    s3_api_calls = (
        (total_pages * 4) / 1000.0 * 0.005
    )  # 4 S3 ops per page (put original, derivatives, get)
    s3_monthly = s3_storage + s3_api_calls

    # KMS: 10,000 apps * 20 envelope encryptions = 200,000 KMS requests @ $0.03/10k
    kms_monthly = (profile.total_applications * 20.0 / 10_000.0) * 0.03

    # CloudWatch: Structured JSON telemetry + alarms (~$50/mo)
    cloudwatch_monthly = 50.0

    total_monthly_usd = ecs_monthly + rds_monthly + s3_monthly + kms_monthly + cloudwatch_monthly
    total_monthly_inr = total_monthly_usd * inr_per_usd

    cost_per_app_usd = total_monthly_usd / profile.total_applications
    cost_per_app_inr = cost_per_app_usd * inr_per_usd

    cost_per_page_usd = total_monthly_usd / total_pages
    cost_per_page_inr = cost_per_page_usd * inr_per_usd

    breakdown = CostBreakdown(
        ecs_fargate_monthly_usd=round(ecs_monthly, 2),
        rds_aurora_monthly_usd=round(rds_monthly, 2),
        s3_storage_monthly_usd=round(s3_monthly, 2),
        kms_requests_monthly_usd=round(kms_monthly, 2),
        cloudwatch_monthly_usd=round(cloudwatch_monthly, 2),
        total_monthly_usd=round(total_monthly_usd, 2),
        total_monthly_inr=round(total_monthly_inr, 2),
        cost_per_application_usd=round(cost_per_app_usd, 4),
        cost_per_application_inr=round(cost_per_app_inr, 2),
        cost_per_page_usd=round(cost_per_page_usd, 4),
        cost_per_page_inr=round(cost_per_page_inr, 4),
    )

    return {
        "workload_profile": asdict(profile),
        "rates": {
            "total_pages": total_pages,
            "sustained_arrival_apps_per_sec": round(lambda_apps_per_sec, 4),
            "sustained_arrival_pages_per_sec": round(lambda_pages_per_sec, 4),
            "peak_burst_pages_per_sec": round(lambda_peak_pages_per_sec, 4),
        },
        "worker_equivalents": {
            "target_utilization": profile.target_utilization,
            "sustained_workers_required": sustained_workers,
            "peak_burst_workers_required": peak_burst_workers,
            "formula": "W = ceil(lambda * S / u)",
        },
        "cost_model": asdict(breakdown),
    }


def format_report_markdown(result: dict[str, object]) -> str:
    """Format capacity & cost report into markdown."""
    cost = result["cost_model"]
    workers = result["worker_equivalents"]
    rates = result["rates"]

    return f"""### Capacity and AWS Infrastructure Cost Model Qualification

#### 1. Workload Sizing & Arrival Rates
- **Regulatory Intake Window**: 10,000 applications across 30 days (12 hours/day operational).
- **Total Workload**: {rates["total_pages"]:,} pages (50 pages/packet average).
- **Sustained Arrival Rate**: {rates["sustained_arrival_pages_per_sec"]:.2f} pages/s ({rates["sustained_arrival_apps_per_sec"]:.4f} applications/s).
- **Peak Burst Arrival Rate**: {rates["peak_burst_pages_per_sec"]:.2f} pages/s (2.5x deadline surge multiplier).

#### 2. Worker Equivalents
- **Queueing / Target Utilization Factor ($u$)**: {workers["target_utilization"] * 100:.0f}%
- **Average Page Processing Time ($S$)**: 1.20s (OCR, layout analysis, fact extraction).
- **Sustained Worker Pool ($W_{{sustained}}$)**: **{workers["sustained_workers_required"]} workers** (ECS Fargate 2 vCPU / 4 GB).
- **Peak Burst Worker Pool ($W_{{peak}}$)**: **{workers["peak_burst_workers_required"]} workers** (dynamic horizontal autoscaling).
- **Capacity Sizing Formula**: $W = \\lceil \\frac{{\\lambda \\cdot S}}{{u}} \\rceil$

#### 3. Monthly Infrastructure Cost Breakdown
| AWS Infrastructure Component | Monthly Cost (USD) | Monthly Cost (INR @ INR 85/$) | Allocation Basis |
| --- | --- | --- | --- |
| **ECS Fargate Worker Pool** | ${cost["ecs_fargate_monthly_usd"]:,.2f} | INR {cost["ecs_fargate_monthly_usd"] * 85:,.2f} | Auto-scaled 2 vCPU / 4 GB tasks |
| **RDS Aurora PostgreSQL Multi-AZ** | ${cost["rds_aurora_monthly_usd"]:,.2f} | INR {cost["rds_aurora_monthly_usd"] * 85:,.2f} | db.r6g.xlarge (Multi-AZ failover) |
| **S3 Storage & Data Transfer** | ${cost["s3_storage_monthly_usd"]:,.2f} | INR {cost["s3_storage_monthly_usd"] * 85:,.2f} | 250 GB quarantined/clean storage + derivatives |
| **AWS KMS (Envelope Cryptography)** | ${cost["kms_requests_monthly_usd"]:,.2f} | INR {cost["kms_requests_monthly_usd"] * 85:,.2f} | 200,000 document crypt-operations |
| **CloudWatch (Audit & Telemetry)** | ${cost["cloudwatch_monthly_usd"]:,.2f} | INR {cost["cloudwatch_monthly_usd"] * 85:,.2f} | Immutable log streams & alarms |
| **Total Monthly Infrastructure** | **${cost["total_monthly_usd"]:,.2f}** | **INR {cost["total_monthly_inr"]:,.2f}** | Full high-availability deployment |

#### 4. Unit Economics
- **Cost per Completed Application Packet**: **${cost["cost_per_application_usd"]:.2f}** (~**INR {cost["cost_per_application_inr"]:.2f}**)
- **Cost per Processed Page**: **${cost["cost_per_page_usd"]:.4f}** (~**INR {cost["cost_per_page_inr"]:.4f}**)
"""


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Capacity and cost model calculator.")
    parser.add_argument("--json", action="store_true", help="Output JSON format")
    args = parser.parse_args()

    res = calculate_capacity_and_cost(WorkloadProfile())
    if args.json:
        print(json.dumps(res, indent=2))
    else:
        print(format_report_markdown(res))
