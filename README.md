# COG-History

Outil en ligne de commande pour retracer l'**historique complet des communes françaises** à partir du [Code Officiel Géographique](https://www.insee.fr/fr/information/2560452) (COG) de l'INSEE : fusions, scissions, changements de nom, changements de code, communes nouvelles, etc., depuis 1943.

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![Licence](https://img.shields.io/badge/licence-MIT-green)
![Dépendances](https://img.shields.io/badge/dépendances-aucune-brightgreen)

---

## Fonctionnalités

- **Fiche commune** — nom, type (COM/COMD/COMA/ARM), département, région, arrondissement, canton, commune parente
- **Historique complet** — tous les événements depuis 1943 (fusions, changements de nom, de code, de département…)
- **Récursion sur les absorptions** — remonte l'historique de chaque commune absorbée, y compris les sous-absorptions
- **Codes historiques** — un ancien code (ex. `75001` → `94002`) affiche la chaîne de succession avec dates et la fiche de la commune actuelle
- **Recherche par nom** — trouver un code INSEE à partir d'un nom de commune
- **Enrichissement CSV/XLSX** — ajouter les infos communales à un fichier tabulaire en une commande
- **Visualisation HTML** — frise chronologique interactive par commune, canton, arrondissement ou département
- **Zéro dépendance** — uniquement la bibliothèque standard Python (openpyxl optionnel pour les fichiers Excel)

## Installation

```bash
git clone https://github.com/GohuFR/COG-History.git
cd COG-History
```

Aucune dépendance obligatoire. Python 3.10+ requis. Pour le support XLSX (optionnel) :

```bash
pip install openpyxl
```

## Démarrage rapide

```bash
# 1. Télécharger les données COG depuis l'INSEE (~6 fichiers CSV)
python cog_history.py --download

# 2. Consulter l'historique d'une commune
python cog_history.py 73010
```

## Utilisation

### Fiche et historique d'une commune

```bash
python cog_history.py 01015              # Arboys en Bugey (commune nouvelle)
python cog_history.py 69008              # Lyon 8e — commune sans événement
python cog_history.py 75001              # Code historique → succession vers 94002
python cog_history.py 49018 --depuis 2000  # Filtrer depuis 2000
python cog_history.py 73010 --json         # Sortie JSON
```

### Recherche par nom

```bash
python cog_history.py --nom "Entrelacs"
python cog_history.py --nom "saint germain"    # Insensible casse et accents
```

Retourne la liste des communes correspondantes avec leur code, département, type et nombre d'événements.

### Enrichissement de fichiers CSV/XLSX

Ajoute automatiquement 10 colonnes d'informations communales à un fichier contenant des codes INSEE :

```bash
python cog_history.py --enrichir codes.csv --col code_insee
python cog_history.py --enrichir bdni.xlsx --col INSEE --out enrichi.xlsx
```

Colonnes ajoutées : `cog_nom`, `cog_type`, `cog_departement`, `cog_dep_code`, `cog_region`, `cog_arrondissement`, `cog_canton`, `cog_nb_evenements`, `cog_nb_absorbees`, `cog_code_actuel`.

Pour les codes historiques (ex. 75001), le champ `cog_code_actuel` contient le code successeur et les infos renvoyées sont celles de la commune actuelle.

### Visualisation HTML interactive

Génère une frise chronologique dans un fichier HTML autonome, sauvegardé dans le dossier `html/` :

```bash
python cog_history.py 73010 --html entrelacs.html          # Une commune
python cog_history.py --dep 73 --html savoie.html          # Un département
python cog_history.py --arr 73-1 --html arr_chambery.html   # Un arrondissement
python cog_history.py --canton 73-05 --html canton.html     # Un canton
```

Le fichier HTML s'ouvre automatiquement dans le navigateur. Il inclut :

- Une barre par commune, **segmentée selon les changements de nom** (ex. Albens → Entrelacs)
- Un code couleur : vert = active, violet = commune nouvelle, gris = absorbée
- Des **lignes de fusion** (orange) reliant les communes absorbées à leur cible
- Des **lignes de succession de code** (tirets cyan) pour les changements de département/code
- Des marqueurs au survol pour chaque événement
- Un champ de recherche et un zoom
- Le support du dark mode

### Statistiques globales

```bash
python cog_history.py --stats
```

### Options complètes

| Option | Description |
|---|---|
| `<CODE_INSEE>` | Code INSEE à rechercher (ex: `01015`, `75056`) |
| `--nom NOM` | Rechercher par nom de commune |
| `--enrichir FICHIER` | Enrichir un CSV/XLSX avec les infos communales |
| `--col COLONNE` | Colonne code INSEE dans le fichier (défaut: `code_insee`) |
| `--out FICHIER` | Fichier de sortie (enrichir / HTML) |
| `--depuis ANNEE` | Filtrer les événements à partir d'une année |
| `--json` | Sortie JSON |
| `--html FICHIER` | Générer une visualisation HTML (dans `html/`) |
| `--dep DEP` | Filtrer par département (ex: `73`) |
| `--arr DEP-ARR` | Filtrer par arrondissement (ex: `73-1`) |
| `--canton DEP-CAN` | Filtrer par canton (ex: `73-05`) |
| `--download` | Télécharger les fichiers COG depuis l'INSEE |
| `--millesime 2025\|2026` | Choisir le millésime COG (défaut: 2026) |
| `--data FICHIER` | Utiliser un fichier `mvtcommune` CSV personnalisé |
| `--stats` | Statistiques globales de la base |

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
COG-History/
├── cog_history.py          # Script principal
├── README.md
├── LICENSE
├── .gitignore
├── data/                   # Données COG (--download, gitignored)
│   ├── v_mvt_commune_2026.csv
│   ├── v_commune_2026.csv
│   ├── v_departement_2026.csv
│   ├── v_region_2026.csv
│   ├── v_arrondissement_2026.csv
│   └── v_canton_2026.csv
└── html/                   # Visualisations générées (gitignored)
```

## Intégration Python

```python
from cog_history import MvtDB, Annuaire, Tracer
from pathlib import Path

db = MvtDB("data/v_mvt_commune_2026.csv")
annuaire = Annuaire(Path("data"))

# Historique d'une commune
result = Tracer(db).trace("73010")
print(result["absorbees"])

# Fiche
fiche = annuaire.get("73010")
print(fiche.libelle, fiche.dep_nom, fiche.reg_nom)

# Recherche par nom
for f in annuaire.search_name("Entrelacs"):
    print(f.code, f.libelle)

# Filtrer par département
communes_73 = annuaire.filter(dep="73")
```

## Source des données

Les données proviennent du [Code Officiel Géographique](https://www.insee.fr/fr/information/2560452) publié par l'INSEE. Le `--download` télécharge 6 fichiers : `v_mvt_commune` (événements), `v_commune`, `v_departement`, `v_region`, `v_arrondissement`, `v_canton`.

## Grandes vagues historiques

- **1968** — Réorganisation de la région parisienne : éclatement de la Seine (75) et de la Seine-et-Oise (78) en 7 départements
- **1976** — Scission de la Corse : département 20 → 2A et 2B
- **2015–2019** — Vague massive de communes nouvelles suite à la loi NOTRe

## Licence

MIT
