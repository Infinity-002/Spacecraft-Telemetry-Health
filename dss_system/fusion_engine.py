"""Evidence fusion for telemetry, rules, and operator notes using Dempster-Shafer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import Optional
import numpy as np

from .reliability_module import ReliabilityResult
from .rule_engine import RuleResult

if TYPE_CHECKING:
    from .joint_context_model import NoteContext


@dataclass(frozen=True)
class Decision:
    severity: str
    confidence: float
    recommended_action: str
    explanation: str
    severity_index: float
    uncertainty: float
    conflict: float


NOTE_SCORES = {
    "Nominal": 0.0,
    "None": 0.0,
    "Low": 0.25,
    "Medium": 0.5,
    "High": 0.8,
    "Critical": 1.0,
}

THETA = frozenset({"Nominal", "Monitor", "Investigate", "Immediate"})


def _severity_from_index(index: float) -> tuple[str, str]:
    if index >= 0.75:
        return "Immediate Action", "Enter safe mode or execute the relevant contingency procedure."
    if index >= 0.45:
        return "Investigate", "Assign subsystem owner and increase telemetry sampling."
    if index >= 0.2:
        return "Monitor", "Trend the affected parameters on the next pass."
    return "Nominal", "Continue monitoring."

def _severity_rank(severity: str) -> int:
    return {
        "Nominal": 0,
        "Monitor": 1,
        "Investigate": 2,
        "Immediate Action": 3,
        "Immediate": 3,
    }.get(severity, 0)


def _max_severity(a: str, b: str) -> str:
    return a if _severity_rank(a) >= _severity_rank(b) else b


def combine_three_bbas(
    m1: dict[frozenset[str], float],
    m2: dict[frozenset[str], float],
    m3: dict[frozenset[str], float]
) -> tuple[dict[frozenset[str], float], float]:
    combined = {}
    K = 0.0
    for s1, w1 in m1.items():
        for s2, w2 in m2.items():
            for s3, w3 in m3.items():
                intersection = s1 & s2 & s3
                prod = w1 * w2 * w3
                if not intersection:
                    K += prod
                else:
                    combined[intersection] = combined.get(intersection, 0.0) + prod

    if K >= 1.0:
        return {THETA: 1.0}, 1.0

    for s in combined:
        combined[s] /= (1.0 - K)

    return combined, K


def fuse_evidence(
    rule_result: RuleResult,
    telemetry_score: float,
    note_context: NoteContext,
    reliability: ReliabilityResult,
    telemetry_weight: float = 0.7,
    telemetry_pvalue: Optional[float] = None,
) -> Decision:
    # 1. Rule Engine BBA
    m_rule = {}
    if rule_result.triggered:
        if rule_result.severity == "Immediate Action":
            m_rule[frozenset({"Immediate"})] = 0.95
            m_rule[THETA] = 0.05
        elif rule_result.severity == "Investigate":
            m_rule[frozenset({"Investigate"})] = 0.85
            m_rule[THETA] = 0.15
        else:
            m_rule[frozenset({rule_result.severity})] = 0.85
            m_rule[THETA] = 0.15
    else:
        m_rule[THETA] = 1.0

    # 2. Telemetry BBA
    m_tel = {}
    if telemetry_pvalue is not None and not np.isnan(telemetry_pvalue) and telemetry_pvalue >= 0.0:
        if telemetry_pvalue > 0.05:
            m_tel[frozenset({"Nominal"})] = 0.7
            m_tel[THETA] = 0.3
        elif 0.001 <= telemetry_pvalue <= 0.05:
            m_tel[frozenset({"Monitor"})] = 0.6
            m_tel[frozenset({"Nominal"})] = 0.15
            m_tel[THETA] = 0.25
        else:
            m_tel[frozenset({"Investigate"})] = 0.6
            m_tel[frozenset({"Monitor"})] = 0.2
            m_tel[THETA] = 0.2
    else:
        if telemetry_score is not None and not np.isnan(telemetry_score):
            if telemetry_score < 0.15:
                m_tel[frozenset({"Nominal"})] = 0.7
                m_tel[THETA] = 0.3
            elif 0.15 <= telemetry_score <= 0.4:
                m_tel[frozenset({"Monitor"})] = 0.5
                m_tel[frozenset({"Nominal"})] = 0.2
                m_tel[THETA] = 0.3
            elif 0.4 < telemetry_score <= 0.7:
                m_tel[frozenset({"Investigate"})] = 0.6
                m_tel[frozenset({"Monitor"})] = 0.15
                m_tel[THETA] = 0.25
            else:
                m_tel[frozenset({"Investigate"})] = 0.6
                m_tel[frozenset({"Monitor"})] = 0.2
                m_tel[THETA] = 0.2
        else:
            m_tel[THETA] = 1.0

    # 3. Note BBA
    urgency = note_context.urgency
    m_note_base_set = frozenset({"Nominal"})
    if urgency == "Critical":
        m_note_base_set = frozenset({"Immediate"})
    elif urgency == "High":
        m_note_base_set = frozenset({"Investigate"})
    elif urgency in ("Medium", "Low"):
        m_note_base_set = frozenset({"Monitor"})

    w = reliability.weight
    m_note = {
        m_note_base_set: w,
        THETA: 1.0 - w
    }

    # Combine evidence using Dempster's rule
    m_combined, K = combine_three_bbas(m_rule, m_tel, m_note)

    # Compute Belief and Plausibility for singletons
    singletons = ["Nominal", "Monitor", "Investigate", "Immediate"]

    def belief(x: str) -> float:
        s_target = frozenset({x})
        return sum(val for s, val in m_combined.items() if s.issubset(s_target))

    def plausibility(x: str) -> float:
        s_target = frozenset({x})
        return sum(val for s, val in m_combined.items() if not s.isdisjoint(s_target))

    winner = max(singletons, key=belief)
    win_bel = belief(winner)
    win_pl = plausibility(winner)
    uncertainty = win_pl - win_bel

    # Map "Immediate" to "Immediate Action" for consistency with existing code
    severity = winner
    if severity == "Immediate":
        severity = "Immediate Action"

    telemetry_floor = "Nominal"

    if telemetry_pvalue is not None and not np.isnan(telemetry_pvalue):
        if telemetry_pvalue < 0.001:
            telemetry_floor = "Investigate"
        elif telemetry_pvalue < 0.01:
            telemetry_floor = "Monitor"

    severity = _max_severity(severity, telemetry_floor)

    # Default action based on combined severity
    severity_actions = {
        "Immediate Action": "Enter safe mode or execute the relevant contingency procedure.",
        "Investigate": "Assign subsystem owner and increase telemetry sampling.",
        "Monitor": "Trend the affected parameters on the next pass.",
        "Nominal": "Continue monitoring.",
    }
    action = severity_actions.get(severity, "Continue monitoring.")

    # Apply note action override if urgency suggests concern
    if note_context.action != "None" and severity != "Nominal":
        action = note_context.action

    # Compute fallback severity index
    note_score = NOTE_SCORES.get(note_context.urgency, 0.0)
    note_weight = (1.0 - telemetry_weight) * reliability.weight
    tel_score_val = telemetry_score if (telemetry_score is not None and not np.isnan(telemetry_score)) else 0.0
    severity_index = telemetry_weight * tel_score_val + note_weight * note_score

    p_str = f"{telemetry_pvalue:.4f}" if (telemetry_pvalue is not None and not np.isnan(telemetry_pvalue)) else "N/A"
    score_str = f"{telemetry_score:.2f}" if (telemetry_score is not None and not np.isnan(telemetry_score)) else "N/A"
    explanation = (
        f"Fused telemetry score {score_str} (p-value: {p_str}) with "
        f"{note_context.urgency.lower()} note urgency at reliability {reliability.weight:.2f}. "
        f"Fault type: {note_context.fault_type}. {reliability.explanation}. "
        f"Conflict K: {K:.2f}, Uncertainty: {uncertainty:.2f}."
    )

    # Respect rule engine triggers as an override if they exist
    if rule_result.triggered:
        return Decision(
            severity=rule_result.severity,
            confidence=rule_result.confidence,
            recommended_action=rule_result.action,
            explanation=f"Rule override: {rule_result.violated_rule}",
            severity_index=1.0 if rule_result.severity == "Immediate Action" else 0.55,
            uncertainty=uncertainty,
            conflict=K,
        )

    return Decision(
        severity=severity,
        confidence=win_bel,
        recommended_action=action,
        explanation=explanation,
        severity_index=severity_index,
        uncertainty=uncertainty,
        conflict=K,
    )
