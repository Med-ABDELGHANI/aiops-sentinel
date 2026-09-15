import json
import os
import time

import requests
import urllib3
from dotenv import load_dotenv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv()

SPLUNK_HEC_URL = os.getenv("SPLUNK_HEC_URL", "https://localhost:8088/services/collector/event")
SPLUNK_HEC_TOKEN = os.getenv("SPLUNK_HEC_TOKEN", "")


def send_to_splunk(event_type: str, data: dict) -> None:
    """Send a structured event to Splunk via HEC.

    Failures are logged locally but never raised, so that observability
    issues never interrupt the agent's normal operation.

    Args:
        event_type (str): category of the event (e.g. "router_decision",
            "tool_call", "final_answer")
        data (dict): the event payload
    """
    if not SPLUNK_HEC_TOKEN:
        return

    payload = {
        "event": {
            "service": "rag_agent",
            "event_type": event_type,
            "timestamp": time.time(),
            **data,
            # "data" : data,
        }
    }

    try:
        requests.post(
            SPLUNK_HEC_URL,
            headers={"Authorization": f"Splunk {SPLUNK_HEC_TOKEN}"},
            data=json.dumps(payload),
            verify=False,
            timeout=3,
        )
    except requests.RequestException as e:
        print(f"[splunk_logger] Failed to send event: {e}")
