"""Trend detection for spacecraft telemetry parameters."""

from dataclasses import dataclass
from typing import Optional, List
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class TrendAlert:
    mission_id: str
    parameter: str
    direction: str  # "rising" or "falling"
    slope_per_hour: float
    hours_to_warning: Optional[float]
    confidence: float
    message: str


NOMINAL_WARNING_LIMITS = {
    "batt_voltage": (26.5, 31.5),
    "batt_current": (-5.0, 8.0),
    "batt_soc": (40.0, 100.0),
    "temp_batt": (0.0, 25.0),
    "sa_current": (0.0, 12.0),
    "bus_current": (1.5, 8.0),
    "bus_voltage": (27.8, 28.2),
    "temp_tx": (15.0, 50.0),
    "tx_power": (0.0, 10.0),
    "rw_speed": (-3000.0, 3000.0),
    "rw_current": (0.1, 1.2),
    "rw_torque": (-0.1, 0.1),
    "pointing_error": (0.0, 0.1),
    "cpu_usage": (5.0, 50.0),
    "solar_flux": (0.0, 1361.0),
}


def detect_trends(
    telemetry: pd.DataFrame,
    mission_id: str,
    nominal_ranges: dict[str, tuple[float, float]],  # (low_warn, high_warn)
    min_hours: float = 2.0,
    slope_threshold_sigma: float = 2.0,
) -> List[TrendAlert]:
    mission_telemetry = telemetry[telemetry["mission_id"] == mission_id].sort_values("timestamp")
    if len(mission_telemetry) < 2:
        return []

    timestamps = pd.to_datetime(mission_telemetry["timestamp"])
    time_hours = (timestamps - timestamps.min()).dt.total_seconds() / 3600.0
    x = time_hours.values

    alerts = []

    UNITS = {
        "batt_voltage": "V",
        "batt_current": "A",
        "batt_soc": "%",
        "temp_batt": "C",
        "sa_current": "A",
        "bus_current": "A",
        "bus_voltage": "V",
        "temp_tx": "C",
        "tx_power": "W",
        "rw_speed": "rpm",
        "rw_current": "A",
        "rw_torque": "Nm",
        "pointing_error": "deg",
        "cpu_usage": "%",
        "solar_flux": "W/m2",
    }

    for parameter, (low_warn, high_warn) in nominal_ranges.items():
        if parameter not in mission_telemetry.columns:
            continue
        y = mission_telemetry[parameter].values.astype(float)

        slopes = []
        i = 0
        for j in range(len(x)):
            while x[j] - x[i] > min_hours:
                i += 1
            if x[j] - x[i] >= 0.9 * min_hours:
                x_win = x[i : j + 1]
                y_win = y[i : j + 1]
                n = len(x_win)
                if n >= 2:
                    sum_x = x_win.sum()
                    sum_y = y_win.sum()
                    sum_xx = (x_win ** 2).sum()
                    sum_xy = (x_win * y_win).sum()
                    denom = n * sum_xx - sum_x ** 2
                    slope = (n * sum_xy - sum_x * sum_y) / denom if denom != 0 else 0.0
                    slopes.append(slope)

        if not slopes:
            continue

        std_slopes = np.std(slopes)
        latest_slope = slopes[-1]

        if std_slopes > 0 and abs(latest_slope) > slope_threshold_sigma * std_slopes:
            current_value = y[-1]
            direction = "rising" if latest_slope > 0 else "falling"
            unit = UNITS.get(parameter, "")

            hours_to_warning = None
            warning_limit = None
            if latest_slope > 0:
                if current_value < high_warn:
                    warning_limit = high_warn
                    hours_to_warning = (high_warn - current_value) / latest_slope
            elif latest_slope < 0:
                if current_value > low_warn:
                    warning_limit = low_warn
                    hours_to_warning = (low_warn - current_value) / latest_slope

            if hours_to_warning is not None:
                message = (
                    f"{parameter} {direction} at {latest_slope:.2f}{unit}/hr, "
                    f"estimated {hours_to_warning:.1f} hours to warning limit ({warning_limit:.1f}{unit})"
                )
            else:
                message = f"{parameter} {direction} at {latest_slope:.2f}{unit}/hr"

            z_score = abs(latest_slope) / std_slopes
            confidence = min(0.98, 0.70 + 0.28 * (z_score - slope_threshold_sigma) / max(1.0, z_score))
            confidence = max(0.50, confidence)

            alerts.append(
                TrendAlert(
                    mission_id=mission_id,
                    parameter=parameter,
                    direction=direction,
                    slope_per_hour=latest_slope,
                    hours_to_warning=hours_to_warning,
                    confidence=confidence,
                    message=message,
                )
            )

    return alerts
