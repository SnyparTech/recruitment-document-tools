"""
Device allowlist for the Chrome extension.

Registration tokens (one-time, handed out by the admin) live in
settings.DEVICE_REGISTRATION_TOKENS (comma-separated, .env). Redeeming one
permanently authorizes the device id that redeemed it and burns the token —
it can't be reused to authorize a second device. The authorized-device set
and the list of burned tokens are persisted to a JSON file (same pattern as
state_persistence.py) so a backend restart doesn't un-authorize everyone.

Device ids themselves are opaque, extension-generated UUIDs (see
extension/content.js) — this module never tries to fingerprint hardware.
"""
import json
import logging
import os
import tempfile
import time
from typing import Any, Dict

logger = logging.getLogger(__name__)

_STATE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".data")
_STATE_FILE = os.path.join(_STATE_DIR, "authorized_devices.json")


def _load() -> Dict[str, Any]:
    try:
        with open(_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                data.setdefault("devices", {})
                data.setdefault("burned_tokens", [])
                return data
    except FileNotFoundError:
        pass
    except Exception as exc:
        logger.warning("Could not load authorized_devices.json (%s) — starting empty.", exc)
    return {"devices": {}, "burned_tokens": []}


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
    return bool(_valid_tokens(settings))


def _valid_tokens(settings) -> set:
    raw = settings.DEVICE_REGISTRATION_TOKENS or ""
    return {t.strip() for t in raw.split(",") if t.strip()}


def is_authorized(device_id: str) -> bool:
    if not device_id:
        return False
    return device_id in _load()["devices"]


def register_device(settings, registration_token: str, device_id: str) -> None:
    """Redeem a one-time token for device_id. Raises ValueError on any failure
    (unknown/already-burned token, missing device_id) with a message safe to
    return to the caller."""
    if not device_id or not device_id.strip():
        raise ValueError("device_id is required.")
    token = (registration_token or "").strip()
    valid_tokens = _valid_tokens(settings)
    if not valid_tokens:
        raise ValueError("Device registration is not enabled on this server.")

    data = _load()
    if token in data["burned_tokens"]:
        raise ValueError("This registration token has already been used.")
    if token not in valid_tokens:
        raise ValueError("Invalid registration token.")

    data["devices"][device_id] = {"registered_at": time.time()}
    data["burned_tokens"].append(token)
    _save(data)
    logger.info("Device %s registered via token redemption.", device_id)
