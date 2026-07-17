# Runbook — Fondation approbation (sous-projet A)

## 1. Champs Airtable à créer sur la table Projets
- `StatutPublication` — Single select : `À rédiger`, `En attente d'approbation`, `Approuvé`, `Publié`.
- `BrouillonPost`, `BrouillonDescFR`, `BrouillonDescEN` — Long text.
- `ResponsableBureauEmail` — Email.
- `ApprouvéPar` — Single line text.
- `DateApprobation` — Date.
- `RaisonRejet` — Long text.
- Lien photos : **réutiliser le champ `sharepointUrl` existant** (URL) — aucun
  champ à créer. Le code lit `sharepointUrl` comme lien photos sur la page
  d'approbation.

## 2. Automatisation d'entrée « À rédiger »
- Déclencheur : When record matches conditions.
- Conditions (toutes) : `StatutPublication` vide ET `BrouillonPost` vide ET
  `BrouillonDescFR` vide ET `BrouillonDescEN` vide ET `postDone` = false ET
  `confidential` = false.
- Action : Update record → `StatutPublication` = `À rédiger`.

## 3. Inscription d'app Azure AD (Microsoft Graph)
- Créer une app dans Azure AD (Entra) ; noter Tenant ID, Client ID, créer un Client secret.
- Permissions Graph : `Chat.Create`, `ChatMessage.Send` (application).
  ⚠️ L'envoi de messages de chat en application est une API protégée : suivre la
  demande d'accès Microsoft si nécessaire. Repli documenté (spec) : jeton délégué
  via compte de service, ou `Mail.Send` (e-mail Outlook portant le même lien).
- `GRAPH_SENDER_ID` : l'object id (GUID) de l'utilisateur/compte de service expéditeur.

## 4. Secrets à renseigner (.streamlit/secrets.toml ou variables d'env)
- `AIRTABLE_PAT`, `AIRTABLE_BASE_ID`, `AIRTABLE_TABLE_NAME`
- `GRAPH_TENANT_ID`, `GRAPH_CLIENT_ID`, `GRAPH_CLIENT_SECRET`, `GRAPH_SENDER_ID`
- `BASE_APP_URL` — URL publique de l'app Streamlit (pour construire `?record=`).

## 5. Migration des responsables
- Compléter `MAPPING` dans `migrate_responsable_email.py` (nom Airtable → email).
- Exécuter : `python migrate_responsable_email.py` ; traiter les noms non mappés listés.

## 6. Acceptation manuelle
1. Projet test non confidentiel, brouillons vides → passe auto à `À rédiger`.
2. Remplir les brouillons, sélectionner le projet dans le dashboard, cliquer
   « 📤 Envoyer pour approbation » → statut `En attente d'approbation` + le
   responsable reçoit un DM Teams avec le lien.
3. Ouvrir le lien → page d'approbation d'un seul brouillon (pas le dashboard).
4. Approuver → `Approuvé` + `ApprouvéPar` + `DateApprobation`.
5. Sur un autre : Rejeter avec motif → retour à `À rédiger` + `RaisonRejet`.
6. Un projet confidentiel ne passe jamais à `À rédiger`.
