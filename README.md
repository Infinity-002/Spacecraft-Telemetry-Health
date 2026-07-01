# Context-Aware Spacecraft Telemetry and Note Decision Support System (DSS)

A safety-first, multi-modal prototype designed to support ground operators under pressure. The system fuses continuous spacecraft sensor telemetry with qualitative operator log notes, deterministic safety rules, and model uncertainty bounds to produce unified health recommendations.

---

## 🛰️ Project Overview

During a low Earth orbit (LEO) ground station pass, a ground operator is flooded with high-dimensional telemetry over a very short visibility window (typically 8 to 12 minutes). At the same time, operators must write and review qualitative log notes. 

Existing ground segment consoles excel at displaying telemetry but fail to reason over telemetry and notes together. Operators must manually cross-reference notes and sensor trends in their heads. 

This **Decision Support System (DSS)** automates that joint reasoning. It processes power, thermal, comms, computer, and attitude subsystems, and translates telemetry and operator logs into a single, explainable health recommendation: **Nominal**, **Monitor**, **Investigate**, or **Immediate Action**.

---

## ⚙️ Core Architecture

The DSS utilizes a four-layer processing pipeline to evaluate spacecraft state:

1. **GRU Telemetry Anomaly Model**: A Gated Recurrent Unit (GRU) sequence autoencoder trained on healthy baseline data (Mission M01). It maps 10-minute sliding windows of 26 parameters to a hybrid sequence plus max-feature reconstruction error, converted to conformal-style $p$-values.
2. **Joint Telemetry-Note Context Model**: A dual-branch PyTorch Multi-Layer Perceptron (MLP) that embeds operator logs alongside a snapshot of the telemetry to classify note urgency and expected spacecraft behavior.
3. **Safety Rule Engine**: A deterministic flight software interlock. If any critical sensor threshold is breached, it immediately overrides all statistical ML models to force a safety recommendation.
4. **Dempster-Shafer Evidence Fusion**: Fuses evidence masses from telemetry p-values, note context, and rules. It propagates epistemic ignorance during telemetry dropouts and measures conflict ($K$) between human notes and sensor readings.

---

## 🚀 How to Run the Project

### Prerequisites
* **Python**: Version `3.10` or higher
* **Bun**: Version `1.0` or higher (or Node.js >= 20.19 with `npm`)
* **Package Manager**: [uv](https://github.com/astral-sh/uv) (for Python) and [Bun](https://bun.sh/) (for frontend)

---

### Step 1: Start the Backend API Server
1. Synchronize the Python environment and download dependencies:
   ```bash
   uv sync
   ```
2. Launch the backend API server. This trains the models (if no checkpoints exist in `artifacts/`) and starts the server on port `8000`:
   ```bash
   uv run dss-serve
   ```
   *Alternatively, run in module form:*
   ```bash
   uv run python -m dss_system.api
   ```

---

### Step 2: Start the Frontend Console
1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   bun install
   ```
3. Start the Vite development server:
   ```bash
   bun dev
   ```
4. Open the console HUD in your browser at `http://localhost:5173`.

---

### Step 3: Run the Live Simulation (M06)
1. On the frontend dashboard, click **"Start Simulation"**.
2. The simulation streams exactly **8 orbits** sequentially:
   * **Orbits 1-4 (Nominal)**: Spacecraft functions nominally; sensor readings and logs agree.
   * **Orbit 5 (Telemetry Dropout)**: Complete packet loss. Telemetry is flatlined. Fused uncertainty spikes to **46%**.
   * **Orbits 6-8 (Thermal & Voltage Emergencies)**: Subsystem temperatures exceed 65.0°C and battery voltage drops below 31.2V. The Rule Engine overrides the neural networks to force **Immediate Action (Safe Mode)** recommendations.

---

## 📊 Offline Pipeline Evaluation
To run the offline evaluation pipeline which trains the models, scores orbits, and prints an analytical report on console:
```bash
uv run dss-run
```
*Alternatively, run in module form:*
```bash
uv run python -m dss_system.run_dss
```
