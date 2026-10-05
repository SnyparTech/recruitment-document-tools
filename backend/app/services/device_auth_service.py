"""
Device allowlist for the Chrome extension, gated by company email.

A device registers once with its work email (must end @<AUTHORIZED_EMAIL_DOMAIN>,
default snypartech.com). One email = one device: registering a second device
with the same email is rejected outright — an admin must clear the old entry
in authorized_devices.json first (e.g. after a laptop swap). The authorized
set is persisted to a JSON file (same pattern as state_persistence.py) so a
backend restart doesn't un-authorize everyone.

Device ids themselves are opaque, extension-generated UUIDs (see
extension/content.js) — this module never tries to fingerprint hardware.
"""
import json
import logging
import os
import re
import tempfile
import time
from typing import Any, Dict

logger = logging.getLogger(__name__)

_STATE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".data")
_STATE_FILE = os.path.join(_STATE_DIR, "authorized_devices.json")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _load() -> Dict[str, Any]:
    try:
        with open(_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                data.setdefault("devices", {})  # device_id -> {email, registered_at}
                data.setdefault("emails", {})   # email (lowercase) -> device_id
                return data
    except FileNotFoundError:
        pass
    except Exception as exc:
        logger.warning("Could not load authorized_devices.json (%s) — starting empty.", exc)
    return {"devices": {}, "emails": {}}


def _save(data: Dict[str, Any]) -> None:
    try:
        os.makedirs(_STATE_DIR, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=_STATE_DIR, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f)
            os.replace(tmp_path, _STATE_FILE)
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
    except Exception as exc:
        logger.warning("Could not persist authorized_devices.json (%s).", exc)


def device_lock_enabled(settings) -> bool:
    return bool(getattr(settings, "DEVICE_AUTH_ENABLED", False))


def is_authorized(device_id: str) -> bool:
    if not device_id:
        return False
    return device_id in _load()["devices"]


def register_device(settings, email: str, device_id: str) -> None:
    """Register device_id against a work email. Raises ValueError (message is
    safe to return to the caller) on any failure: malformed email, wrong
    domain, email already tied to a different device, or missing device_id."""
    if not device_id or not device_id.strip():
        raise ValueError("device_id is required.")

    email = (email or "").strip().lower()
    if not _EMAIL_RE.match(email):
        raise ValueError("Enter a valid email address.")

    domain = (getattr(settings, "AUTHORIZED_EMAIL_DOMAIN", "") or "").strip().lower()
    if domain and not email.endswith("@" + domain):
        raise ValueError(f"Only @{domain} email addresses can register a device.")

    data = _load()
    existing_device = data["emails"].get(email)
    if existing_device and existing_device != device_id:
        raise ValueError("This email is already registered to another device. Ask an admin to clear it first.")

    data["devices"][device_id] = {"email": email, "registered_at": time.time()}
    data["emails"][email] = device_id
    _save(data)
    logger.info("Device %s registered to %s.", device_id, email)
