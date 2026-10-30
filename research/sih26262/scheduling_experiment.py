"""Illustrative scheduling comparison on six synthetic cases, not AICTE field data.

Eligibility lists represent already-authorized committees. This experiment does not
select committee members, establish legal rules, or measure production performance.
All methods see the same inputs. Exhaustive search certifies only this tiny model.
"""

import json
from itertools import permutations
from pathlib import Path

CASES = [
    {"id": "A", "created_order": 1, "due_day": 1, "eligible": ["C1", "C2"]},
    {"id": "B", "created_order": 2, "due_day": 1, "eligible": ["C1"]},
    {"id": "C", "created_order": 3, "due_day": 2, "eligible": ["C2"]},
    {"id": "D", "created_order": 4, "due_day": 2, "eligible": ["C1", "C2"]},
    {"id": "E", "created_order": 5, "due_day": 3, "eligible": ["C1"]},
    {"id": "F", "created_order": 6, "due_day": 3, "eligible": ["C2"]},
]
SLOTS = [(day, committee) for day in (1, 2, 3) for committee in ("C1", "C2")]


def summarize(assignments):
    by_id = {c["id"]: c for c in CASES}
    assert len({a["case"] for a in assignments}) == len(assignments)
    assert len({(a["day"], a["committee"]) for a in assignments}) == len(assignments)
    assert all(a["committee"] in by_id[a["case"]]["eligible"] for a in assignments)
    late = [a["case"] for a in assignments if a["day"] > by_id[a["case"]]["due_day"]]
    return {
        "scheduled": len(assignments),
        "late_count": len(late),
        "late_cases": late,
        "total_tardiness_days": sum(
            max(0, a["day"] - by_id[a["case"]]["due_day"]) for a in assignments
        ),
        "assignments": assignments,
    }


def greedy(key):
    pending = sorted(CASES, key=key)
    assignments = []
    for day, committee in SLOTS:
        selected = next((c for c in pending if committee in c["eligible"]), None)
        if selected:
            assignments.append(
                {"case": selected["id"], "day": day, "committee": committee}
            )
            pending.remove(selected)
    return summarize(assignments)


def exhaustive():
    best = None
    feasible_count = 0
    for ordering in permutations(CASES):
        if not all(
            committee in case["eligible"]
            for (_, committee), case in zip(SLOTS, ordering, strict=True)
        ):
            continue
        feasible_count += 1
        candidate = summarize(
            [
                {"case": case["id"], "day": day, "committee": committee}
                for (day, committee), case in zip(SLOTS, ordering, strict=True)
            ]
        )
        score = candidate["late_count"], candidate["total_tardiness_days"]
        if best is None or score < (best["late_count"], best["total_tardiness_days"]):
            best = candidate
    assert best is not None
    best["solver_status"] = "OPTIMAL_FOR_ENUMERATED_SYNTHETIC_MODEL"
    best["feasible_complete_assignments_checked"] = feasible_count
    return best


def run():
    report = {
        "label": "ILLUSTRATIVE_SYNTHETIC_EXPERIMENT",
        "scope": "6 cases, 2 pre-authorized committees, 3 days, one visit per committee per day",
        "cases": CASES,
        "results": {
            "FIFO_greedy": greedy(lambda c: c["created_order"]),
            "earliest_deadline_greedy": greedy(
                lambda c: (c["due_day"], c["created_order"])
            ),
            "scarcity_aware_deadline_greedy": greedy(
                lambda c: (c["due_day"], len(c["eligible"]), c["created_order"])
            ),
            "exhaustive_optimum": exhaustive(),
        },
        "interpretation": "A simple constraint-aware heuristic matches the exact optimum on this fixture. This does not demonstrate general superiority or real-world time savings.",
    }
    assert report["results"]["FIFO_greedy"]["late_count"] == 1
    assert report["results"]["earliest_deadline_greedy"]["late_count"] == 1
    assert report["results"]["scarcity_aware_deadline_greedy"]["late_count"] == 0
    assert report["results"]["exhaustive_optimum"]["late_count"] == 0
    return report


if __name__ == "__main__":
    result = run()
    path = Path(__file__).with_name("scheduling_results.json")
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {name: value["late_count"] for name, value in result["results"].items()}
        )
    )
