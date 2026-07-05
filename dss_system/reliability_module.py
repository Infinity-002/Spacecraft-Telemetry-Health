"""Operator-note reliability scoring."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import TYPE_CHECKING
from typing import Mapping

import numpy as np

from . import FEATURE_COLUMNS

if TYPE_CHECKING:
    from .joint_context_model import NoteContext


@dataclass(frozen=True)
class ReliabilityResult:
    weight: float
    specificity: float
    confidence: float
    consistency: float
    explanation: str


HEDGE_PATTERN = re.compile(r"\b(maybe|possibly|looks|seems|suspect|unclear|could be|might)\b", re.I)
VALUE_PATTERN = re.compile(r"[-+]?\d+(?:\.\d+)?\s?(?:v|a|c|%|rpm|deg|degrees)?", re.I)
PARAMETER_TERMS = {
    "batt_voltage": ("battery voltage", "batt voltage", "voltage", "v"),
    "temp_batt": ("battery temp", "batt temp", "temp_batt"),
    "temp_tx": ("tx temp", "transmitter temp", "temp_tx"),
    "rw_speed": ("rw speed", "reaction wheel", "wheel speed"),
    "pointing_error": ("pointing error", "attitude error"),
}


def build_nominal_stats(frame) -> dict[str, tuple[float, float]]:
    stats = {}
    for column in FEATURE_COLUMNS:
        mean = float(frame[column].mean())
        std = float(frame[column].std(ddof=0)) or 1.0
        stats[column] = (mean, std)
    return stats


def telemetry_zscores(row: Mapping[str, float], stats: Mapping[str, tuple[float, float]]) -> dict[str, float]:
    return {
        column: (float(row[column]) - mean) / std
        for column, (mean, std) in stats.items()
    }


def _specificity(note: str) -> float:
    text = note.lower()
    parameter_hits = sum(any(term in text for term in terms) for terms in PARAMETER_TERMS.values())
    has_value = bool(VALUE_PATTERN.search(note))
    return min(1.0, 0.25 + 0.2 * parameter_hits + (0.25 if has_value else 0.0))


def _confidence(note: str) -> float:
    return 0.45 if HEDGE_PATTERN.search(note) else 0.9


SUBSYSTEM_COLUMNS = {
    "EPS": ("batt_voltage", "batt_current", "batt_soc", "sa_voltage", "sa_current", "solar_flux"),
    "TCS": ("temp_batt", "temp_tx", "temp_obc", "temp_rw", "temp_structure", "tx_temp", "obc_temp", "heater_state"),
    "ADCS": ("rw_speed", "rw_current", "rw_torque", "pointing_error"),
    "TT&C": ("tx_power", "rx_rssi", "data_rate", "comm_link_status"),
    "System": ("cpu_usage", "mem_usage"),
}

def _consistency(context: NoteContext, zscores: Mapping[str, float]) -> tuple[float, str]:
    subsystem = context.subsystem
    # Map parsed note subsystem to target telemetry columns
    target_cols = SUBSYSTEM_COLUMNS.get(subsystem, tuple(zscores.keys()))
    
    # Exclude high-variance normal operational parameters from strict consistency Z-checks
    filtered_cols = [c for c in target_cols if c in zscores and c not in ("rw_speed", "batt_soc", "rw_current")]
    
    if not filtered_cols:
        return 0.7, "no checkable telemetry columns for this subsystem"

    # Find the largest deviation only within the relevant subsystem
    largest_column, largest_z = max(
        ((col, zscores[col]) for col in filtered_cols),
        key=lambda item: abs(item[1])
    )
    abs_z = abs(float(largest_z))

    if context.expected is True and abs_z > 4.5:
        return 0.0, f"note says expected while subsystem telemetry {largest_column} z-score is {largest_z:.2f}"
    if context.expected is False and abs_z < 1.0 and context.concern in {"High", "Critical"}:
        return 0.35, "note is severe but subsystem telemetry is close to nominal"
    if context.subsystem != "System":
        return 0.85, f"note subsystem is specific; largest subsystem z-score is {largest_z:.2f}"
    return 0.7, f"largest subsystem z-score is {largest_z:.2f}"


def score_note_reliability(
    note: str,
    context: NoteContext,
    row: Mapping[str, float],
    nominal_stats: Mapping[str, tuple[float, float]],
) -> ReliabilityResult:
    zscores = telemetry_zscores(row, nominal_stats)
    specificity = _specificity(note)
    confidence = _confidence(note)
    consistency, consistency_reason = _consistency(context, zscores)
    weight = float(np.clip(0.35 * specificity + 0.25 * confidence + 0.40 * consistency, 0.0, 1.0))

    return ReliabilityResult(
        weight=weight,
        specificity=specificity,
        confidence=confidence,
        consistency=consistency,
        explanation=consistency_reason,
    )
