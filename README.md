# cog-history

Outil en ligne de commande pour retracer l'**historique complet des communes françaises** à partir du [Code Officiel Géographique](https://www.insee.fr/fr/information/2560452) (COG) de l'INSEE : fusions, scissions, changements de nom, changements de code, communes nouvelles, etc., depuis 1943.

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![Licence](https://img.shields.io/badge/licence-MIT-green)
![Dépendances](https://img.shields.io/badge/dépendances-aucune-brightgreen)

---

## Fonctionnalités

- **Fiche commune** — nom, type (COM/COMD/COMA/ARM), département, région, arrondissement, canton, commune parente
- **Historique complet** — tous les événements depuis 1943 (fusions, changements de nom, de code, de département, créations, rétablissements…)
- **Récursion sur les absorptions** — remonte l'historique de chaque commune absorbée, y compris les sous-absorptions
- **Codes historiques** — un ancien code (ex. `75001` → `94002`) affiche la chaîne de succession avec dates et la fiche de la commune actuelle
- **Visualisation HTML** — frise chronologique interactive par commune, canton, arrondissement ou département
- **Zéro dépendance** — uniquement la bibliothèque standard Python

## Installation

```bash
git clone https://github.com/<user>/cog-history.git
cd cog-history
```

Aucune dépendance à installer. Python 3.10+ requis.

## Démarrage rapide

```bash
# 1. Télécharger les données COG depuis l'INSEE (~6 fichiers CSV)
python cog_history.py --download

# 2. Consulter l'historique d'une commune
python cog_history.py 73010
```

Exemple de sortie pour Entrelacs (73010) :

```
══════════════════════════════════════════════════════════════════════
  FICHE COMMUNE
══════════════════════════════════════════════════════════════════════

  Code INSEE      73010
  Nom             Entrelacs
  Type            Commune
  Département     Savoie (73)
  Région          Auvergne-Rhône-Alpes (84)
  Arrondissement  Chambéry (1)
  Canton          Albens (05)

══════════════════════════════════════════════════════════════════════
  HISTORIQUE (4 événement(s))
══════════════════════════════════════════════════════════════════════

  1972-09-29  [MOD 33] Fusion-association (absorbée)
    73016 Ansigny  →  73010 Albens

  1974-01-01  [MOD 33] Fusion-association (absorbée)
    73010 Albens  →  73010 Albens

  2016-01-01  [MOD 32] Commune nouvelle
    73062 Cessens  →  73010 Entrelacs
  ...

  Communes absorbées (6)
  ──────────────────────────────────────────────────────────────────
      ├─ 73016 Ansigny  (absorbée le 2016-01-01, Commune nouvelle)
      ├─ 73062 Cessens  (absorbée le 2016-01-01, Commune nouvelle)
      ├─ 73108 Épersy   (absorbée le 2016-01-01, Commune nouvelle)
      ...
```

## Utilisation

### Fiche et historique d'une commune

```bash
python cog_history.py 01015              # Arboys en Bugey (commune nouvelle)
python cog_history.py 69008              # Lyon 8e — commune sans événement
python cog_history.py 75001              # Code historique → affiche la succession vers 94002
python cog_history.py 49018 --depuis 2000  # Filtrer les événements depuis 2000
```

### Sortie JSON

```bash
python cog_history.py 73010 --json
```

Retourne un objet structuré avec la fiche, les identités successives, les événements et les communes absorbées (récursivement). Utile pour l'intégration dans un pipeline.

### Visualisation HTML interactive

Génère une frise chronologique dans un fichier HTML autonome (aucune dépendance externe), sauvegardé dans le dossier `html/` :

```bash
# Pour une commune et ses absorbées
python cog_history.py 73010 --html entrelacs.html

# Pour un département entier
python cog_history.py --dep 73 --html savoie.html

# Pour un arrondissement (format DEP-ARR)
python cog_history.py --arr 73-1 --html arr_chambery.html

# Pour un canton (format DEP-CAN)
python cog_history.py --canton 73-05 --html canton_albens.html
```

Le fichier HTML s'ouvre automatiquement dans le navigateur. Il inclut :

- une barre par commune, segmentée selon les changements de nom
- un code couleur (vert = active, violet = commune nouvelle, gris = absorbée)
- des lignes de fusion reliant les communes absorbées à leur commune cible
- des marqueurs au survol pour chaque événement
- un champ de recherche et un zoom
- le support du dark mode

### Statistiques globales

```bash
python cog_history.py --stats
```

### Options complètes

| Option | Description |
|---|---|
| `<CODE_INSEE>` | Code INSEE à rechercher (ex: `01015`, `75056`) |
| `--depuis ANNEE` | Filtrer les événements à partir d'une année |
| `--json` | Sortie au format JSON |
| `--html FICHIER` | Générer une visualisation HTML (dans `html/`) |
| `--dep DEP` | Filtrer par département (ex: `73`) |
| `--arr DEP-ARR` | Filtrer par arrondissement (ex: `73-1`) |
| `--canton DEP-CAN` | Filtrer par canton (ex: `73-05`) |
| `--download` | Télécharger les fichiers COG depuis l'INSEE |
| `--millesime 2025\|2026` | Choisir le millésime COG (défaut: 2026) |
| `--data FICHIER` | Utiliser un fichier `mvtcommune` CSV personnalisé |
| `--stats` | Afficher les statistiques globales de la base |

## Types d'événements (codes MOD)

| MOD | Description |
|---|---|
| 10 | Changement de nom |
| 20 | Création |
| 21 | Rétablissement |
| 30 | Suppression (fusion simple) |
| 31 | Fusion-association (commune absorbante) |
| 32 | Création de commune nouvelle |
| 33 | Fusion-association (commune absorbée) |
| 34 | Transformation fusion-association → commune nouvelle |
| 35 | Suppression de commune déléguée |
| 41 | Changement de département ou région |
| 50 | Changement de code |
| 70 | Transformation commune associée → commune déléguée |

## Arborescence

```
cog-history/
├── cog_history.py          # Script principal (unique fichier)
├── README.md
├── .gitignore
├── data/                   # Données COG (générées par --download, gitignored)
│   ├── v_mvt_commune_2026.csv
│   ├── v_commune_2026.csv
│   ├── v_departement_2026.csv
│   ├── v_region_2026.csv
│   ├── v_arrondissement_2026.csv
│   └── v_canton_2026.csv
└── html/                   # Visualisations générées (gitignored)
    ├── entrelacs.html
    └── savoie.html
```

## Source des données

Les données proviennent du [Code Officiel Géographique](https://www.insee.fr/fr/information/2560452) publié par l'INSEE. Le fichier clé est `v_mvt_commune` qui recense tous les événements survenus aux communes depuis 1943.

Le `--download` télécharge 6 fichiers du COG :

| Fichier | Contenu |
|---|---|
| `v_mvt_commune` | Événements (fusions, changements de nom/code…) |
| `v_commune` | Liste des communes actuelles |
| `v_departement` | Liste des départements |
| `v_region` | Liste des régions |
| `v_arrondissement` | Liste des arrondissements |
| `v_canton` | Liste des cantons |

## Intégration dans un pipeline Python

```python
from cog_history import MvtDB, Annuaire, Tracer

db = MvtDB("data/v_mvt_commune_2026.csv")
annuaire = Annuaire(Path("data"))

# Historique d'une commune
result = Tracer(db).trace("73010")
print(result["absorbees"])  # communes absorbées (récursif)

# Fiche d'une commune
fiche = annuaire.get("73010")
print(fiche.libelle, fiche.dep_nom, fiche.reg_nom)

# Filtrer les communes d'un département
communes_73 = annuaire.filter(dep="73")
```

## Grandes vagues historiques de modification

Les principaux événements expliquant les changements massifs de codes INSEE :

- **1968** — Réorganisation de la région parisienne : éclatement de la Seine (75) et de la Seine-et-Oise (78) en 7 départements (75, 91, 92, 93, 94, 95 + réduction du 78 aux Yvelines). Des centaines de communes changent de code.
- **1976** — Scission de la Corse : le département 20 devient Corse-du-Sud (2A) et Haute-Corse (2B).
- **2015–2019** — Vague massive de communes nouvelles suite à la loi NOTRe, entraînant la fusion de milliers de communes.

## Licence

MIT
