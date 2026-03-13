"""Maintenance Management Application.

A Dash-based web application that provides:
1. Location-bound QR code generation for equipment/assets.
2. A maintenance sheet that engineers fill after scanning the QR code.
3. Abnormality detection with popup alerts and admin notifications.

Run with::

    python maintenance_app.py
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dash import Dash, Input, Output, State, dcc, html
from dash.dependencies import ALL

from utils.notifications import build_alert_message, log_notification
from utils.qr_generator import generate_qr_code, verify_location

# ---------------------------------------------------------------------------
# Data persistence helpers
# ---------------------------------------------------------------------------
DATA_DIR = Path(__file__).resolve().parent / "data"


def _load_records():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / "maintenance_records.json"
    if path.exists():
        with open(path, "r") as fh:
            try:
                return json.load(fh)
            except json.JSONDecodeError:
                return []
    return []


def _save_record(record):
    records = _load_records()
    records.append(record)
    with open(DATA_DIR / "maintenance_records.json", "w") as fh:
        json.dump(records, fh, indent=2)


def _load_notifications():
    path = DATA_DIR / "notifications.json"
    if path.exists():
        with open(path, "r") as fh:
            try:
                return json.load(fh)
            except json.JSONDecodeError:
                return []
    return []


# ---------------------------------------------------------------------------
# Maintenance checklist items (configurable)
# ---------------------------------------------------------------------------
CHECKLIST_ITEMS = [
    "Electrical connections",
    "Vibration levels",
    "Temperature readings",
    "Lubrication status",
    "Belt / chain tension",
    "Safety guards in place",
    "Leakage check",
    "Noise levels",
    "Control panel indicators",
    "Overall cleanliness",
]

# ---------------------------------------------------------------------------
# App initialisation
# ---------------------------------------------------------------------------
app = Dash(
    __name__,
    suppress_callback_exceptions=True,
    title="Maintenance Management",
)

# ---------------------------------------------------------------------------
# Layout — all pages are rendered up-front and toggled via display style
# ---------------------------------------------------------------------------
app.layout = html.Div([
    dcc.Location(id="url", refresh=False),

    # Global stores
    dcc.Store(id="store-qr-lat"),
    dcc.Store(id="store-qr-lng"),
    dcc.Store(id="store-qr-radius"),
    dcc.Store(id="store-equipment-id"),
    dcc.Store(id="store-user-lat"),
    dcc.Store(id="store-user-lng"),
    dcc.Store(id="store-location-verified", data=False),

    # Abnormality popup
    dcc.ConfirmDialog(id="abnormality-popup", message=""),

    # ---- Navbar ----
    html.Div(className="app-header", children=[
        html.H1("\U0001f527 Maintenance Management"),
        html.Div(className="nav-links", children=[
            dcc.Link("Generate QR", href="/"),
            dcc.Link("Maintenance Form", href="/maintenance"),
            dcc.Link("Admin Dashboard", href="/admin"),
        ]),
    ]),

    # ---- Page: QR Generator ----
    html.Div(id="page-qr", className="page-container", children=[
        html.Div(className="card", children=[
            html.H2("Generate Location-Bound QR Code"),
            html.P(
                "Create a QR code for a piece of equipment. "
                "The QR can only be used within the specified radius "
                "of the given GPS coordinates."
            ),
            html.Div(className="form-group", children=[
                html.Label("Equipment / Asset ID"),
                dcc.Input(id="qr-equipment-id", type="text",
                          placeholder="e.g. PUMP-A-101"),
            ]),
            html.Div(className="form-group", children=[
                html.Label("Latitude"),
                dcc.Input(id="qr-latitude", type="number",
                          placeholder="e.g. 28.6139"),
            ]),
            html.Div(className="form-group", children=[
                html.Label("Longitude"),
                dcc.Input(id="qr-longitude", type="number",
                          placeholder="e.g. 77.2090"),
            ]),
            html.Div(className="form-group", children=[
                html.Label("Allowed Radius (metres)"),
                dcc.Input(id="qr-radius", type="number",
                          value=100, min=10, max=5000),
            ]),
            html.Button("Generate QR Code", id="btn-generate-qr",
                        className="btn-primary", n_clicks=0),
            html.Div(id="qr-output"),
        ]),
    ]),

    # ---- Page: Maintenance Form ----
    html.Div(id="page-maintenance", className="page-container", children=[
        # Location status banner
        html.Div(id="location-status"),
        # Maintenance form (shown only after location verification)
        html.Div(id="maintenance-form-container",
                 style={"display": "none"}, children=[
            html.Div(className="card", children=[
                html.H2(id="form-title", children="Maintenance Sheet"),
                html.Div(className="form-group", children=[
                    html.Label("Engineer Name"),
                    dcc.Input(id="engineer-name", type="text",
                              placeholder="Your full name"),
                ]),
                html.Div(className="form-group", children=[
                    html.Label("Date"),
                    dcc.DatePickerSingle(
                        id="maintenance-date",
                        date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    ),
                ]),
                # Checklist items
                html.H3("Checklist"),
                html.Table(className="checklist-table", children=[
                    html.Thead(html.Tr([
                        html.Th("Item"), html.Th("Status"),
                    ])),
                    html.Tbody([
                        html.Tr([
                            html.Td(item),
                            html.Td(dcc.Dropdown(
                                id={"type": "checklist-status", "index": idx},
                                options=[
                                    {"label": "OK", "value": "OK"},
                                    {"label": "Abnormal", "value": "Abnormal"},
                                    {"label": "N/A", "value": "N/A"},
                                ],
                                value="OK",
                                clearable=False,
                                style={"width": "140px"},
                            )),
                        ])
                        for idx, item in enumerate(CHECKLIST_ITEMS)
                    ]),
                ]),
                html.Div(className="form-group",
                         style={"marginTop": "16px"}, children=[
                    html.Label("Observations / Remarks"),
                    dcc.Textarea(
                        id="observations",
                        placeholder="Describe any observations or "
                                    "abnormalities in detail \u2026",
                    ),
                ]),
                html.Button("Submit Maintenance Report",
                            id="btn-submit-maintenance",
                            className="btn-primary", n_clicks=0),
                html.Div(id="submit-result"),
            ]),
        ]),
    ]),

    # ---- Page: Admin Dashboard ----
    html.Div(id="page-admin", className="page-container", children=[
        html.Div(className="card", children=[
            html.H2("\u26a0\ufe0f Abnormality Alerts"),
            html.P(
                "Below are the alerts triggered when engineers "
                "report abnormalities during maintenance checks."
            ),
            html.Button("Refresh", id="btn-refresh-alerts",
                        className="btn-primary", n_clicks=0),
            html.Div(id="alerts-list", style={"marginTop": "16px"}),
        ]),
        html.Div(className="card", children=[
            html.H2("\U0001f4cb Recent Maintenance Records"),
            html.Button("Refresh", id="btn-refresh-records",
                        className="btn-primary", n_clicks=0),
            html.Div(id="records-list", style={"marginTop": "16px"}),
        ]),
    ]),
])

# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

# ---- Routing: show/hide pages ----
@app.callback(
    Output("page-qr", "style"),
    Output("page-maintenance", "style"),
    Output("page-admin", "style"),
    Input("url", "pathname"),
)
def route_pages(pathname):
    hide = {"display": "none"}
    show = {}
    if pathname == "/maintenance":
        return hide, show, hide
    if pathname == "/admin":
        return hide, hide, show
    return show, hide, hide


# ---- QR Generation ----
@app.callback(
    Output("qr-output", "children"),
    Input("btn-generate-qr", "n_clicks"),
    State("qr-equipment-id", "value"),
    State("qr-latitude", "value"),
    State("qr-longitude", "value"),
    State("qr-radius", "value"),
    prevent_initial_call=True,
)
def generate_qr(n_clicks, equipment_id, lat, lng, radius):
    if not all([equipment_id, lat, lng, radius]):
        return html.Div("Please fill in all fields.",
                        className="alert-banner alert-warning")

    try:
        lat, lng, radius = float(lat), float(lng), int(radius)
    except (ValueError, TypeError):
        return html.Div(
            "Invalid numeric values for latitude, longitude or radius.",
            className="alert-banner alert-danger",
        )

    base_url = os.environ.get("APP_BASE_URL", "http://localhost:8050")
    qr_url, qr_base64 = generate_qr_code(
        base_url, equipment_id, lat, lng, radius
    )

    return html.Div(className="qr-display", children=[
        html.Img(src=qr_base64, alt="QR Code"),
        html.P(f"Equipment: {equipment_id}"),
        html.P(f"Location: ({lat}, {lng}) \u2014 radius {radius} m"),
        html.P(
            [html.Strong("URL: "), html.Code(qr_url)],
            style={"wordBreak": "break-all", "fontSize": "0.85rem"},
        ),
        html.Div(
            "\u2705 QR code generated! Print and place at the equipment location.",
            className="alert-banner alert-success",
        ),
    ])


# ---- Maintenance: parse URL query params ----
@app.callback(
    Output("store-qr-lat", "data"),
    Output("store-qr-lng", "data"),
    Output("store-qr-radius", "data"),
    Output("store-equipment-id", "data"),
    Input("url", "search"),
)
def parse_query_params(search):
    import urllib.parse as _up
    params = _up.parse_qs((search or "").lstrip("?"))
    return (
        params.get("lat", [None])[0],
        params.get("lng", [None])[0],
        params.get("radius", [None])[0],
        params.get("equipment_id", [None])[0],
    )


# Client-side callback to request browser geolocation
app.clientside_callback(
    """
    function(pathname) {
        if (pathname !== '/maintenance') return [null, null];
        if (!navigator.geolocation) return [null, null];
        return new Promise(function(resolve) {
            navigator.geolocation.getCurrentPosition(
                function(pos) {
                    resolve([pos.coords.latitude, pos.coords.longitude]);
                },
                function() {
                    resolve([null, null]);
                },
                {enableHighAccuracy: true, timeout: 10000}
            );
        });
    }
    """,
    Output("store-user-lat", "data"),
    Output("store-user-lng", "data"),
    Input("url", "pathname"),
)


# ---- Maintenance: verify location and show/hide form ----
@app.callback(
    Output("location-status", "children"),
    Output("maintenance-form-container", "style"),
    Output("store-location-verified", "data"),
    Output("form-title", "children"),
    Input("store-user-lat", "data"),
    Input("store-user-lng", "data"),
    Input("store-qr-lat", "data"),
    Input("store-qr-lng", "data"),
    Input("store-qr-radius", "data"),
    Input("store-equipment-id", "data"),
)
def verify_and_show_form(
    user_lat, user_lng, qr_lat, qr_lng, qr_radius, equipment_id
):
    # No QR params -> generic message
    if not all([qr_lat, qr_lng, qr_radius, equipment_id]):
        return (
            html.Div(
                "\u2139\ufe0f  Scan a location-bound QR code to open the "
                "maintenance sheet.",
                className="alert-banner alert-info",
            ),
            {"display": "none"},
            False,
            "Maintenance Sheet",
        )

    # Waiting for geolocation
    if user_lat is None or user_lng is None:
        return (
            html.Div(
                "\U0001f4cd Requesting your location \u2026 please allow "
                "location access in your browser.",
                className="alert-banner alert-warning",
            ),
            {"display": "none"},
            False,
            "Maintenance Sheet",
        )

    try:
        qr_lat_f = float(qr_lat)
        qr_lng_f = float(qr_lng)
        radius_m = int(qr_radius)
    except (ValueError, TypeError):
        return (
            html.Div("\u274c Invalid QR parameters.",
                     className="alert-banner alert-danger"),
            {"display": "none"},
            False,
            "Maintenance Sheet",
        )

    is_ok, distance = verify_location(
        user_lat, user_lng, qr_lat_f, qr_lng_f, radius_m
    )

    if is_ok:
        return (
            html.Div(
                f"\u2705 Location verified \u2014 you are {distance} m from "
                f"the equipment (within {radius_m} m radius).",
                className="alert-banner alert-success",
            ),
            {"display": "block"},
            True,
            f"Maintenance Sheet \u2014 {equipment_id}",
        )

    return (
        html.Div(
            f"\u274c Access denied \u2014 you are {distance} m away from the "
            f"equipment location (allowed radius: {radius_m} m). "
            "Please go to the equipment location and scan again.",
            className="alert-banner alert-danger",
        ),
        {"display": "none"},
        False,
        "Maintenance Sheet",
    )


# ---- Maintenance: submit report ----
@app.callback(
    Output("submit-result", "children"),
    Output("abnormality-popup", "displayed"),
    Output("abnormality-popup", "message"),
    Input("btn-submit-maintenance", "n_clicks"),
    State("store-equipment-id", "data"),
    State("engineer-name", "value"),
    State("maintenance-date", "date"),
    State({"type": "checklist-status", "index": ALL}, "value"),
    State("observations", "value"),
    State("store-location-verified", "data"),
    prevent_initial_call=True,
)
def submit_maintenance(
    n_clicks, equipment_id, engineer_name, maint_date, statuses,
    observations, location_verified,
):
    if not location_verified:
        return (
            html.Div("\u274c Location not verified. Cannot submit.",
                     className="alert-banner alert-danger"),
            False, "",
        )

    if not engineer_name:
        return (
            html.Div("Please enter your name.",
                     className="alert-banner alert-warning"),
            False, "",
        )

    # Build checklist dict
    checklist = {
        item: status
        for item, status in zip(CHECKLIST_ITEMS, statuses)
    }

    # Detect abnormalities
    abnormal_items = [
        item for item, status in checklist.items() if status == "Abnormal"
    ]
    has_abnormality = len(abnormal_items) > 0

    # Persist record
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "equipment_id": equipment_id or "Unknown",
        "engineer_name": engineer_name,
        "date": maint_date,
        "checklist": checklist,
        "observations": observations or "",
        "has_abnormality": has_abnormality,
        "abnormal_items": abnormal_items,
    }
    _save_record(record)

    # If abnormality found -> notify admin
    popup_msg = ""
    if has_abnormality:
        details = (
            f"Abnormal items: {', '.join(abnormal_items)}. "
            f"Observations: {observations or 'N/A'}"
        )
        log_notification(
            equipment_id or "Unknown", engineer_name, details,
        )
        popup_msg = build_alert_message(
            equipment_id or "Unknown", engineer_name, details,
        )

    result_children = [
        html.Div("\u2705 Maintenance report submitted successfully!",
                 className="alert-banner alert-success"),
    ]
    if has_abnormality:
        result_children.append(
            html.Div(
                f"\u26a0\ufe0f Abnormality detected in: "
                f"{', '.join(abnormal_items)}. "
                "The admin/management team has been notified.",
                className="alert-banner alert-danger",
            )
        )

    return html.Div(result_children), has_abnormality, popup_msg


# ---- Admin: list alerts ----
@app.callback(
    Output("alerts-list", "children"),
    Input("btn-refresh-alerts", "n_clicks"),
)
def refresh_alerts(_):
    notifications = _load_notifications()
    if not notifications:
        return html.P("No abnormality alerts yet.", style={"color": "#888"})

    return [
        html.Div(
            className="notification-item"
            + (" acknowledged" if n.get("acknowledged") else ""),
            children=[
                html.Strong(f"Equipment: {n.get('equipment_id', 'N/A')}"),
                html.Span(
                    f"  \u2022  {n.get('timestamp', '')}",
                    style={"color": "#888", "marginLeft": "8px"},
                ),
                html.P(f"Engineer: {n.get('engineer_name', 'N/A')}"),
                html.P(n.get("abnormality_details", "")),
            ],
        )
        for n in reversed(notifications)
    ]


# ---- Admin: list records ----
@app.callback(
    Output("records-list", "children"),
    Input("btn-refresh-records", "n_clicks"),
)
def refresh_records(_):
    records = _load_records()
    if not records:
        return html.P("No maintenance records yet.", style={"color": "#888"})

    rows = []
    for r in reversed(records):
        abnormal = "\u26a0\ufe0f Yes" if r.get("has_abnormality") else "\u2705 No"
        rows.append(html.Tr([
            html.Td(r.get("date", "")),
            html.Td(r.get("equipment_id", "")),
            html.Td(r.get("engineer_name", "")),
            html.Td(abnormal),
            html.Td(r.get("observations", "")[:80]),
        ]))

    return html.Table(className="checklist-table", children=[
        html.Thead(html.Tr([
            html.Th("Date"),
            html.Th("Equipment"),
            html.Th("Engineer"),
            html.Th("Abnormality"),
            html.Th("Observations"),
        ])),
        html.Tbody(rows),
    ])


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=True)
