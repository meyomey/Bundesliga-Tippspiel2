"""Admin: Einladungen verwalten."""
import secrets
from datetime import datetime, timedelta, timezone

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user

from audit_log import log_admin_action
from extensions import db
from models import InvitationCode


def _admin_invitations_view():
    invites = InvitationCode.query.order_by(InvitationCode.created_at.desc()).all()
    return render_template("admin/invitations.html", invites=invites, now_dt=datetime.now(timezone.utc).replace(tzinfo=None))


def _admin_invitation_create():
    email = (request.form.get("email") or "").strip().lower() or None
    max_uses = request.form.get("max_uses", type=int) or 1
    days = request.form.get("days", type=int) or 30
    max_uses = max(1, min(100, max_uses))
    days = max(1, min(365, days))
    inv = InvitationCode(
        code=secrets.token_urlsafe(18),
        invited_by_user_id=current_user.id,
        email=email,
        max_uses=max_uses,
        uses=0,
        expires_at=datetime.now(timezone.utc) + timedelta(days=days),
    )
    db.session.add(inv)
    db.session.commit()
    log_admin_action("invitation_create", "invitation", inv.id, "Einladungscode erstellt", {"email": email, "max_uses": max_uses})
    flash("✅ Einladungscode erstellt.", "success")
    return redirect(url_for("admin.invitations"), code=303)


def _admin_invitation_deactivate(invite_id):
    inv = db.get_or_404(InvitationCode, invite_id)
    inv.uses = inv.max_uses or 1
    db.session.commit()
    log_admin_action("invitation_deactivate", "invitation", inv.id, "Einladungscode deaktiviert")
    flash("Einladungscode deaktiviert.", "info")
    return redirect(url_for("admin.invitations"), code=303)


def _admin_invitation_delete(invite_id):
    inv = db.get_or_404(InvitationCode, invite_id)
    db.session.delete(inv)
    db.session.commit()
    log_admin_action("invitation_delete", "invitation", invite_id, "Einladungscode geloescht")
    flash("Einladungscode gelöscht.", "warning")
    return redirect(url_for("admin.invitations"), code=303)
