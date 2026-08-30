"""Admin Activity Log Helper."""
import json
from datetime import datetime, timezone

from flask import has_request_context, request
from flask_login import current_user

from extensions import db
from models import AdminActivityLog


def log_admin_action(action, entity_type=None, entity_id=None, message=None, metadata=None, commit=True):
    """Schreibt einen Audit-Log-Eintrag fuer Admin-Aktionen.

    Fehler beim Logging sollen die eigentliche Admin-Aktion nie verhindern.
    """
    try:
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
