"""Mapping Airtable → projet, filtres, tri, stats.

Port fidèle de la logique du Next.js (app/page.tsx, FilterBar.tsx,
ProjectTable.tsx, lib/utils.ts).
"""

import re

_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")


def build_dates_display(date_debut: str, date_fermeture: str) -> str:
    debut = (date_debut or "").strip()
    fermeture = (date_fermeture or "").strip()
    if debut and fermeture:
        return f"{debut} - {fermeture}"
    if debut:
        return debut
    return ""


def record_to_project(record: dict) -> dict:
    f = record.get("fields", {})
    date_debut = f.get("DateDebut", "") or ""
    date_fermeture = f.get("DateFermeture", "") or ""
    return {
        "id": record.get("id", ""),
        "project_no": f.get("Project_No", "") or "",
        "company": f.get("Entreprise", "") or "",
        "project": f.get("NomDuProjet", "") or "",
        "client": f.get("Client", "") or "",
        "desc_fr": f.get("descFR", "") or "",
        "date_debut": date_debut,
        "date_fermeture": date_fermeture,
        "dates": build_dates_display(date_debut, date_fermeture),
        "responsable_bureau": f.get("ResponsableBureau", "") or "",
        "responsable_chantier": f.get("ResponsableDeChantier", "") or "",
        "photo_available": bool(f.get("photoAvailable", False)),
        "online": bool(f.get("online", False)),
        "post_done": bool(f.get("postDone", False)),
        "confidential": bool(f.get("confidential", False)),
        "confidential_reason": f.get("confidentialReason", "") or "",
        "notes": f.get("notes", "") or "",
        "desc_en": f.get("descEN", "") or "",
    }


def extract_years(date_str: str) -> list:
    if not date_str or date_str == "N/A":
        return []
    matches = _YEAR_RE.findall(date_str)
    return sorted({int(m) for m in matches})


def filter_recent(projects: list, current_year: int, span: int = 5) -> list:
    min_year = current_year - span
    out = []
    for p in projects:
        years = extract_years(p.get("dates", ""))
        if years and years[0] >= min_year:
            out.append(p)
    return out


def apply_filters(projects: list, f: dict) -> list:
    search = (f.get("search") or "").strip().lower()
    company = f.get("company") or ""
    year_from = f.get("year_from") or ""
    year_to = f.get("year_to") or ""
    without_photo = bool(f.get("without_photo"))
    without_online = bool(f.get("without_online"))
    without_post = bool(f.get("without_post"))

    out = []
    for p in projects:
        if search:
            haystack = " ".join([
                p.get("project", ""), p.get("client", ""), p.get("project_no", ""),
                p.get("company", ""), p.get("desc_fr", ""), p.get("notes", ""),
            ]).lower()
            if search not in haystack:
                continue
        if company and p.get("company") != company:
            continue
        if without_photo and p.get("photo_available"):
            continue
        if without_online and p.get("online"):
            continue
        if without_post and p.get("post_done"):
            continue
        if year_from or year_to:
            years = extract_years(p.get("dates", ""))
            if not years:
                continue
            if year_from and min(years) < int(year_from):
                continue
            if year_to and max(years) > int(year_to):
                continue
        out.append(p)
    return out


def _end_date(p: dict) -> str:
    return (p.get("date_fermeture") or p.get("date_debut") or "").strip()


def sort_by_end_date_desc(projects: list) -> list:
    # Les projets sans date de fin passent en dernier ; sinon tri décroissant.
    return sorted(
        projects,
        key=lambda p: (_end_date(p) != "", _end_date(p)),
        reverse=True,
    )


def compute_stats(projects: list) -> dict:
    return {
        "total": len(projects),
        "photos": sum(1 for p in projects if p.get("photo_available")),
        "online": sum(1 for p in projects if p.get("online")),
        "todo": sum(1 for p in projects if not p.get("post_done")),
    }


def company_options(projects: list) -> list:
    return sorted({p.get("company") for p in projects if p.get("company")})


def year_options(projects: list) -> list:
    years = set()
    for p in projects:
        years.update(extract_years(p.get("dates", "")))
    return sorted(years)
