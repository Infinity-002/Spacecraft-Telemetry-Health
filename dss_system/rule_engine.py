"""Deterministic spacecraft safety checks."""

from dataclasses import dataclass, field
from typing import Mapping, Optional, Iterable, List


@dataclass(frozen=True)
class RuleResult:
    severity: str
    confidence: float
    action: str
    violated_rules: List[str] = field(default_factory=list)

    @property
    def violated_rule(self) -> Optional[str]:
        if self.violated_rules:
            return self.violated_rules[0]
        return None

    @property
    def triggered(self) -> bool:
        return len(self.violated_rules) > 0


IMMEDIATE_LIMITS = [
    ("batt_voltage", "<", 31.2, "Battery voltage below survival floor"),
    ("temp_batt", ">", 45.0, "Battery temperature above critical limit"),
    ("temp_tx", ">", 65.0, "Transmitter temperature above critical limit"),
    ("batt_soc", "<", 15.0, "Battery SoC critically depleted"),
    ("rw_speed", ">", 6000.0, "Reaction wheel speed saturation"),
    ("rw_speed", "<", -6000.0, "Reaction wheel speed saturation"),
    ("rw_current", ">", 2.5, "Reaction wheel motor overcurrent"),
    ("pointing_error", ">", 1.0, "Attitude pointing loss critical"),
    ("cpu_usage", ">", 95.0, "OBC processor overload"),
    ("bus_voltage", "<", 24.0, "Bus voltage below survival floor"),
]

INVESTIGATE_LIMITS = [
    ("batt_voltage", "<", 31.8, "Battery voltage below caution limit"),
    ("temp_batt", ">", 35.0, "Battery temperature above caution limit"),
    ("temp_tx", ">", 55.0, "Transmitter temperature above caution limit"),
    ("batt_soc", "<", 20.0, "Battery SoC below caution"),
    ("rw_speed", ">", 5000.0, "Reaction wheel approaching saturation"),
    ("rw_speed", "<", -5000.0, "Reaction wheel approaching saturation"),
    ("rw_current", ">", 1.8, "Reaction wheel current elevated"),
    ("pointing_error", ">", 0.5, "Pointing error above caution limit"),
    ("temp_rw", ">", 55.0, "Reaction wheel motor overheating"),
    ("bus_voltage", "<", 26.0, "Bus voltage below caution"),
    ("cpu_usage", ">", 85.0, "OBC processor high"),
]


def _violates(value: float, operator: str, threshold: float) -> bool:
    if operator == "<":
        return value < threshold
    if operator == ">":
        return value > threshold
    raise ValueError(f"Unsupported rule operator: {operator}")


def _check_limit(row: Mapping[str, float], limits: Iterable[tuple]) -> List[str]:
    violations = []
    for column, operator, threshold, message in limits:
        if column in row:
            value = float(row[column])
            if _violates(value, operator, threshold):
                violations.append(f"{message}: {column}={value:.2f} {operator} {threshold:.2f}")
    return violations


def evaluate_rules(row: Mapping[str, float]) -> RuleResult:
    immediate = _check_limit(row, IMMEDIATE_LIMITS)
    if immediate:
        return RuleResult(
            severity="Immediate Action",
            confidence=1.0,
            action="Enter safe mode and prioritize subsystem stabilization.",
            violated_rules=immediate,
        )

    investigate = _check_limit(row, INVESTIGATE_LIMITS)
    if investigate:
        return RuleResult(
            severity="Investigate",
            confidence=0.9,
            action="Open engineering investigation and trend affected telemetry.",
            violated_rules=investigate,
        )

    return RuleResult(
        severity="Nominal",
        confidence=0.75,
        action="Continue monitoring.",
        violated_rules=[],
    )
