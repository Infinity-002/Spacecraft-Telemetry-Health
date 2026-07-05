"""Pass-level aggregation for spacecraft telemetry decisions."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
import pandas as pd

from .fusion_engine import Decision
from .trend_detector import TrendAlert


SEVERITY_ORDER = {
    "Nominal": 0,
    "Monitor": 1,
    "Investigate": 2,
    "Immediate Action": 3,
    "Immediate": 3,
}


@dataclass(frozen=True)
class PassSummary:
    mission_id: str
    pass_number: int
    start_time: datetime
    end_time: datetime
    overall_severity: str
    overall_confidence: float
    overall_uncertainty: float
    flagged_subsystems: list[str]
    num_notes: int
    num_rule_overrides: int
    worst_decision: Decision
    decisions: list[dict]
    summary_text: str
    trend_alerts: List[TrendAlert] = field(default_factory=list)


def aggregate_pass(
    decisions: list[dict],
    pass_number: int = 1,
    trend_alerts: Optional[List[TrendAlert]] = None
) -> PassSummary:
    if not decisions:
        raise ValueError("Cannot aggregate empty decisions list.")

    mission_id = decisions[0]["mission_id"]
    start_time = pd.to_datetime(decisions[0]["timestamp"]).to_pydatetime()
    end_time = pd.to_datetime(decisions[-1]["timestamp"]).to_pydatetime()

    overall_severity = max(
        (d["severity"] for d in decisions),
        key=lambda s: SEVERITY_ORDER.get(s, 0)
    )

    overall_confidence = sum(d["confidence"] for d in decisions) / len(decisions)
    overall_uncertainty = max(d.get("uncertainty", 0.0) for d in decisions)
    num_notes = len(decisions)

    num_rule_overrides = sum(
        1 for d in decisions if "Rule override" in str(d.get("explanation", ""))
    )

    flagged_subsystems = sorted(
        list(set(d["subsystem"] for d in decisions if d["severity"] != "Nominal"))
    )

    worst_dict = max(
        decisions,
        key=lambda d: SEVERITY_ORDER.get(d["severity"], 0)
    )

    worst_decision = Decision(
        severity=worst_dict["severity"],
        confidence=worst_dict["confidence"],
        recommended_action=worst_dict["action"],
        explanation=worst_dict["explanation"],
        severity_index=worst_dict.get("severity_index", 0.0),
        uncertainty=worst_dict.get("uncertainty", 0.0),
        conflict=worst_dict.get("conflict", 0.0),
    )

    if overall_severity == "Nominal":
        summary_text = f"Pass {pass_number} ({mission_id}): {num_notes} notes, all nominal. No concerns."
    else:
        flagged_str = ", ".join(flagged_subsystems)
        override_word = "override" if num_rule_overrides == 1 else "overrides"
        summary_text = (
            f"Pass {pass_number} ({mission_id}): {num_notes} notes, worst={overall_severity} "
            f"(confidence {overall_confidence:.2f}). Flagged: {flagged_str}. "
            f"{num_rule_overrides} rule {override_word}."
        )

    alerts_list = trend_alerts if trend_alerts is not None else []

    return PassSummary(
        mission_id=mission_id,
        pass_number=pass_number,
        start_time=start_time,
        end_time=end_time,
        overall_severity=overall_severity,
        overall_confidence=overall_confidence,
        overall_uncertainty=overall_uncertainty,
        flagged_subsystems=flagged_subsystems,
        num_notes=num_notes,
        num_rule_overrides=num_rule_overrides,
        worst_decision=worst_decision,
        decisions=decisions,
        summary_text=summary_text,
        trend_alerts=alerts_list,
    )

def assign_orbit_numbers(
    decisions: list[dict],
    scenario_log: pd.DataFrame,
) -> list[dict]:
    orbit_events = (
        scenario_log[scenario_log["type"].eq("EVENT")]
        .loc[:, ["mission_id", "timestamp", "orbit_number"]]
        .sort_values(["mission_id", "timestamp"])
        .copy()
    )

    orbit_events["timestamp"] = pd.to_datetime(orbit_events["timestamp"])

    decisions_df = pd.DataFrame(decisions).copy()
    decisions_df["timestamp"] = pd.to_datetime(decisions_df["timestamp"])

    assigned = []

    for mission_id, mission_decisions in decisions_df.groupby("mission_id"):
        mission_events = orbit_events[orbit_events["mission_id"] == mission_id]
        mission_decisions = mission_decisions.sort_values("timestamp")

        if mission_events.empty:
            mission_decisions["orbit_number"] = 1
            assigned.append(mission_decisions)
            continue

        merged = pd.merge_asof(
            mission_decisions,
            mission_events[["timestamp", "orbit_number"]].sort_values("timestamp"),
            on="timestamp",
            direction="backward",
        )

        merged["orbit_number"] = merged["orbit_number"].fillna(1).astype(int)
        assigned.append(merged)

    if not assigned:
        return []

    result = pd.concat(assigned, ignore_index=True)
    return result.to_dict("records")


def aggregate_all_passes(
    decisions: list[dict],
    scenario_log: pd.DataFrame,
    trend_alerts: Optional[List[TrendAlert]] = None,
) -> list[PassSummary]:
    if not decisions:
        return []

    assigned_decisions = assign_orbit_numbers(decisions, scenario_log)

    from collections import defaultdict

    by_pass = defaultdict(list)
    for decision in assigned_decisions:
        key = (decision["mission_id"], int(decision["orbit_number"]))
        by_pass[key].append(decision)

    all_summaries = []

    for (mission_id, orbit_number), pass_decisions in sorted(by_pass.items()):
        pass_decisions = sorted(pass_decisions, key=lambda d: pd.to_datetime(d["timestamp"]))

        overlapping = []
        if trend_alerts:
            overlapping = [
                alert for alert in trend_alerts
                if alert.mission_id == mission_id
            ]

        summary = aggregate_pass(
            pass_decisions,
            pass_number=orbit_number,
            trend_alerts=overlapping,
        )
        all_summaries.append(summary)

    return all_summaries
