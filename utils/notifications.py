"""Notification helpers for the Maintenance Management application.

When an abnormality is detected the system needs to alert the admin /
management team.  This module provides:

* ``build_alert_message`` – formats a human-readable alert string.
* ``send_email_notification`` – sends an email via SMTP (best-effort).
* ``log_notification`` – appends the alert to a local JSON log so that
  the admin dashboard can display it even when email delivery fails.
"""

import json
import os
import smtplib
from datetime import datetime, timezone
from email.mime.text import MIMEText
from pathlib import Path

# Directory where notification logs are persisted
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def build_alert_message(equipment_id, engineer_name, abnormality_details):
    """Return a formatted alert message string."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return (
        f"⚠️  ABNORMALITY ALERT\n"
        f"Equipment : {equipment_id}\n"
        f"Engineer  : {engineer_name}\n"
        f"Time      : {timestamp}\n"
        f"Details   : {abnormality_details}\n"
    )


def log_notification(equipment_id, engineer_name, abnormality_details):
    """Persist an abnormality notification to a JSON log file.

    Returns the notification dict that was written.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    log_path = DATA_DIR / "notifications.json"

    notification = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "equipment_id": equipment_id,
        "engineer_name": engineer_name,
        "abnormality_details": abnormality_details,
        "acknowledged": False,
    }

    notifications = []
    if log_path.exists():
        with open(log_path, "r") as fh:
            try:
                notifications = json.load(fh)
            except json.JSONDecodeError:
                notifications = []

    notifications.append(notification)

    with open(log_path, "w") as fh:
        json.dump(notifications, fh, indent=2)

    return notification


def send_email_notification(
    equipment_id,
    engineer_name,
    abnormality_details,
    recipient_email=None,
):
    """Send an abnormality alert email via SMTP (best-effort).

    SMTP settings are read from environment variables:

    * ``SMTP_HOST`` – SMTP server hostname (default ``localhost``)
    * ``SMTP_PORT`` – SMTP server port (default ``587``)
    * ``SMTP_USER`` – SMTP username
    * ``SMTP_PASS`` – SMTP password
    * ``ALERT_FROM``  – sender address
    * ``ALERT_TO``    – default recipient (overridden by *recipient_email*)

    Returns ``True`` on success, ``False`` on failure.
    """
    host = os.environ.get("SMTP_HOST", "localhost")
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER", "")
    password = os.environ.get("SMTP_PASS", "")
    sender = os.environ.get("ALERT_FROM", "maintenance@example.com")
    recipient = recipient_email or os.environ.get("ALERT_TO", "")

    if not recipient:
        return False

    body = build_alert_message(equipment_id, engineer_name, abnormality_details)
    msg = MIMEText(body)
    msg["Subject"] = f"Maintenance Alert – {equipment_id}"
    msg["From"] = sender
    msg["To"] = recipient

    try:
        with smtplib.SMTP(host, port, timeout=10) as server:
            if user and password:
                server.starttls()
                server.login(user, password)
            server.sendmail(sender, [recipient], msg.as_string())
        return True
    except Exception:
        return False
