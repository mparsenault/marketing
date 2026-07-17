# Sous-projet A — Fondation Airtable + approbation via lien Teams — Design

Date : 2026-07-16
Révisé : 2026-07-17 — Streamlit conservé comme cœur ; approbation sur une page
Streamlit à enregistrement unique, atteinte par un lien envoyé en DM Teams
(Microsoft Graph) au responsable bureau. Abandon du pivot M365/Power Automate
(qui faisait toute l'approbation hors app) et de l'Interface Airtable.

## Contexte et pivot

Le dépôt contient une app Streamlit (portée d'un Next.js) : une vue filtrée +
éditable des projets Airtable, protégée par SSO Microsoft Entra restreint à
`@elem.global`. Sa raison d'être : donner un accès sans siège Airtable.

Le vrai objectif visé est un **workflow de publication**. Un agent IA
(« Hermès », à construire) rédige les publications des fiches projet ; le
**responsable bureau** de chaque projet doit approuver les brouillons avant
publication sur les réseaux sociaux et le site web.

Le projet global se découpe en trois sous-projets :
- **A (ce spec)** — Fondation Airtable + approbation dans Streamlit.
- **B** — Agent Hermès : génération des brouillons (post + descriptions), accès aux photos SharePoint.
- **C** — Auto-publication (réseaux LinkedIn/Meta, site).

### Choix retenu : approbation dans Streamlit, notification par lien Teams

Décisions structurantes (brainstorming du 2026-07-17) :

- **Streamlit reste le cœur.** L'app n'est pas retirée. On l'étend.
- L'**approbation** se fait sur une **page Streamlit à enregistrement unique**,
  gardée par le SSO `@elem.global` existant. Tout utilisateur `@elem.global`
  connecté qui détient le lien peut approuver (pas de contrôle de rôle strict en
  phase A).
- Le responsable bureau reçoit un **message direct Teams** contenant un résumé
  du brouillon et le **lien** vers sa page d'approbation. Le DM est envoyé via
  **Microsoft Graph depuis du code** (module Python), pas via Power Automate ni
  l'action Teams native d'Airtable (qui ne poste qu'en canal).
- **Cloisonnement souple** : `?record=recXXX` affiche la page d'approbation ;
  la racine affiche le dashboard. Pas de blocage dur — un responsable pourrait
  techniquement atteindre le dashboard en retirant le paramètre ; c'est accepté
  en phase A.

## Objectif du sous-projet A

Mettre en place le socle du cycle de vie « brouillon → approbation → publié »
côté Airtable, la page d'approbation Streamlit et la notification Teams —
**sans** encore d'agent Hermès ni de publication automatique. À la fin de A, on
peut, depuis le dashboard, envoyer manuellement un brouillon pour approbation et
vérifier tout le flux (DM Teams → page → statut réécrit) de bout en bout.

## Deux surfaces dans la même app (`app.py`)

- **Racine (`/`)** → **dashboard** (onglet Projets existant), usage marketing.
- **`/?record=recXXX`** → **page d'approbation** affichant *ce seul* brouillon,
  gardée par SSO `@elem.global`.

Le routage est décidé par la présence du paramètre `record` dans
`st.query_params`.

## Modèle de données (table Projets)

Décision : **champs sur la table Projets** (1 projet = 1 publication). Pas de
table séparée.

### Séparation brouillon / live

Hermès rédigera le post réseaux **et** les descriptions `descFR`/`descEN`. Or le
site Next.js lit `descFR`/`descEN` en direct : écrire un brouillon non approuvé
directement dedans le ferait fuiter sur le site. On sépare donc :

| Champ brouillon (écrit par Hermès en B) | Recopié à la publication (C) vers | Champ live existant |
|---|---|---|
| `BrouillonPost` | post réseaux publié | `postDone = true` |
| `BrouillonDescFR` | `descFR` | `descFR` |
| `BrouillonDescEN` | `descEN` | `descEN` |
| — | mise en ligne | `online = true` |

La recopie brouillon → live et le passage des booléens se font en **sous-projet
C** (publication), pas ici.

### Nouveaux champs à créer sur Projets

| Champ | Type | Détail |
|---|---|---|
| `StatutPublication` | Single select | Options : `À rédiger`, `En attente d'approbation`, `Approuvé`, `Publié`. (Pas de statut `Rejeté` : un rejet renvoie à `À rédiger`, voir cycle de vie.) |
| `BrouillonPost` | Long text | Texte du post réseaux (rempli par Hermès en B ; manuellement pour tester A) |
| `BrouillonDescFR` | Long text | Brouillon description FR |
| `BrouillonDescEN` | Long text | Brouillon description EN |
| `ResponsableBureauEmail` | Email | Adresse `@elem.global` du responsable, cible du DM Teams. Peuplé depuis le texte `ResponsableBureau` (voir Migration). Le champ texte reste. |
| `ApprouvéPar` | Single line text | Email de l'approbateur, écrit par le dashboard (`st.user.email`) à l'approbation (audit). |
| `DateApprobation` | Date | Écrite par le dashboard à l'approbation (audit). |
| `RaisonRejet` | Long text | Motif du rejet, saisi par l'approbateur sur la page d'approbation. |
| `LienPhotosSharePoint` | Formula | `base_url & Project_No` — un dossier SharePoint par `Project_No`. `base_url` déterminé depuis le site SharePoint réel (runbook). |

Aucun champ « collaborateur » : personne du côté responsables n'est invité dans
Airtable.

## Cycle de vie et transitions

```
(vide) --auto--> À rédiger <---------------------[Rejeter (+RaisonRejet)]------------------+
                    |                                                                      |
                    | « Envoyer pour approbation » (dashboard)                             |
                    v  → DM Teams (Graph) au responsable, avec lien ?record=               |
              En attente d'approbation --(page d'approbation Streamlit)--> Approuver       |
                    |                                                          |           |
                    +----------------------------------------------------------+-----------+
                                                       Approuvé
                                                          | [publie C]
                                                       Publié
```

- **Entrée automatique** — automatisation Airtable qui met `StatutPublication =
  À rédiger` quand **toutes** ces conditions sont vraies : `StatutPublication`
  vide **ET** `BrouillonPost` vide **ET** `BrouillonDescFR` vide **ET**
  `BrouillonDescEN` vide **ET** `postDone = false` **ET** `confidential = false`.
  Les projets confidentiels ou déjà postés restent hors pipeline.
- **À rédiger → En attente d'approbation** : en phase A, déclenché par l'action
  **« Envoyer pour approbation »** du dashboard (voir plus bas). En B, Hermès
  reprend ce déclencheur après avoir rempli les brouillons.
- **En attente → notification** : l'action ci-dessus appelle le module de
  notification Graph, qui envoie le DM Teams au `ResponsableBureauEmail` avec le
  lien `?record=<id>`.
- **Approuver** (page d'approbation) : `StatutPublication = Approuvé`,
  `ApprouvéPar = st.user.email`, `DateApprobation = aujourd'hui`.
- **Rejeter** (page d'approbation) : `StatutPublication = À rédiger`,
  `RaisonRejet = <saisie>`. Le brouillon (non vidé) et la `RaisonRejet`
  restent en place comme feedback pour la reprise.
- **Approuvé → Publié** : fait par Hermès (C). Hors périmètre A.

Après rejet, le projet revient à `À rédiger` (avec sa `RaisonRejet`), prêt à
être révisé puis renvoyé pour approbation. Comme ses brouillons ne sont pas
vides, l'automatisation d'entrée `À rédiger` ne le retouche pas.

## Action « Envoyer pour approbation » (dashboard, onglet Projets)

Sur un projet sélectionné dont les brouillons sont remplis :
1. Écrit `StatutPublication = En attente d'approbation` (PATCH Airtable).
2. Appelle `notifications.send_approval_request(email, lien, résumé)` où
   `email = ResponsableBureauEmail`, `lien = base_app_url + "?record=" + id`.
3. `st.cache_data.clear()` + retour visuel (toast / message).

C'est le déclencheur testable de phase A qui remplace Hermès. En B, Hermès
appellera la même logique.

## Page d'approbation Streamlit (`?record=recXXX`)

- Gardée par le SSO `@elem.global` (même mécanisme que le dashboard).
- Charge l'unique enregistrement `record`. Affiche : `Project_No`,
  `NomDuProjet`, `Client`, `BrouillonPost`, `BrouillonDescFR`,
  `BrouillonDescEN`, `LienPhotosSharePoint` (cliquable), et `ResponsableBureau`
  (texte, informatif).
- Deux actions :
  - **Approuver** → payload `Approuvé` + `ApprouvéPar` + `DateApprobation`.
  - **Rejeter** → saisie d'une raison → payload `À rédiger` + `RaisonRejet`.
- Cas limites gérés : `record` absent/inconnu → message d'erreur clair ; statut
  déjà traité (≠ `En attente d'approbation`) → afficher l'état sans reproposer
  les boutons.

## Notification Teams (Microsoft Graph, `notifications.py`)

- Fonction I/O `send_approval_request(email, lien, résumé)` : envoie un DM Teams
  au destinataire via l'API Graph (`ChatMessage.Send`).
- Helpers **purs, testés** : construction du lien `?record=` à partir de
  `base_app_url` + id, et construction du corps du message (titre, extrait du
  post, lien).
- Requiert une **inscription d'app Azure AD** ; les secrets (client id/secret,
  tenant) sont lus depuis la config/variables d'environnement.

**Risque à valider au démarrage** (analogue au risque « connecteur premium » de
l'ancien design) : l'envoi d'un DM 1:1 en *app-only* passe par une API Graph
protégée, qui peut exiger une demande d'approbation Microsoft. Alternatives à
trancher au runbook si l'app-only n'est pas disponible : jeton **délégué** via
un compte de service, ou **repli e-mail Outlook** (`Mail.Send`) portant le même
lien `?record=`. Le module de notification est conçu pour que seule
l'implémentation d'envoi change, pas les appelants.

## Migration `ResponsableBureau` texte → `ResponsableBureauEmail`

`ResponsableBureau` est du texte libre. Pour cibler le DM Teams il faut l'email.

1. Établir une correspondance `nom texte → email @elem.global`.
2. Script de migration (voir plan) qui lit chaque projet et écrit
   `ResponsableBureauEmail` d'après la correspondance. Les noms non mappés sont
   rapportés (log) pour traitement manuel.

Aucune invitation de collaborateur, aucun identifiant utilisateur Airtable requis.

## Streamlit conservé

Aucune suppression de fichiers. `app.py`, `dashboard.py`, `theme.py`,
`transform.py`, `airtable_client.py` et leurs tests restent. On **ajoute** :
- le routage `?record=` dans `app.py` ;
- la page d'approbation et le module `approvals.py` ;
- le module `notifications.py` (Graph) ;
- le script de migration ;
- l'action « Envoyer pour approbation » dans l'onglet Projets.

## Découpage code + tests (TDD)

Logique pure isolée du rendu Streamlit, comme les fonctions existantes
`compute_inline_updates` / `build_text_payload`.

- `app.py` : sélection de surface selon `st.query_params` (`?record=` → page
  d'approbation ; sinon dashboard).
- `approvals.py` (pur, testé) : `target_record_id(query_params)`,
  `build_approval_payload(approver_email, today)`,
  `build_rejection_payload(reason)`.
- `notifications.py` : envoi Graph (I/O) + helpers purs (lien, corps du message).
- `migrate_responsable_email.py` : fonction pure de correspondance (nom→email) +
  runner qui écrit `ResponsableBureauEmail`.
- Rendu Streamlit (page d'approbation, bouton « Envoyer pour approbation »)
  gardé fin ; toute la logique décisionnelle passe par les fonctions pures.

## Nature du livrable

1. Un **runbook de configuration** : champs Airtable, automatisation d'entrée
   `À rédiger`, inscription d'app Azure AD/Graph, `base_url` SharePoint,
   `base_app_url` du lien d'approbation.
2. Du **code testable** : routage `app.py`, `approvals.py`, `notifications.py`,
   script de migration, action « Envoyer pour approbation ».
3. Aucune suppression de Streamlit.

## Tests / acceptation

- **Fonctions pures** (unitaires) : correspondance nom→email (nom inconnu →
  rapporté ; casse/espaces normalisés) ; `target_record_id` (présent / absent) ;
  `build_approval_payload` / `build_rejection_payload` ; construction du lien et
  du corps de message de notification.
- **Acceptation manuelle du flux** (runbook) : projet test non confidentiel →
  passage auto à `À rédiger` ; remplir les brouillons + « Envoyer pour
  approbation » → `En attente d'approbation` **et** le bon responsable reçoit un
  DM Teams avec le lien ; ouvrir le lien → page d'approbation d'un seul
  brouillon (pas le dashboard) ; Approuver → `Approuvé` avec
  `ApprouvéPar`/`DateApprobation` ; sur un autre, Rejeter avec motif → retour à
  `À rédiger` + `RaisonRejet` (brouillon conservé) ; un projet confidentiel ne
  passe jamais à `À rédiger`.
- `pytest` passe (tests existants + nouveaux modules).

## Hors périmètre (YAGNI)

- Génération des brouillons par Hermès (sous-projet B).
- Récupération des photos SharePoint *dans* Airtable — ici un simple **lien** ;
  tirer les images relève de B.
- Publication automatique réseaux/site et recopie brouillon → live (sous-projet C).
- Approbation par canal séparé : une seule approbation couvre post + descriptions.
- Contrôle de rôle strict / blocage dur du dashboard pour les responsables
  (routage souple accepté en A).
- Édition du brouillon pendant l'approbation (approuver/rejeter seulement).
- Interface Airtable et pivot M365/Power Automate (abandonnés).
