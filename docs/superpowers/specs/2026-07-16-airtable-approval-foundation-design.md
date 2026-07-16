# Sous-projet A — Fondation Airtable + approbation — Design

Date : 2026-07-16

## Contexte et pivot

Le dépôt contenait une app Streamlit (portée d'un Next.js) : une vue filtrée +
éditable des projets Airtable, protégée par SSO Microsoft Entra restreint à
`@elem.global`. Sa raison d'être principale était le **contrôle d'accès** (donner
un accès sans siège Airtable).

Le vrai objectif visé est différent : un **workflow de publication**. Un agent IA
(« Hermès », à construire) rédige les publications des fiches projet ; le
**responsable bureau** de chaque projet doit approuver les brouillons avant
publication sur les réseaux sociaux et le site web.

Le projet global se découpe en trois sous-projets :
- **A (ce spec)** — Fondation Airtable + approbation (statuts, Interface, notif). Retrait de Streamlit.
- **B** — Agent Hermès : génération des brouillons (post + descriptions), accès aux photos SharePoint.
- **C** — Auto-publication (réseaux LinkedIn/Meta, site).

Comme l'approbation se fait très bien dans une **Interface Airtable** (et que les
1-2 responsables bureau auront un siège Airtable), l'app Streamlit devient
redondante et est retirée dans ce sous-projet.

## Objectif du sous-projet A

Mettre en place, dans Airtable, le socle du cycle de vie « brouillon →
approbation → publié » et l'écran d'approbation du responsable bureau — **sans**
encore d'agent Hermès ni de publication automatique. À la fin de A, on peut
simuler manuellement un brouillon en attente et vérifier tout le flux
d'approbation de bout en bout.

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
| `StatutPublication` | Single select | Options : `À rédiger`, `En attente d'approbation`, `Approuvé`, `Publié`, `Rejeté` |
| `BrouillonPost` | Long text | Texte du post réseaux (rempli par Hermès en B) |
| `BrouillonDescFR` | Long text | Brouillon description FR |
| `BrouillonDescEN` | Long text | Brouillon description EN |
| `ResponsableBureauUser` | Collaborator | Cible du routage/notif. Peuplé depuis le texte `ResponsableBureau` existant (voir Migration). Le champ texte `ResponsableBureau` reste (non destructif). |
| `ApprouvéPar` | Collaborator | Rempli à l'approbation (audit) |
| `DateApprobation` | Date | Remplie à l'approbation (audit) |
| `RaisonRejet` | Long text | Feedback du responsable en cas de rejet |
| `LienPhotosSharePoint` | Formula | `base_url & Project_No` — un dossier SharePoint par `Project_No`. `base_url` est une constante à déterminer depuis le site SharePoint réel (runbook). |

Les champs existants (`descFR`, `descEN`, `postDone`, `online`, `confidential`,
`ResponsableBureau`, `Project_No`, etc.) sont conservés.

## Cycle de vie et transitions

```
(vide) --auto--> À rédiger --[Hermès B]--> En attente d'approbation
                                                |
                          responsable Approuver |  responsable Rejeter
                                                v                     \
                                            Approuvé --[publie C]--> Publié
                                                                      Rejeté --(retour rédaction)
```

- **Entrée automatique** — une automatisation Airtable met `StatutPublication =
  À rédiger` quand **toutes** ces conditions sont vraies : `StatutPublication`
  vide **ET** `BrouillonPost` vide **ET** `BrouillonDescFR` vide **ET**
  `BrouillonDescEN` vide **ET** `postDone = false` **ET** `confidential = false`.
  Les projets confidentiels ou déjà postés restent hors pipeline (statut vide).
- **À rédiger → En attente d'approbation** : fait par Hermès (B) après avoir
  rempli les brouillons. En sous-projet A, se teste **manuellement**.
- **En attente → Approuvé** : bouton Approuver de l'Interface. Remplit
  `ApprouvéPar` (utilisateur courant) et `DateApprobation` (aujourd'hui).
- **En attente → Rejeté** : bouton Rejeter. Demande `RaisonRejet`.
- **Approuvé → Publié** : fait par Hermès (C). Hors périmètre A.

## Interface Airtable d'approbation

- Page liste **« Brouillons à approuver »**, filtrée sur `StatutPublication =
  En attente d'approbation` **ET** `ResponsableBureauUser = utilisateur courant`
  (chaque responsable ne voit que ses projets).
- Vue détail d'un enregistrement : `Project_No`, `NomDuProjet`, `Entreprise`,
  `Client`, `BrouillonPost`, `BrouillonDescFR`, `BrouillonDescEN`,
  `LienPhotosSharePoint` (cliquable → dossier photos).
- Deux boutons d'action :
  - **Approuver** → `StatutPublication = Approuvé`, `ApprouvéPar = utilisateur
    courant`, `DateApprobation = aujourd'hui`.
  - **Rejeter** → `StatutPublication = Rejeté` ; l'utilisateur saisit
    `RaisonRejet`.

## Automatisation de notification

Déclencheur : `StatutPublication` devient `En attente d'approbation`.
Action : envoyer un email (automatisation Airtable) au `ResponsableBureauUser` du
projet, contenant `Project_No`, `NomDuProjet`, un extrait du `BrouillonPost`, et
le lien vers l'Interface d'approbation.

## Migration `ResponsableBureau` texte → collaborateur

`ResponsableBureau` est aujourd'hui du texte libre. Pour le routage/notif il faut
`ResponsableBureauUser` (collaborateur).

1. Inviter chaque responsable bureau comme collaborateur de la base (leur siège).
2. Établir une table de correspondance `nom texte → identifiant utilisateur Airtable`.
3. Script de migration (voir plan) qui lit chaque projet, et écrit
   `ResponsableBureauUser` d'après la correspondance. Les noms non mappés sont
   rapportés (log) pour traitement manuel.

## Retrait de Streamlit

L'Interface Airtable remplace le dashboard. On retire l'app Streamlit :
suppression de `app.py`, `dashboard.py`, `theme.py`, `transform.py` et de leurs
tests, du dossier `.streamlit/` (config auth/secrets Streamlit), et de la
dépendance `streamlit` dans `requirements.txt`. L'historique git conserve tout.

`airtable_client.py` est **conservé et allégé** (retirer la dépendance à
`st.secrets` dans `get_config`, garder lecture via variables d'environnement)
car il sert de client Airtable réutilisable pour le script de migration et les
futurs sous-projets B et C.

## Nature du livrable

Contrairement au code Streamlit, l'essentiel de A se configure dans l'UI Airtable
et n'est pas du code testable en TDD. Le livrable est :
1. Un **runbook de configuration** pas-à-pas (création des champs, Interface,
   automatisations) — la création des champs se fait à la main dans l'UI (peu de
   champs, une fois).
2. Un **script de migration** `ResponsableBureau → ResponsableBureauUser`
   (répétitif sur beaucoup d'enregistrements → automatisé), testable.
3. Le **retrait de Streamlit** (suppression de fichiers).

## Tests / acceptation

- **Script de migration** : tests unitaires sur la fonction pure de correspondance
  (nom → userId ; nom inconnu → rapporté ; casse/espaces normalisés).
- **Acceptation manuelle du flux** (runbook) : créer un projet de test non
  confidentiel → vérifier passage auto à `À rédiger` ; remplir les brouillons +
  passer à `En attente d'approbation` → vérifier réception de l'email par le bon
  responsable ; ouvrir l'Interface → le projet apparaît sous le bon utilisateur,
  pas sous un autre ; cliquer Approuver → `Approuvé` + `ApprouvéPar`/`DateApprobation`
  remplis ; cliquer Rejeter sur un autre → `Rejeté` + `RaisonRejet` saisie ;
  vérifier qu'un projet confidentiel ne passe jamais à `À rédiger`.
- Après retrait de Streamlit : `pytest` passe (ne reste que les tests du script
  de migration et d'`airtable_client`).

## Hors périmètre (YAGNI)

- Génération des brouillons par Hermès (sous-projet B).
- Accès/récupération des photos SharePoint *dans* Airtable — ici on ne met qu'un
  **lien** ; tirer les images relève de B (Hermès a besoin des photos pour rédiger).
- Publication automatique réseaux/site et recopie brouillon → live (sous-projet C).
- Approbation par canal séparé : une seule approbation couvre post + descriptions.
- Notification Teams (on s'en tient à l'email Airtable).
