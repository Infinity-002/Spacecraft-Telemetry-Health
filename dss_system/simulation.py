"""Simulation engine for generating realistic unseen mission (M06) data."""

from dataclasses import dataclass
import pandas as pd
import numpy as np
from dss_system import FEATURE_COLUMNS


@dataclass
class SimulatedMission:
    mission_id: str
    telemetry: pd.DataFrame
    notes: pd.DataFrame
    annotations: pd.DataFrame


class SimulationEngine:
    def __init__(self, nominal_telemetry: pd.DataFrame):
        """Takes M01 telemetry as the nominal baseline."""
        self.nominal = nominal_telemetry.sort_values("timestamp").copy()

    def generate_mission(self, mission_id="M06", num_orbits=8) -> SimulatedMission:
        """Generates complete telemetry + operator notes for a new mission."""
        num_rows = num_orbits * 99
        if len(self.nominal) >= num_rows:
            df = self.nominal.iloc[:num_rows].copy()
        else:
            df = pd.concat([self.nominal] * (num_rows // len(self.nominal) + 1), ignore_index=True).iloc[:num_rows].copy()

        df["mission_id"] = mission_id

        start_time = pd.Timestamp("2026-07-08T00:00:00Z")
        df["timestamp"] = [start_time + pd.Timedelta(minutes=i) for i in range(num_rows)]

        # 1. Apply gradual/progressive fault injections per timestep
        for t in range(num_rows):
            orbit = (t // 99) + 1

            # Orbits 5-8: Gradual battery aging
            if orbit >= 5:
                factor_bat = min(1.0, (orbit - 4) / 4.0)
                if t > 0:
                    delta_soc = df.loc[t, "batt_soc"] - df.loc[t - 1, "batt_soc"]
                    if delta_soc < 0:
                        df.loc[t, "batt_soc"] = df.loc[t - 1, "batt_soc"] + delta_soc * (1.0 - 0.3 * factor_bat)
                if df.loc[t, "batt_current"] < 0:
                    df.loc[t, "batt_voltage"] -= (0.5 + 1.0 * factor_bat)

            # Orbits 7-8: Solar panel degradation
            if orbit >= 7:
                factor_sa = min(1.0, (orbit - 6) / 2.0)
                cap_sa = 12.0 - 2.5 * factor_sa
                df.loc[t, "sa_current"] = min(df.loc[t, "sa_current"], cap_sa)

            # Orbits 6-8: Cooling failure
            if orbit >= 6:
                if t > 0 and df.loc[t, "comm_link_status"] == 1:
                    df.loc[t, "temp_tx"] = df.loc[t - 1, "temp_tx"] + 4.0
                    df.loc[t, "tx_temp"] = df.loc[t, "temp_tx"]
                start_row_orbit_6 = 5 * 99
                drift = 0.5 * (t - start_row_orbit_6)
                df.loc[t, "temp_batt"] += drift
                df.loc[t, "batt_temp"] += drift

            # Orbit 5: Simulate telemetry packet loss/dropout
            if orbit == 5:
                for col in FEATURE_COLUMNS:
                    df.loc[t, col] = np.nan

        # 2. Add realistic Gaussian noise
        NOMINAL_RANGES = {
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
        for param, (low, high) in NOMINAL_RANGES.items():
            if param in df.columns:
                sigma = 0.005 * (high - low)
                noise = np.random.normal(0, sigma, num_rows)
                df[param] = df[param] + noise
 
        # 3. Generate operator notes at 6 standard points per orbit
        note_rows = []
        ann_rows = []
        note_idx = 3001
 
        offsets = [0, 20, 35, 63, 70, 80]
 
        for k in range(1, num_orbits + 1):
            for offset in offsets:
                t_idx = (k - 1) * 99 + offset
                timestamp = df.loc[t_idx, "timestamp"]
                note_id = f"NOTE_{note_idx}"
                note_idx += 1
 
                if k <= 4:
                    if offset == 0:
                        note = f"Orbit {k} start. Sunlit phase. Solar array generating 12.0A. Battery charging. Nominal."
                        sub, con, exp, conf, act, urg = "EPS", "None", "Yes", "High", "None", "Nominal"
                    elif offset == 20:
                        note = "Science payload activated. Bus load increased. OBC cpu load rose. Thermal offsets nominal."
                        sub, con, exp, conf, act, urg = "System", "None", "Yes", "High", "None", "Nominal"
                    elif offset == 35:
                        note = "Science sequence completed. Payload returned to low-power standby. Nominal."
                        sub, con, exp, conf, act, urg = "System", "None", "Yes", "High", "None", "Nominal"
                    elif offset == 63:
                        note = "Eclipse entry. Solar flux at 0. Battery discharging. Expected."
                        sub, con, exp, conf, act, urg = "EPS", "None", "Yes", "High", "None", "Nominal"
                    elif offset == 70:
                        note = "Signal lock with ground station. RX signal strength active. Downlink operating. Nominal."
                        sub, con, exp, conf, act, urg = "TT&C", "None", "Yes", "High", "None", "Nominal"
                    else:
                        note = "LOS. Transmitter offline. RSSI back to noise floor. Nominal."
                        sub, con, exp, conf, act, urg = "TT&C", "None", "Yes", "High", "None", "Nominal"
 
                elif k == 5:
                    if offset == 0:
                        note = "High bit error rate on downlink. Ingesting corrupted frames. Spacecraft status unclear."
                        sub, con, exp, conf, act, urg = "System", "None", "Unknown", "Medium", "Monitor", "Medium"
                    elif offset == 20:
                        note = "Signal lock lost. Telemetry downlink interrupted. Tracking antenna error. Watching."
                        sub, con, exp, conf, act, urg = "TT&C", "None", "Unknown", "Medium", "Monitor", "Medium"
                    elif offset == 35:
                        note = "Bit sync recovered but frame synchronization failing. Telemetry packet loss 100%."
                        sub, con, exp, conf, act, urg = "TT&C", "None", "Unknown", "Medium", "Monitor", "Medium"
                    elif offset == 63:
                        note = "Eclipse entry. Still no telemetry downlink. Spacecraft health status is currently unknown."
                        sub, con, exp, conf, act, urg = "System", "None", "Unknown", "Medium", "Monitor", "Medium"
                    elif offset == 70:
                        note = "Downlink signal re-acquired on backup S-band carrier. Resuming packet decoding."
                        sub, con, exp, conf, act, urg = "TT&C", "None", "Yes", "High", "None", "Nominal"
                    else:
                        note = "LOS. Backup downlink offline. Standard receiver noise floor. Status unconfirmed."
                        sub, con, exp, conf, act, urg = "TT&C", "None", "Unknown", "Medium", "Monitor", "Medium"
 
                else:
                    if offset == 0:
                        note = f"Orbit {k} start. Solar array current capped at 9.5A. Battery soc low."
                        sub, con, exp, conf, act, urg = "EPS", "Central Cooling Pump Failure", "No", "High", "Recommend Engineering Review", "High"
                    elif offset == 20:
                        note = "Science payload active. temp_batt is drifting upward. currently 28C. investigate?"
                        sub, con, exp, conf, act, urg = "EPS", "Central Cooling Pump Failure", "No", "Medium", "Recommend Engineering Review", "High"
                    elif offset == 35:
                        note = "Science completed. CRITICAL: batt temp 47C and climbing exponentially. entering safe mode NOW."
                        sub, con, exp, conf, act, urg = "EPS", "Central Cooling Pump Failure", "No", "High", "Enter safe mode", "Critical"
                    elif offset == 63:
                        note = "Eclipse entry. temp_batt remains high at 42C. cooling loops not keeping up."
                        sub, con, exp, conf, act, urg = "EPS", "Central Cooling Pump Failure", "No", "High", "Recommend Engineering Review", "High"
                    elif offset == 70:
                        note = "Signal lock. temp_tx 58°C and climbing during downlink. cooling loop may have failed."
                        sub, con, exp, conf, act, urg = "TCS", "Central Cooling Pump Failure", "No", "Medium", "Recommend Engineering Review", "High"
                    else:
                        note = "LOS. CRITICAL: temp_tx hit 66°C, executing emergency transmitter shutdown"
                        sub, con, exp, conf, act, urg = "TCS", "Central Cooling Pump Failure", "No", "High", "Disable transmitter", "Critical"
 
                note_rows.append({
                    "note_id": note_id,
                    "mission_id": mission_id,
                    "timestamp": timestamp,
                    "operator_note": note
                })
 
                ann_rows.append({
                    "note_id": note_id,
                    "subsystem": sub,
                    "concern": con,
                    "expected_behaviour": exp,
                    "confidence": conf,
                    "action": act,
                    "urgency": urg
                })
 
        notes_df = pd.DataFrame(note_rows)
        annotations_df = pd.DataFrame(ann_rows)
 
        return SimulatedMission(
            mission_id=mission_id,
            telemetry=df,
            notes=notes_df,
            annotations=annotations_df
        )
 
    def iterate_pass_by_pass(self, mission: SimulatedMission):
        """Yields one pass at a time: (pass_telemetry_df, pass_notes_df)"""
        for orbit_idx in range(len(mission.notes) // 6):
            pass_notes = mission.notes.iloc[orbit_idx * 6 : (orbit_idx + 1) * 6]
            pass_tel = mission.telemetry.iloc[orbit_idx * 99 : (orbit_idx + 1) * 99]
            yield pass_tel, pass_notes
