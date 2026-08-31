"""Admin Activity Log Helper."""
import json
from datetime import date, datetime, timezone

from flask import has_request_context, request
from flask_login import current_user

from extensions import db
from models import AdminActivityLog


def _jsonable(value):
    """Normalisiert Modellwerte fuer den JSON-Vergleich (Datum -> ISO-String)."""
    if isinstance(value, (datetime, date)):
        try:
            return value.isoformat()
        except Exception:
            return str(value)
    return value


def snapshot_model(obj, attrs):
    """Liest die angegebenen Attribute eines Modells aus (fuer before/after)."""
    data = {}
    for attr in attrs:
        if not hasattr(obj, attr):
            continue
        data[attr] = _jsonable(getattr(obj, attr))
    return data


def diff_snapshots(before, after):
    """Ermittelt geaenderte Felder: {feld: {"from": alt, "to": neu}}.

    Verglichen werden die Schluessel von ``after``; Felder mit unveraendertem
    Wert fallen weg. None-Gleichheit wird beachtet.
    """
    before = before or {}
    after = after or {}
    diff = {}
    for key, new_val in after.items():
        old_val = before.get(key)
        if _jsonable(old_val) != _jsonable(new_val):
            diff[key] = {"from": _jsonable(old_val), "to": _jsonable(new_val)}
    return diff


def log_admin_action(action, entity_type=None, entity_id=None, message=None, metadata=None, commit=True,
                     before=None, after=None):
    """Schreibt einen Audit-Log-Eintrag fuer Admin-Aktionen.

    ``before``/``after`` koennen als Attribute-Dictionaries (z. B. aus
    :func:`snapshot_model`) uebergeben werden; die berechnete Diff wird dann
    als ``diff``-Schluessel in die Metadaten gelegt.

    Fehler beim Logging sollen die eigentliche Admin-Aktion nie verhindern.
    """
    try:
        if before is not None and after is not None:
            diff = diff_snapshots(before, after)
            if diff:
                if metadata is None:
                    metadata = {}
                if isinstance(metadata, dict):
                    metadata = {**metadata, "diff": diff}
                else:
                    metadata = {"payload": metadata, "diff": diff}
        admin_id = None
        ip = None
        ua = None
        if has_request_context():
            if getattr(current_user, "is_authenticated", False):
                admin_id = current_user.id
            ip = request.headers.get("X-Forwarded-For", request.remote_addr or "")
            if ip and "," in ip:
                ip = ip.split(",", 1)[0].strip()
            ua = (request.headers.get("User-Agent", "") or "")[:300]
        entry = AdminActivityLog(
            admin_user_id=admin_id,
            action=str(action)[:80],
            entity_type=str(entity_type)[:80] if entity_type else None,
            entity_id=str(entity_id)[:80] if entity_id is not None else None,
            message=str(message)[:500] if message else None,
            metadata_json=json.dumps(metadata, ensure_ascii=False, default=str) if metadata is not None else None,
            ip_address=ip,
            user_agent=ua,
            created_at=datetime.now(timezone.utc),
        )
        db.session.add(entry)
        if commit:
            db.session.commit()
        return entry
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        return None
