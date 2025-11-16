"""
notifications.py
Handles optional Discord notifications for batch summaries or errors.
"""

import json
import urllib.request
from utils import log
import config
from urllib.error import URLError, HTTPError


# Helper to check webhook connectivity and mask URL in logs
def check_webhook_connectivity() -> bool:
    """
    Quickly verify that the Discord webhook is reachable.
    Masks the webhook URL in logs to avoid leaking secrets.
    """
    if not config.WEBHOOK_ENABLED or not getattr(config, "WEBHOOK_URL", ""):
        log("Webhook disabled or URL missing. Skipping connectivity check.")
        return False

    masked = config.WEBHOOK_URL[:30] + "..."  # Masked URL for logs
    try:
        req = urllib.request.Request(config.WEBHOOK_URL, method="HEAD")
        urllib.request.urlopen(req, timeout=3)
        log(f"Webhook connectivity OK: {masked}")
        return True
    except Exception as e:
        log(f"Webhook connectivity FAILED for {masked}: {e}")
        return False


def send_discord_message(content: str):
    """
    Send a simple Discord message. Respects WEBHOOK_ENABLED.
    """
    if not config.WEBHOOK_ENABLED or not getattr(config, "WEBHOOK_URL", ""):
        log("Webhook disabled or missing URL. Skipping Discord message.")
        return False

    if not check_webhook_connectivity():
        log("Skipping send due to failed webhook connectivity.")
        return False

    masked = config.WEBHOOK_URL[:30] + "..."

    payload = {"content": content}

    try:
        req = urllib.request.Request(
            config.WEBHOOK_URL,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req)
        log(f"Discord notification sent to {masked}.")
        return True
    except Exception as e:
        log(f"Failed to send Discord message to {masked}: {e}")
        return False


def send_summary_embed(report):
    """
    Optional: send a nicer embed with stats from the report.
    """
    if not config.WEBHOOK_ENABLED or not getattr(config, "WEBHOOK_URL", ""):
        return False

    if not check_webhook_connectivity():
        log("Skipping embed send due to failed webhook connectivity.")
        return False

    masked = config.WEBHOOK_URL[:30] + "..."

    summary = report.to_summary_dict()

    embed = {
        "title": "Media Conversion Summary",
        "color": config.DISCORD_EMBED_COLOR,
        "fields": [
            {"name": "Mode", "value": summary["mode"], "inline": True},
            {"name": "Total Files", "value": str(summary["total_files"]), "inline": True},
            {"name": "Converted", "value": str(summary["converted"]), "inline": True},
            {"name": "Skipped", "value": str(summary["skipped"]), "inline": True},
            {"name": "Failed", "value": str(summary["failed"]), "inline": True},
        ]
    }

    # Add audio failures if any
    if summary["audio_failures"]:
        embed["fields"].append({
            "name": "Audio Failures",
            "value": str(summary["audio_failures"]),
            "inline": True
        })

    # Add retry failures if any
    if summary["retry_failures"]:
        embed["fields"].append({
            "name": "Retry Failures",
            "value": str(summary["retry_failures"]),
            "inline": True
        })

    # List failed files if any (truncate to first 10 to avoid embed limit)
    if summary["failed_files"]:
        failed_list = summary["failed_files"][:10]
        failed_text = "\n".join(f"- {f}" for f in failed_list)
        if len(summary["failed_files"]) > 10:
            failed_text += "\n... (more omitted)"
        embed["fields"].append({
            "name": "Failed Files",
            "value": failed_text,
            "inline": False
        })

    payload = {"embeds": [embed]}

    try:
        req = urllib.request.Request(
            config.WEBHOOK_URL,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req)
        log(f"Summary embed sent to Discord ({masked}).")
        return True
    except Exception as e:
        log(f"Failed to send Discord embed to {masked}: {e}")
        return False