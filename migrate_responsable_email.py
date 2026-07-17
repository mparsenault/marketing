"""Migration : peupler ResponsableBureauEmail depuis le texte ResponsableBureau.

Usage : python migrate_responsable_email.py   (lit MAPPING ci-dessous)
La fonction pure build_migration_updates est testée ; le runner main() applique.
"""

import airtable_client
import transform

# Correspondance nom (tel qu'écrit dans Airtable) → email @elem.global.
# À compléter au runbook avant exécution.
MAPPING = {
    # "Jean Tremblay": "jean.tremblay@elem.global",
}


def normalize(name: str) -> str:
    return " ".join((name or "").split()).lower()


def map_name_to_email(name: str, mapping: dict):
    lookup = {normalize(k): v for k, v in mapping.items()}
    return lookup.get(normalize(name))


def build_migration_updates(projects: list, mapping: dict):
    updates = []
    unmapped = set()
    for p in projects:
        name = p.get("responsable_bureau", "")
        if not name:
            continue
        email = map_name_to_email(name, mapping)
        if email:
            updates.append((p["id"], {"ResponsableBureauEmail": email}))
        else:
            unmapped.add(name)
    return updates, sorted(unmapped)


def main():
    cfg = airtable_client.get_config()
    records = airtable_client.fetch_projects(**cfg)
    projects = [transform.record_to_project(r) for r in records]
    updates, unmapped = build_migration_updates(projects, MAPPING)
    for rec_id, payload in updates:
        airtable_client.update_project(
            cfg["pat"], cfg["base_id"], cfg["table_name"], rec_id, payload)
    print(f"{len(updates)} projet(s) mis à jour.")
    if unmapped:
        print("Noms non mappés (à compléter dans MAPPING) :")
        for name in unmapped:
            print(f"  - {name}")


if __name__ == "__main__":
    main()
