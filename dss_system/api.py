"""FastAPI server for the spacecraft Decision Support System."""

import asyncio
from datetime import datetime
import json
from pathlib import Path
from typing import Optional, List, Dict

import numpy as np
import pandas as pd
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from dss_system import FEATURE_COLUMNS
from dss_system.fusion_engine import Decision
from dss_system.pass_aggregator import PassSummary
from dss_system.trend_detector import TrendAlert
from dss_system.joint_context_model import predict_note_context


app = FastAPI(title="Spacecraft DSS API")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ROOT = Path(__file__).resolve().parents[1]
TELEMETRY_PATH = ROOT / "telemetry_simulation" / "telemetry.csv"
NOTES_PATH = ROOT / "flight_logs" / "operator_notes.csv"
ANNOTATIONS_PATH = ROOT / "flight_logs" / "note_annotations.csv"
OVERRIDES_PATH = ROOT / "artifacts" / "overrides.json"

# In-memory result cache
CACHE: Dict[str, any] = {
    "missions": ["M01", "M02", "M03", "M04", "M05"],
    "passes": {},       # mission_id -> list of PassSummary dicts
    "telemetry": {},    # mission_id -> dict
    "trends": {},       # mission_id -> list of TrendAlert dicts
    # Shared ML/Rule models
    "model": None,
    "scaler": None,
    "reference_errors": None,
    "nominal_stats": None,
    "joint_model_artifacts": None,
    "raw_telemetry": None,  # M01 telemetry for SimulationEngine
}


def decision_to_dict(d: Decision) -> dict:
    return {
        "severity": d.severity,
        "confidence": float(d.confidence),
        "recommended_action": d.recommended_action,
        "explanation": d.explanation,
        "severity_index": float(d.severity_index),
        "uncertainty": float(d.uncertainty),
        "conflict": float(d.conflict),
    }


def trend_alert_to_dict(t: TrendAlert) -> dict:
    return {
        "mission_id": t.mission_id,
        "parameter": t.parameter,
        "direction": t.direction,
        "slope_per_hour": float(t.slope_per_hour),
        "hours_to_warning": float(t.hours_to_warning) if t.hours_to_warning is not None else None,
        "confidence": float(t.confidence),
        "message": t.message,
    }


def pass_summary_to_dict(p: PassSummary) -> dict:
    return {
        "mission_id": p.mission_id,
        "pass_number": int(p.pass_number),
        "start_time": p.start_time.isoformat(),
        "end_time": p.end_time.isoformat(),
        "overall_severity": p.overall_severity,
        "overall_confidence": float(p.overall_confidence),
        "overall_uncertainty": float(p.overall_uncertainty),
        "flagged_subsystems": p.flagged_subsystems,
        "num_notes": int(p.num_notes),
        "num_rule_overrides": int(p.num_rule_overrides),
        "worst_decision": decision_to_dict(p.worst_decision),
        "decisions": p.decisions,
        "summary_text": p.summary_text,
        "trend_alerts": [trend_alert_to_dict(t) for t in p.trend_alerts],
    }


@app.on_event("startup")
async def startup_event():
    # Load inputs
    telemetry = pd.read_csv(TELEMETRY_PATH, parse_dates=["timestamp"])
    notes = pd.read_csv(NOTES_PATH, parse_dates=["timestamp"])

    from dss_system.run_dss import train_temporal_model, score_mission, evaluate_notes, train_joint_model
    from dss_system.reliability_module import build_nominal_stats
    from dss_system.pass_aggregator import aggregate_all_passes
    from dss_system.trend_detector import detect_trends, NOMINAL_WARNING_LIMITS

    # Train/load GRU and Joint Context components
    model, scaler, reference_errors, losses = train_temporal_model(telemetry)
    nominal_stats = build_nominal_stats(telemetry.loc[telemetry["mission_id"] == "M01"])
    joint_model_artifacts = train_joint_model(telemetry)

    # Store shared components
    CACHE["model"] = model
    CACHE["scaler"] = scaler
    CACHE["reference_errors"] = reference_errors
    CACHE["nominal_stats"] = nominal_stats
    CACHE["joint_model_artifacts"] = joint_model_artifacts
    CACHE["raw_telemetry"] = telemetry.loc[telemetry["mission_id"] == "M01"].copy()

    # Precompute and cache results for M01-M05
    scored_frames = []
    for mission_id in ["M01", "M02", "M03", "M04", "M05"]:
        scored = score_mission(telemetry, mission_id, model, scaler, reference_errors)
        scored_frames.append(scored)

        # Cache telemetry
        param_cols = {}
        for col in FEATURE_COLUMNS:
            param_cols[col] = scored[col].tolist()

        param_cols["telemetry_score"] = scored["telemetry_score"].tolist()
        param_cols["telemetry_pvalue"] = scored["telemetry_pvalue"].tolist()

        CACHE["telemetry"][mission_id] = {
            "timestamps": [t.isoformat() for t in pd.to_datetime(scored["timestamp"])],
            "columns": param_cols,
        }

        # Cache trends
        trends = detect_trends(telemetry, mission_id, NOMINAL_WARNING_LIMITS)
        CACHE["trends"][mission_id] = [trend_alert_to_dict(t) for t in trends]

    scored_telemetry = pd.concat(scored_frames, ignore_index=True)
    selected_notes = notes.loc[notes["mission_id"].isin(["M01", "M02", "M03", "M04", "M05"])]
    decisions = evaluate_notes(scored_telemetry, selected_notes, nominal_stats, joint_model_artifacts)

    # Aggregate passes with overlapping trend alerts
    all_trend_alerts = []
    for m_id in ["M01", "M02", "M03", "M04", "M05"]:
        m_trends = CACHE["trends"][m_id]
        all_trend_alerts.extend([
            TrendAlert(
                mission_id=t["mission_id"],
                parameter=t["parameter"],
                direction=t["direction"],
                slope_per_hour=t["slope_per_hour"],
                hours_to_warning=t["hours_to_warning"],
                confidence=t["confidence"],
                message=t["message"]
            ) for t in m_trends
        ])

    scenario_log = pd.read_csv(ROOT / "telemetry_simulation" / "scenario_log.csv", parse_dates=["timestamp"])
    pass_summaries = aggregate_all_passes(decisions, scenario_log=scenario_log, trend_alerts=all_trend_alerts)

    # Initialize passes cache
    for m_id in ["M01", "M02", "M03", "M04", "M05"]:
        CACHE["passes"][m_id] = []
    for p in pass_summaries:
        CACHE["passes"][p.mission_id].append(pass_summary_to_dict(p))


@app.get("/api/missions")
def get_missions():
    return CACHE["missions"]


@app.get("/api/passes")
def get_passes(mission_id: Optional[str] = None):
    if mission_id:
        return CACHE["passes"].get(mission_id, [])
    # Return all passes across all missions
    all_passes = []
    for m_id in CACHE["missions"]:
        all_passes.extend(CACHE["passes"].get(m_id, []))
    return all_passes


@app.get("/api/telemetry/{mission_id}")
def get_telemetry(mission_id: str):
    if mission_id not in CACHE["telemetry"]:
        return {"timestamps": [], "columns": {}}
    return CACHE["telemetry"][mission_id]


@app.get("/api/trends/{mission_id}")
def get_trends(mission_id: str):
    return CACHE["trends"].get(mission_id, [])


class OverrideBody(BaseModel):
    note_id: str
    operator_severity: str
    operator_comment: str


@app.post("/api/override")
def post_override(body: OverrideBody):
    OVERRIDES_PATH.parent.mkdir(parents=True, exist_ok=True)
    overrides = []
    if OVERRIDES_PATH.exists():
        try:
            with open(OVERRIDES_PATH, "r", encoding="utf-8") as f:
                overrides = json.load(f)
        except Exception:
            overrides = []

    record = {
        "note_id": body.note_id,
        "operator_severity": body.operator_severity,
        "operator_comment": body.operator_comment,
        "timestamp": datetime.utcnow().isoformat(),
    }
    overrides.append(record)
    with open(OVERRIDES_PATH, "w", encoding="utf-8") as f:
        json.dump(overrides, f, indent=2)
    return {"status": "ok"}


@app.get("/api/overrides")
def get_overrides():
    if not OVERRIDES_PATH.exists():
        return []
    try:
        with open(OVERRIDES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


@app.get("/api/simulate/start")
def start_simulation(speed: float = Query(default=5.0, ge=0.1)):
    from dss_system.simulation import SimulationEngine
    from dss_system.gru_model import reconstruction_errors, normalize_errors, compute_anomaly_pvalue
    from dss_system.rule_engine import evaluate_rules
    from dss_system.joint_context_model import predict_note_context
    from dss_system.reliability_module import score_note_reliability
    from dss_system.fusion_engine import fuse_evidence
    from dss_system.pass_aggregator import aggregate_pass
    from dss_system.trend_detector import detect_trends, NOMINAL_WARNING_LIMITS

    async def event_generator():
        # Setup Simulation
        nominal_tel = CACHE["raw_telemetry"][CACHE["raw_telemetry"]["mission_id"] == "M01"]
        engine = SimulationEngine(nominal_tel)
        mission = engine.generate_mission("M06", num_orbits=8)

        prev_pass_tel = None
        accumulated_telemetry = pd.DataFrame()

        orbit_idx = 0
        for pass_tel, pass_notes in engine.iterate_pass_by_pass(mission):
            orbit_idx += 1

            # Score telemetry through GRU
            if prev_pass_tel is None:
                # First pass, no padding history
                values = pass_tel[FEATURE_COLUMNS].to_numpy(dtype=np.float32)
                if np.isnan(values).any():
                    pass_scores = np.full(99, np.nan)
                    pass_pvalues = np.full(99, np.nan)
                else:
                    errors = reconstruction_errors(CACHE["model"], CACHE["scaler"], values)
                    scores = normalize_errors(errors, CACHE["reference_errors"])
                    pvalues = compute_anomaly_pvalue(errors, CACHE["reference_errors"])

                    # Pad front for the first 9 rows
                    pass_scores = np.zeros(99)
                    pass_pvalues = np.ones(99)
                    pass_scores[9:] = scores
                    pass_pvalues[9:] = pvalues
            else:
                # Prepend last 9 rows of the previous pass's telemetry
                context_tel = pd.concat([prev_pass_tel.iloc[-9:], pass_tel], ignore_index=True)
                context_values = context_tel[FEATURE_COLUMNS].to_numpy(dtype=np.float32)
                if np.isnan(context_values).any():
                    pass_scores = np.full(99, np.nan)
                    pass_pvalues = np.full(99, np.nan)
                else:
                    errors = reconstruction_errors(CACHE["model"], CACHE["scaler"], context_values)
                    pass_scores = normalize_errors(errors, CACHE["reference_errors"])
                    pass_pvalues = compute_anomaly_pvalue(errors, CACHE["reference_errors"])

            # Scored telemetry DataFrame
            pass_tel_scored = pass_tel.copy()
            pass_tel_scored["telemetry_score"] = pass_scores
            pass_tel_scored["telemetry_pvalue"] = pass_pvalues

            # Decisions scoring pipeline
            merged = pass_notes.merge(pass_tel_scored, on=["mission_id", "timestamp"], how="inner")

            pass_decisions = []
            for _, row in merged.iterrows():
                telemetry_row = {column: float(row[column]) for column in FEATURE_COLUMNS}
                if "temp_rw" in row:
                    telemetry_row["temp_rw"] = float(row["temp_rw"])
                rule_result = evaluate_rules(telemetry_row)
                note_context = predict_note_context(str(row["operator_note"]), telemetry_row, CACHE["joint_model_artifacts"])
                reliability = score_note_reliability(
                    str(row["operator_note"]),
                    note_context,
                    telemetry_row,
                    CACHE["nominal_stats"],
                )
                decision = fuse_evidence(
                    rule_result=rule_result,
                    telemetry_score=float(row["telemetry_score"]) if not pd.isna(row["telemetry_score"]) else None,
                    note_context=note_context,
                    reliability=reliability,
                    telemetry_pvalue=float(row["telemetry_pvalue"]) if not pd.isna(row["telemetry_pvalue"]) else None,
                )
                pass_decisions.append({
                    "mission_id": row["mission_id"],
                    "timestamp": row["timestamp"].isoformat(),
                    "note_id": row["note_id"],
                    "operator_note": str(row["operator_note"]),
                    "subsystem": note_context.subsystem,
                    "fault_type": note_context.fault_type,
                    "urgency": note_context.urgency,
                    "telemetry_score": float(row["telemetry_score"]) if not pd.isna(row["telemetry_score"]) else None,
                    "telemetry_pvalue": float(row["telemetry_pvalue"]) if not pd.isna(row["telemetry_pvalue"]) else None,
                    "note_weight": reliability.weight,
                    "severity": decision.severity,
                    "confidence": decision.confidence,
                    "action": decision.recommended_action,
                    "explanation": decision.explanation,
                    "uncertainty": decision.uncertainty,
                    "conflict": decision.conflict,
                    "severity_index": decision.severity_index,
                })

            # Accumulate telemetry
            accumulated_telemetry = pd.concat([accumulated_telemetry, pass_tel_scored], ignore_index=True)

            # Detect trends up to the current pass
            current_trends = detect_trends(accumulated_telemetry, "M06", NOMINAL_WARNING_LIMITS)

            # Pass aggregator overlap check
            t_max = pd.to_datetime(pass_decisions[-1]["timestamp"]).to_pydatetime()
            trend_start = t_max - pd.Timedelta(hours=2.0)
            overlapping_trends = [
                alert for alert in current_trends
                if pd.to_datetime(pass_decisions[-1]["timestamp"]).to_pydatetime() >= trend_start
            ]

            summary = aggregate_pass(pass_decisions, pass_number=orbit_idx, trend_alerts=overlapping_trends)
            summary_dict = pass_summary_to_dict(summary)

            # 1. Send Pass rollup summary event
            yield {
                "event": "pass",
                "data": json.dumps(summary_dict)
            }

            # 2. Send Telemetry event
            tel_columns = {col: pass_tel_scored[col].tolist() for col in FEATURE_COLUMNS}
            tel_columns["telemetry_score"] = pass_tel_scored["telemetry_score"].tolist()
            tel_columns["telemetry_pvalue"] = pass_tel_scored["telemetry_pvalue"].tolist()

            tel_data = {
                "mission_id": "M06",
                "timestamps": [t.isoformat() for t in pd.to_datetime(pass_tel_scored["timestamp"])],
                "columns": tel_columns,
            }
            yield {
                "event": "telemetry",
                "data": json.dumps(tel_data)
            }

            # Prepare for next pass
            prev_pass_tel = pass_tel

            # Sleep: one 99-min orbit streams over 99 / speed seconds
            sleep_time = 99.0 / speed
            try:
                await asyncio.sleep(sleep_time)
            except asyncio.CancelledError:
                # Client disconnected, stop generator
                break

        # Send final completion event
        yield {
            "event": "complete",
            "data": json.dumps({
                "mission_id": "M06",
                "total_passes": orbit_idx,
                "summary": f"Real-time simulation completed. Total passes streamed: {orbit_idx}."
            })
        }

    return EventSourceResponse(event_generator())


# Serve frontend static assets in production if they are built
FRONTEND_DIR = ROOT / "frontend" / "dist"
if FRONTEND_DIR.exists():
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="static")


def serve():
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("dss_system.api:app", host="0.0.0.0", port=port, reload=False)
