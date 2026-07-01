"""Run the spacecraft Decision Support System end to end."""

from pathlib import Path
import sys

import numpy as np
from dataclasses import replace
from dss_system.urgency_calibrator import calibrate_urgency

try:
    import pandas as pd
except ModuleNotFoundError as exc:  # pragma: no cover - runtime guidance.
    raise SystemExit("pandas is required to run the DSS orchestrator. Run uv sync, then uv run dss-run.") from exc

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from dss_system import FEATURE_COLUMNS, TEST_MISSIONS
from dss_system.fusion_engine import fuse_evidence
from dss_system.joint_context_model import predict_note_context
from dss_system.reliability_module import build_nominal_stats, score_note_reliability
from dss_system.rule_engine import evaluate_rules
from dss_system.gru_model import (
    load_gru_artifact,
    normalize_errors,
    reconstruction_errors,
    save_gru_artifact,
    train_gru_autoencoder,
    compute_anomaly_pvalue,
)
from dss_system.pass_aggregator import PassSummary, aggregate_all_passes
from dss_system.trend_detector import detect_trends, NOMINAL_WARNING_LIMITS, TrendAlert


ROOT = Path(__file__).resolve().parents[1]
TELEMETRY_PATH = ROOT / "telemetry_simulation" / "telemetry.csv"
NOTES_PATH = ROOT / "flight_logs" / "operator_notes.csv"
ANNOTATIONS_PATH = ROOT / "flight_logs" / "note_annotations.csv"
ARTIFACTS_DIR = ROOT / "artifacts"
GRU_ARTIFACT_PATH = ARTIFACTS_DIR / "gru_autoencoder.pt"
SCENARIO_LOG_PATH = ROOT / "telemetry_simulation" / "scenario_log.csv"


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    telemetry = pd.read_csv(TELEMETRY_PATH, parse_dates=["timestamp"])
    notes = pd.read_csv(NOTES_PATH, parse_dates=["timestamp"])
    missing = [column for column in FEATURE_COLUMNS if column not in telemetry.columns]
    if missing:
        raise ValueError(f"Telemetry is missing required columns: {missing}")
    return telemetry, notes


def train_temporal_model(telemetry: pd.DataFrame, force_retrain: bool = False):
    if GRU_ARTIFACT_PATH.exists() and not force_retrain:
        model, scaler, reference_errors, losses, metadata = load_gru_artifact(GRU_ARTIFACT_PATH)
        if metadata["feature_columns"] == FEATURE_COLUMNS:
            print(f"Loaded saved GRU model: {GRU_ARTIFACT_PATH}")
            return model, scaler, reference_errors, losses

        print("Saved GRU model uses different features; retraining.")

    healthy = telemetry.loc[telemetry["mission_id"] == "M01"].sort_values("timestamp")
    train_values = healthy[FEATURE_COLUMNS].to_numpy(dtype=np.float32)

    model, scaler, losses, val_losses = train_gru_autoencoder(train_values, epochs=30)
    reference_errors = reconstruction_errors(model, scaler, train_values)

    save_gru_artifact(
        GRU_ARTIFACT_PATH,
        model=model,
        scaler=scaler,
        reference_errors=reference_errors,
        losses=losses,
        feature_columns=FEATURE_COLUMNS,
        val_losses=val_losses,
    )

    print(f"Saved GRU model: {GRU_ARTIFACT_PATH}")
    return model, scaler, reference_errors, losses


JOINT_ARTIFACT_PATH = ARTIFACTS_DIR / "joint_context_model.pt"

def train_joint_model(telemetry: pd.DataFrame, force_retrain: bool = False):
    from dss_system.joint_context_model import (
        train_joint_context_model,
        load_joint_records,
        save_joint_artifact,
        load_joint_artifact,
    )
    if JOINT_ARTIFACT_PATH.exists() and not force_retrain:
        try:
            artifacts = load_joint_artifact(JOINT_ARTIFACT_PATH)
            if artifacts.feature_columns == FEATURE_COLUMNS:
                print(f"Loaded saved Joint Context model: {JOINT_ARTIFACT_PATH}")
                return artifacts
        except Exception as e:
            print(f"Failed to load saved Joint Context model ({e}), retraining.")
            
    print("Training Joint Context Model...")
    records = load_joint_records(NOTES_PATH, ANNOTATIONS_PATH, TELEMETRY_PATH)
    artifacts = train_joint_context_model(records, FEATURE_COLUMNS, epochs=25)
    save_joint_artifact(JOINT_ARTIFACT_PATH, artifacts)
    print(f"Saved Joint Context model: {JOINT_ARTIFACT_PATH}")
    return artifacts


def score_mission(telemetry: pd.DataFrame, mission_id: str, model, scaler, reference_errors) -> pd.DataFrame:
    mission = telemetry.loc[telemetry["mission_id"] == mission_id].sort_values("timestamp").copy()
    values = mission[FEATURE_COLUMNS].to_numpy(dtype=np.float32)
    errors = reconstruction_errors(model, scaler, values)
    scores = normalize_errors(errors, reference_errors)
    pvalues = compute_anomaly_pvalue(errors, reference_errors)

    mission["telemetry_score"] = 0.0
    mission["telemetry_pvalue"] = 1.0
    mission.loc[mission.index[9:], "telemetry_score"] = scores
    mission.loc[mission.index[9:], "telemetry_pvalue"] = pvalues
    return mission


def evaluate_notes(
    scored_telemetry: pd.DataFrame,
    notes: pd.DataFrame,
    nominal_stats: dict[str, tuple[float, float]],
    joint_model_artifacts,
) -> list[dict[str, object]]:
    merged = notes.merge(
        scored_telemetry,
        on=["mission_id", "timestamp"],
        how="inner",
        suffixes=("_note", ""),
    ).sort_values(["mission_id", "timestamp"])

    decisions = []
    for _, row in merged.iterrows():
        telemetry_row = {column: float(row[column]) for column in FEATURE_COLUMNS}
        if "temp_rw" in row:
            telemetry_row["temp_rw"] = float(row["temp_rw"])
        rule_result = evaluate_rules(telemetry_row)
        note_context = predict_note_context(str(row["operator_note"]), telemetry_row, joint_model_artifacts)
        calibrated_urgency, urgency_reason = calibrate_urgency(
            note_context.urgency,
            note_context.fault_type,
            float(row["telemetry_pvalue"]),
        )
        note_context = replace(note_context, urgency=calibrated_urgency, concern=calibrated_urgency)
        reliability = score_note_reliability(
            str(row["operator_note"]),
            note_context,
            telemetry_row,
            nominal_stats,
        )
        decision = fuse_evidence(
            rule_result=rule_result,
            telemetry_score=float(row["telemetry_score"]),
            note_context=note_context,
            reliability=reliability,
            telemetry_pvalue=float(row["telemetry_pvalue"]),
        )
        decisions.append(
            {
                "mission_id": row["mission_id"],
                "timestamp": row["timestamp"],
                "note_id": row["note_id"],
                "operator_note": str(row["operator_note"]),
                "subsystem": note_context.subsystem,
                "fault_type": note_context.fault_type,
                "urgency": note_context.urgency,
                "telemetry_score": float(row["telemetry_score"]),
                "telemetry_pvalue": float(row["telemetry_pvalue"]),
                "note_weight": reliability.weight,
                "severity": decision.severity,
                "confidence": decision.confidence,
                "action": decision.recommended_action,
                "explanation": decision.explanation,
                "uncertainty": decision.uncertainty,
                "conflict": decision.conflict,
                "severity_index": decision.severity_index,
            }
        )
    return decisions





def print_dashboard(
    losses: list[float],
    pass_summaries: list[PassSummary],
    trend_alerts: list[TrendAlert] = None
) -> None:
    print("\nSpacecraft DSS Report")
    print("=" * 90)
    if losses:
        print(f"GRU training loss: first={losses[0]:.6f} final={losses[-1]:.6f}")
    print("-" * 90)

    print("\nPass Rollup Summary:")
    print("-" * 90)
    print(f"{'Pass':<12} | {'Mission':<8} | {'Notes':<6} | {'Worst Severity':<16} | {'Avg Conf':<8} | {'Max Uncert':<10} | {'Overrides':<9}")
    print("-" * 90)
    for p in pass_summaries:
        print(f"Pass {p.pass_number:<7} | {p.mission_id:<8} | {p.num_notes:<6} | {p.overall_severity:<16} | {p.overall_confidence:<8.2f} | {p.overall_uncertainty:<10.2f} | {p.num_rule_overrides:<9}")
    print("-" * 90)

    print("\nActive Trend Alerts:")
    print("-" * 90)
    if trend_alerts:
        for alert in trend_alerts:
            print(f"  [{alert.mission_id}] {alert.message} (confidence: {alert.confidence:.2f})")
    else:
        print("  No active trend alerts detected.")
    print("-" * 90)

    print("\nConcerning Pass Details (Non-Nominal):")
    print("=" * 90)
    concerning_count = 0
    for p in pass_summaries:
        if p.overall_severity != "Nominal":
            concerning_count += 1
            print(f"\n> {p.summary_text}")
            if p.trend_alerts:
                print("  Active Trend Alerts in this pass:")
                for alert in p.trend_alerts:
                    print(f"    - {alert.message} (confidence: {alert.confidence:.2f})")
            print("-" * 90)
            for item in p.decisions:
                stamp = item["timestamp"]
                print(
                    f"  {item['mission_id']} {stamp} {item['note_id']} | "
                    f"{item['severity']} ({item['confidence']:.2f}) | "
                    f"S_tel={item['telemetry_score']:.2f} W_note={item['note_weight']:.2f} | "
                    f"{item['subsystem']} | {item['urgency']} | {item['fault_type']}"
                )
                print(f"    action: {item['action']}")
                print(f"    why: {item['explanation']}")
            print("-" * 90)
    if concerning_count == 0:
        print("No concerning passes detected.")


def main() -> None:
    telemetry, notes = load_inputs()
    model, scaler, reference_errors, losses = train_temporal_model(telemetry)
    nominal_stats = build_nominal_stats(telemetry.loc[telemetry["mission_id"] == "M01"])

    scored_frames = [
        score_mission(telemetry, mission_id, model, scaler, reference_errors)
        for mission_id in ["M01", *TEST_MISSIONS]
    ]
    scored_telemetry = pd.concat(scored_frames, ignore_index=True)

    all_trend_alerts = []
    for mission_id in TEST_MISSIONS:
        alerts = detect_trends(telemetry, mission_id, NOMINAL_WARNING_LIMITS)
        all_trend_alerts.extend(alerts)

    selected_notes = notes.loc[notes["mission_id"].isin(["M01", *TEST_MISSIONS])]
    joint_model_artifacts = train_joint_model(telemetry)
    decisions = evaluate_notes(scored_telemetry, selected_notes, nominal_stats, joint_model_artifacts)

    scenario_log = pd.read_csv(SCENARIO_LOG_PATH, parse_dates=["timestamp"])

    pass_summaries = aggregate_all_passes(
        decisions,
        scenario_log=scenario_log,
        trend_alerts=all_trend_alerts,
    )
    print_dashboard(losses, pass_summaries, trend_alerts=all_trend_alerts)


if __name__ == "__main__":
    main()
