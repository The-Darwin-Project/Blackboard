# BlackBoard/src/observers/kargo_helpers.py
# @ai-rules:
# 1. [Constraint]: Pure stdlib-only helper module (no kubernetes, no asyncio, no Redis); keep <= 100 lines.
# 2. [Pattern]: Coerce K8s string fields via _s() so JSON nulls never propagate None.
# 3. [Pattern]: project_stage_status() is shared by get_stage_status() and poll_kargo_stage_status().
"""Pure verification extraction, stale-freight guards, and stage status projection for KargoObserver."""
from __future__ import annotations

from datetime import datetime, timezone

PROMOTION_FAILED_PHASES = frozenset({"Errored", "Failed"})
VERIFICATION_FAILED_PHASES = frozenset({"Failed", "Error", "Inconclusive"})
VERIFICATION_HOLD_PHASES = frozenset({"Pending", "Running", "Aborted"})


def _s(val: object) -> str:
    """Coerce optional K8s JSON string fields to str."""
    return val if isinstance(val, str) else ""


def _parse_ts(val: str) -> datetime | None:
    """Parse RFC3339 timestamp to UTC-aware datetime, or None on error."""
    if not isinstance(val, str) or not val or len(val) > 64: return None
    try: dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
    except ValueError: return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def extract_latest_verification(status: dict) -> dict:
    """Extract newest freightHistory[0].verificationHistory[0] entry with null-safe strings."""
    fh = status.get("freightHistory") if isinstance(status, dict) else None
    if not isinstance(fh, list) or not fh or not isinstance(fh[0], dict):
        return {}
    vh = fh[0].get("verificationHistory")
    if not isinstance(vh, list) or not vh or not isinstance(vh[0], dict):
        return {}
    vh0, ar = vh[0], vh[0].get("analysisRun")
    return {
        "id": _s(vh0.get("id")), "phase": _s(vh0.get("phase")),
        "message": _s(vh0.get("message")), "start_time": _s(vh0.get("startTime")),
        "finish_time": _s(vh0.get("finishTime")),
        "analysis_run": _s(ar.get("name")) if isinstance(ar, dict) else "",
        "freight_id": _s(fh[0].get("id")),
    }


def is_verification_stale(promo: dict, verif: dict, *, promo_is_current: bool = False) -> bool:
    """Return True when freightHistory[0] verification belongs to an older/superseded freight."""
    if not verif or promo_is_current:
        return bool(verif and promo_is_current)
    p = promo if isinstance(promo, dict) else {}
    ps = p.get("status") if isinstance(p.get("status"), dict) else {}
    phase = _s(ps.get("phase"))
    if phase in PROMOTION_FAILED_PHASES:
        return True
    if phase == "Succeeded":
        fc, pf = ps.get("freightCollection"), p.get("freight")
        promo_fc_id = (_s(fc.get("id")) if isinstance(fc, dict) else "") or (_s(pf.get("name")) if isinstance(pf, dict) else "")
        fh0_id = _s(verif.get("freight_id"))
        return bool(promo_fc_id and fh0_id and promo_fc_id != fh0_id)
    if phase == "Aborted":
        v_dt = _parse_ts(_s(verif.get("start_time")) or _s(verif.get("finish_time")))
        p_dt = _parse_ts(_s(ps.get("finishedAt")) or _s(ps.get("startedAt")) or _s(p.get("finishedAt")))
        return v_dt is not None and p_dt is not None and v_dt < p_dt
    return False


def project_stage_status(status: dict) -> tuple[bool, dict, dict, dict]:
    """Project (promo_is_current, promo, promo_status, active_verif) for on-demand read/poll."""
    st = status if isinstance(status, dict) else {}
    cur = st.get("currentPromotion") if isinstance(st.get("currentPromotion"), dict) else {}
    last = st.get("lastPromotion") if isinstance(st.get("lastPromotion"), dict) else {}
    promo_is_current = bool(_s(cur.get("name")))
    promo = cur if promo_is_current else last
    ps = promo.get("status") if isinstance(promo.get("status"), dict) else {}
    raw_verif = extract_latest_verification(st)
    active_verif = {} if is_verification_stale(promo, raw_verif, promo_is_current=promo_is_current) else raw_verif
    return promo_is_current, promo, ps, active_verif


def resolve_stage_freight(status: dict, promo: dict, verif: dict) -> str:
    """Resolve freight identifier across promotion, freightSummary, and verification history."""
    pf = promo.get("freight") if isinstance(promo, dict) else None
    p_name = _s(pf.get("name")) if isinstance(pf, dict) else ""
    summary = _s(status.get("freightSummary")) if isinstance(status, dict) else ""
    v_id = _s(verif.get("freight_id")) if isinstance(verif, dict) else ""
    return p_name or v_id or summary


def build_verification_dedup_key(verif: dict, promo_name: str) -> str:
    """Build verification-prefixed dedup key keyed on verification UUID (or fallback tuple)."""
    vid = _s(verif.get("id")) if isinstance(verif, dict) else ""
    if vid:
        return f"verification:{vid}"
    v = verif if isinstance(verif, dict) else {}
    fb = _s(v.get("finish_time")) or _s(v.get("phase"))
    if not fb:
        fb = _s(v.get("start_time")) or _s(v.get("analysis_run")) or _s(v.get("freight_id")) or "unknown"
    return f"verification:{promo_name}:{fb}"
