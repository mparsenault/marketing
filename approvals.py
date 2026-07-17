"""Fonctions pures du cycle d'approbation : routage et payloads de statut.

Aucun I/O ici (ni Streamlit, ni réseau) — testables directement.
"""

PENDING = "En attente d'approbation"


def target_record_id(query_params):
    """Id de l'enregistrement à approuver, depuis ?record=... ; None si absent."""
    raw = query_params.get("record")
    if not raw:
        return None
    value = raw.strip()
    return value or None


def build_pending_payload() -> dict:
    """Passe un projet en attente d'approbation."""
    return {"StatutPublication": PENDING}


def build_approval_payload(approver_email: str, today: str) -> dict:
    """Approbation : statut + audit (qui, quand)."""
    return {
        "StatutPublication": "Approuvé",
        "ApprouvéPar": approver_email,
        "DateApprobation": today,
    }


def build_rejection_payload(reason: str) -> dict:
    """Rejet : renvoie à « À rédiger » en conservant le motif comme feedback."""
    return {"StatutPublication": "À rédiger", "RaisonRejet": reason}
