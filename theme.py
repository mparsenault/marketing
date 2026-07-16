"""Couleurs de compagnie et présentation du statut confidentiel.

Port de lib/utils.ts (getCompanyColor) et lib/projectVisual.ts.
"""

COMPANY_COLORS = {
    "Talvi": "#8E8D35",
    "Descimco": "#008557",
    "Elem": "#7B4FCC",
    "Industro-Tech": "#BC302B",
    "Ondel": "#0999AA",
    "Qualifab": "#FDD900",
    "Quantech": "#3568B2",
}

_DEFAULT_COLOR = "#8A96AA"


def get_company_color(company: str) -> str:
    return COMPANY_COLORS.get(company, _DEFAULT_COLOR)


def get_confidential_presentation(confidential: bool, reason: str = "") -> dict:
    if not confidential:
        return {"icon": "🔓", "row_dimmed": False, "tooltip": ""}
    reason = (reason or "").strip()
    return {
        "icon": "🔒",
        "row_dimmed": True,
        "tooltip": reason if reason else "Projet non-publiable",
    }
