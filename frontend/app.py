"""
Smart Grid IDS — NiceGUI Dashboard

Tabs:
  Dashboard  — live metrics cards + alert log (polls every 2 s)
  Simulate   — replay dataset via WebSocket with live feed
  Model      — train / retrain controls + metrics detail
"""

import asyncio
import json
import os
import websockets
import httpx
from nicegui import ui, app

API = os.getenv("API_BASE", "http://localhost:8000")
WS  = API.replace("http", "ws") + "/ws/stream"

SEVERITY_COLOR = {
    "LOW":      "text-green-600",
    "MEDIUM":   "text-yellow-600",
    "HIGH":     "text-orange-600",
    "CRITICAL": "text-red-600",
}
SEVERITY_BG = {
    "LOW":      "bg-green-100",
    "MEDIUM":   "bg-yellow-100",
    "HIGH":     "bg-orange-100",
    "CRITICAL": "bg-red-100",
}


async def get(path: str) -> dict | list:
    async with httpx.AsyncClient(timeout=5.0) as c:
        r = await c.get(f"{API}{path}")
        r.raise_for_status()
        return r.json()


async def post(path: str, data: dict | None = None) -> dict:
    async with httpx.AsyncClient(timeout=30.0) as c:
        r = await c.post(f"{API}{path}", json=data or {})
        r.raise_for_status()
        return r.json()


async def delete(path: str) -> dict:
    async with httpx.AsyncClient(timeout=5.0) as c:
        r = await c.delete(f"{API}{path}")
        r.raise_for_status()
        return r.json()


# ── Shared state ──────────────────────────────────────────────────────────────
_sim_task: asyncio.Task | None = None


# ── Pages ─────────────────────────────────────────────────────────────────────

@ui.page("/")
async def index():
    ui.page_title("Smart Grid IDS")

    with ui.header(elevated=True).classes(
        "items-center justify-between bg-slate-900 text-white px-6 py-3"
    ):
        with ui.row().classes("items-center gap-3"):
            ui.icon("bolt", size="lg")
            ui.label("Smart Grid IDS").classes("text-xl font-semibold")
        ui.label("Ensemble: Isolation Forest · Random Forest · SHAP").classes(
            "text-sm opacity-60"
        )

    with ui.tabs().classes("w-full bg-slate-800 text-white") as tabs:
        tab_dash = ui.tab("Dashboard",  icon="dashboard")
        tab_sim  = ui.tab("Simulation", icon="play_circle")
        tab_model = ui.tab("Model",     icon="model_training")

    with ui.tab_panels(tabs, value=tab_dash).classes("w-full"):
        with ui.tab_panel(tab_dash):
            await _dashboard()
        with ui.tab_panel(tab_sim):
            await _simulation()
        with ui.tab_panel(tab_model):
            await _model_panel()


# ── Dashboard tab ─────────────────────────────────────────────────────────────

async def _dashboard():
    # Metric row
    with ui.row().classes("w-full gap-4 p-4 flex-wrap"):
        lbl_prec  = _kpi_card("Precision",    "--",  "blue-600")
        lbl_rec   = _kpi_card("Recall",       "--",  "green-600")
        lbl_f1    = _kpi_card("F1-Score",     "--",  "purple-600")
        lbl_acc   = _kpi_card("Accuracy",     "--",  "indigo-600")
        lbl_total = _kpi_card("Total Alerts", "0",   "red-600")

    ui.separator()

    # Alert log table
    cols = [
        {"name": "id",             "label": "#",           "field": "id",             "sortable": True, "align": "left"},
        {"name": "timestamp",      "label": "Timestamp",   "field": "timestamp",      "sortable": True, "align": "left"},
        {"name": "severity",       "label": "Severity",    "field": "severity",       "sortable": True, "align": "left"},
        {"name": "ensemble_score", "label": "Score",       "field": "ensemble_score", "sortable": True, "align": "left"},
        {"name": "top_feature",    "label": "Top Feature", "field": "top_feature",    "align": "left"},
        {"name": "packet_rate",    "label": "Pkt Rate",    "field": "packet_rate",    "sortable": True, "align": "left"},
        {"name": "latency_ms",     "label": "Latency ms",  "field": "latency_ms",     "sortable": True, "align": "left"},
    ]

    with ui.card().classes("w-full m-4"):
        ui.label("Recent Alerts").classes("text-lg font-semibold mb-2")
        tbl = ui.table(columns=cols, rows=[], row_key="id").classes("w-full")
        tbl.add_slot("body-cell-severity", """
            <q-td :props="props">
                <q-badge :color="
                    props.value === 'CRITICAL' ? 'red' :
                    props.value === 'HIGH'     ? 'orange' :
                    props.value === 'MEDIUM'   ? 'yellow' : 'green'
                ">{{ props.value }}</q-badge>
            </q-td>
        """)

    async def refresh():
        try:
            m = await get("/metrics")
            if m.get("is_trained"):
                lbl_prec.set_text(f"{m['precision']*100:.1f}%")
                lbl_rec.set_text(f"{m['recall']*100:.1f}%")
                lbl_f1.set_text(f"{m['f1']*100:.1f}%")
                lbl_acc.set_text(f"{m['accuracy']*100:.1f}%")

            cnt = await get("/alerts/count")
            lbl_total.set_text(str(cnt["count"]))

            rows = await get("/alerts?limit=20")
            # Truncate timestamp for display
            for r in rows:
                r["timestamp"] = r["timestamp"][:19].replace("T", " ")
                r["packet_rate"] = f"{r['packet_rate']:.1f}"
                r["latency_ms"]  = f"{r['latency_ms']:.1f}"
            tbl.rows = rows
            tbl.update()
        except Exception:
            pass

    ui.timer(2.0, refresh)
    await refresh()


# ── Simulation tab ────────────────────────────────────────────────────────────

async def _simulation():
    global _sim_task

    ui.label("Replay Dataset via WebSocket").classes("text-lg font-semibold p-4")
    ui.markdown(
        "Streams each row of the dataset (or synthetic data) through the model "
        "and shows results live. Anomalies are persisted to the alert log."
    ).classes("px-4 text-gray-500 text-sm")

    with ui.row().classes("items-center gap-4 p-4"):
        delay = ui.number("Delay between records (ms)", value=300, min=100, max=3000, step=100)
        btn_start = ui.button("▶ Start Simulation", color="positive")
        btn_stop  = ui.button("■ Stop",             color="negative").props("flat")

    # Live feed
    feed_log = ui.log(max_lines=40).classes("w-full h-80 font-mono text-sm m-4")

    async def run_sim():
        feed_log.push("── connecting to WebSocket ──")
        try:
            url = f"{WS}?delay_ms={int(delay.value)}"
            async with websockets.connect(url) as ws:
                async for msg in ws:
                    if _sim_task and _sim_task.cancelled():
                        break
                    data = json.loads(msg)
                    if "error" in data:
                        feed_log.push(f"ERROR: {data['error']}")
                        break
                    if data.get("status") == "stream_complete":
                        feed_log.push("── stream complete ──")
                        break
                    flag = "🚨 ANOMALY" if data["is_anomaly"] else "✅ normal "
                    sev  = data.get("severity", "")
                    feat = data.get("top_feature", "")
                    pps  = data.get("Packet_Transmission_Rate_pps", 0)
                    feed_log.push(
                        f"{flag} [{sev:8}] pps={pps:6.1f}  "
                        f"score={data['ensemble_score']:.2f}  top={feat}"
                    )
        except Exception as e:
            feed_log.push(f"Connection error: {e}")

    def start():
        global _sim_task
        if _sim_task and not _sim_task.done():
            return
        _sim_task = asyncio.ensure_future(run_sim())

    def stop():
        global _sim_task
        if _sim_task:
            _sim_task.cancel()
            feed_log.push("── stopped ──")

    btn_start.on_click(start)
    btn_stop.on_click(stop)


# ── Model tab ─────────────────────────────────────────────────────────────────

async def _model_panel():
    ui.label("Model Controls").classes("text-lg font-semibold p-4")

    status_label = ui.label("Status: checking...").classes("px-4 text-gray-500")
    metrics_grid = ui.grid(columns=4).classes("p-4 gap-4")
    detail_cols  = None  # populated after train

    async def refresh_status():
        try:
            h = await get("/health")
            if h.get("trained"):
                rf_thresh = h.get("rf_threshold") or 0.0
                if_wt = h.get("if_weight") or 0.0
                status_label.set_text(
                    f"✅ Model trained  |  RF threshold: {rf_thresh:.2f}  "
                    f"|  IF weight: {if_wt}"
                )
            else:
                status_label.set_text("⚠️  Model not trained")
        except Exception as e:
            status_label.set_text(f"Backend unreachable: {e}")

    async def do_train():
        train_btn.props("loading")
        train_result.set_text("Training…")
        try:
            r = await post("/train")
            m = r.get("metrics", {})
            train_result.set_text(
                f"✅ Trained on {r['rows_used']} rows ({m.get('note','')})  "
                f"| P={m.get('precision',0)*100:.1f}%  "
                f"R={m.get('recall',0)*100:.1f}%  "
                f"F1={m.get('f1',0)*100:.1f}%  "
                f"Acc={m.get('accuracy',0)*100:.1f}%"
            )
        except Exception as e:
            train_result.set_text(f"Error: {e}")
        finally:
            train_btn.props(remove="loading")
        await refresh_status()

    async def do_clear():
        r = await delete("/alerts/clear")
        ui.notify(f"Cleared {r.get('deleted', 0)} alerts", color="positive")

    with ui.row().classes("gap-4 px-4"):
        train_btn = ui.button("🔁 Train / Retrain", on_click=do_train, color="primary")
        ui.button("🗑 Clear Alert Log", on_click=do_clear, color="negative").props("flat")

    train_result = ui.label("").classes("px-4 mt-2 text-sm font-mono")

    ui.separator().classes("my-4")
    ui.markdown("""
**Ensemble architecture**

| Step | Component | Role |
|------|-----------|------|
| 1 | RobustScaler | Scale all 4 features |
| 2 | IsolationForest (200 trees) | Unsupervised path-length scoring |
| 3 | RandomForestRegressor (200 trees) | Predict packet rate; flag residuals |
| 4 | Threshold (95th percentile) | Calibrate RF outlier cut-off |
| 5 | SHAP TreeExplainer | Per-alert feature attribution |
| 6 | Weighted vote (0.6·IF + 0.4·RF) | Final anomaly / normal decision |
| 7 | Severity scorer | LOW / MEDIUM / HIGH / CRITICAL |
    """).classes("px-4")

    await refresh_status()
    ui.timer(10.0, refresh_status)


# ── Component helpers ─────────────────────────────────────────────────────────

def _kpi_card(title: str, initial: str, color: str):
    """Returns the inner label so callers can call .set_text()."""
    with ui.card().classes("p-4 min-w-36"):
        ui.label(title).classes("text-xs text-gray-500 uppercase tracking-wide")
        lbl = ui.label(initial).classes(f"text-3xl font-bold text-{color} mt-1")
    return lbl


# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ in {"__main__", "__mp_main__"}:
    port = int(os.getenv("NICEGUI_PORT", 8080))
    ui.run(
        title="Smart Grid IDS",
        port=port,
        host="0.0.0.0",
        favicon="⚡",
        dark=False,
        reload=False,
    )
