#!/usr/bin/env python3
"""
cog_history.py — Fiche et historique complet d'une commune française
via le Code Officiel Géographique (COG) de l'INSEE, depuis 1943.

Usage :
    python cog_history.py 01015                     # Fiche + historique
    python cog_history.py 69008                     # Commune sans événement
    python cog_history.py 01015 --depuis 2000       # Filtrer par date
    python cog_history.py 01015 --json              # Sortie JSON
    python cog_history.py --download                # Télécharger les données
    python cog_history.py --stats                   # Stats globales
    python cog_history.py 73010 --html entrelacs.html  # Arbre HTML commune
    python cog_history.py --dep 73 --html savoie.html  # Arbre HTML département
    python cog_history.py --arr 73-1 --html arr1.html  # Arbre HTML arrondissement
    python cog_history.py --canton 73-05 --html can.html  # Arbre HTML canton
"""

import argparse, csv, json, sys, urllib.request, webbrowser
from collections import defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

# ── Config ───────────────────────────────────────────────────────────────────

DATA_DIR = Path(__file__).parent / "data"
DEFAULT_MILLESIME = "2026"

_BASE = {
    "2026": "https://www.insee.fr/fr/statistiques/fichier/8740222",
    "2025": "https://www.insee.fr/fr/statistiques/fichier/8377162",
}
COG_FICHIERS = ["commune", "mvt_commune", "departement", "region", "arrondissement", "canton"]

def _url(millesime, fichier):
    return f"{_BASE[millesime]}/v_{fichier}_{millesime}.csv"

# ── Référentiels ─────────────────────────────────────────────────────────────

MOD_LABELS = {
    10: "Changement de nom", 20: "Création", 21: "Rétablissement",
    30: "Suppression (fusion simple)", 31: "Fusion-association (absorbante)",
    32: "Commune nouvelle", 33: "Fusion-association (absorbée)",
    34: "Fusion-assoc. → commune nouvelle", 35: "Suppression commune déléguée",
    41: "Changement de département/région", 50: "Changement de code",
    70: "Commune associée → déléguée",
}
TYPECOM = {"COM": "Commune", "ARM": "Arrond. municipal",
           "COMA": "Commune associée", "COMD": "Commune déléguée"}
MOD_ABSORPTION = {30, 31, 32, 33, 34}
MOD_IDENTITY = {50, 41}

# ── Style ANSI ───────────────────────────────────────────────────────────────

_T = sys.stdout.isatty()
class S:
    B="\033[1m" if _T else ""; D="\033[2m" if _T else ""; R="\033[0m" if _T else ""
    RD="\033[31m" if _T else ""; GR="\033[32m" if _T else ""; YL="\033[33m" if _T else ""
    BL="\033[34m" if _T else ""; MG="\033[35m" if _T else ""; CY="\033[36m" if _T else ""

def _mod_color(mod):
    if mod in {20, 21}: return S.GR
    if mod in MOD_ABSORPTION | {35}: return S.RD
    if mod == 10: return S.CY
    if mod in MOD_IDENTITY: return S.YL
    return ""

# ── Structures ───────────────────────────────────────────────────────────────

@dataclass
class Evt:
    mod: int; date_eff: str
    typecom_av: str; com_av: str; libelle_av: str
    typecom_ap: str; com_ap: str; libelle_ap: str
    @property
    def mod_label(self): return MOD_LABELS.get(self.mod, f"MOD={self.mod}")
    def to_dict(self):
        d = asdict(self); d["mod_label"] = self.mod_label; return d

@dataclass
class Fiche:
    code: str; libelle: str; typecom: str = ""
    dep_code: str = ""; dep_nom: str = ""
    reg_code: str = ""; reg_nom: str = ""
    arr_code: str = ""; arr_nom: str = ""
    can_code: str = ""; can_nom: str = ""
    comparent: str = ""
    @property
    def typecom_label(self): return TYPECOM.get(self.typecom, self.typecom)
    def to_dict(self): return asdict(self)

# ── Annuaire communes ────────────────────────────────────────────────────────

class Annuaire:
    def __init__(self, data_dir: Path):
        self._fiches: dict[str, Fiche] = {}
        self.dep_names: dict[str, str] = {}
        self.reg_names: dict[str, str] = {}
        self.arr_names: dict[tuple, str] = {}
        self.can_names: dict[tuple, str] = {}
        dep, reg, arr, can = {}, {}, {}, {}
        for path, store, key_cols in [
            ("v_region_*.csv", reg, ("REG",)),
            ("v_departement_*.csv", dep, ("DEP",)),
            ("v_arrondissement_*.csv", arr, ("DEP", "ARR")),
            ("v_canton_*.csv", can, ("DEP", "CAN")),
        ]:
            files = sorted(data_dir.glob(path), reverse=True)
            if not files: continue
            with open(files[0], encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    k = tuple(row.get(c, "") for c in key_cols)
                    store[k if len(k) > 1 else k[0]] = row.get("LIBELLE", row.get("NCCENR", ""))
        self.dep_names, self.reg_names, self.arr_names, self.can_names = dep, reg, arr, can

        com_files = sorted(data_dir.glob("v_commune_*.csv"), reverse=True)
        if not com_files: return
        _prio = {"COM": 0, "ARM": 1, "COMD": 2, "COMA": 3}
        with open(com_files[0], encoding="utf-8") as f:
            for row in csv.DictReader(f):
                code = row.get("COM", "")
                if not code: continue
                tc = row.get("TYPECOM", "")
                if code in self._fiches and _prio.get(tc, 9) >= _prio.get(self._fiches[code].typecom, 9):
                    continue
                d, r, a, c = row.get("DEP",""), row.get("REG",""), row.get("ARR",""), row.get("CAN","")
                self._fiches[code] = Fiche(
                    code=code, libelle=row.get("LIBELLE", ""), typecom=tc,
                    dep_code=d, dep_nom=dep.get(d, ""),
                    reg_code=r, reg_nom=reg.get(r, ""),
                    arr_code=a, arr_nom=arr.get((d, a), ""),
                    can_code=c, can_nom=can.get((d, c), ""),
                    comparent=row.get("COMPARENT", ""),
                )
        print(f"{S.D}Annuaire : {len(self._fiches)} communes{S.R}", file=sys.stderr)

    def get(self, code): return self._fiches.get(code)

    def filter(self, dep=None, arr=None, canton=None):
        """Filtre les communes par département, arrondissement ou canton.
        arr et canton au format 'DEP-CODE' (ex: '73-1', '73-05')."""
        results = []
        for f in self._fiches.values():
            if dep and f.dep_code != dep: continue
            if arr:
                d, a = arr.split("-", 1)
                if f.dep_code != d or f.arr_code != a: continue
            if canton:
                d, c = canton.split("-", 1)
                if f.dep_code != d or f.can_code != c: continue
            results.append(f)
        return results

# ── Base mouvements ──────────────────────────────────────────────────────────

class MvtDB:
    def __init__(self, path: Path):
        self.events = []
        self.by_av: dict[str, list[Evt]] = defaultdict(list)
        self.by_ap: dict[str, list[Evt]] = defaultdict(list)
        if not path.exists():
            print(f"{S.RD}Fichier introuvable : {path}{S.R}", file=sys.stderr)
            print(f"Lancez : python {__file__} --download", file=sys.stderr); sys.exit(1)
        with open(path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                try: mod = int(row.get("MOD", 0))
                except (ValueError, TypeError): continue
                e = Evt(mod=mod, date_eff=row.get("DATE_EFF",""),
                        typecom_av=row.get("TYPECOM_AV",""), com_av=row.get("COM_AV",""),
                        libelle_av=row.get("LIBELLE_AV",""),
                        typecom_ap=row.get("TYPECOM_AP",""), com_ap=row.get("COM_AP",""),
                        libelle_ap=row.get("LIBELLE_AP",""))
                self.events.append(e)
                if e.com_av: self.by_av[e.com_av].append(e)
                if e.com_ap: self.by_ap[e.com_ap].append(e)
        print(f"{S.D}Mouvements : {len(self.events)} événements{S.R}", file=sys.stderr)

    def has(self, code): return code in self.by_av or code in self.by_ap

    def events_for_codes(self, codes: set) -> list[Evt]:
        """Retourne tous les événements impliquant un des codes donnés."""
        seen = set()
        result = []
        for code in codes:
            for e in self.by_av.get(code, []) + self.by_ap.get(code, []):
                eid = id(e)
                if eid not in seen:
                    seen.add(eid)
                    result.append(e)
        return result

# ── Traceur d'historique ─────────────────────────────────────────────────────

class Tracer:
    def __init__(self, db: MvtDB, depuis=None):
        self.db, self.depuis = db, depuis

    def trace(self, code):
        visited = set()
        r = {"code": code, "directs": [], "absorbees": {}, "identites": [code]}
        self._collect(code, r, visited)
        return r

    def _collect(self, code, r, visited):
        if code in visited: return
        visited.add(code)
        for e in self.db.by_av.get(code, []):
            if self._ok(e) and not self._bruit(e): r["directs"].append(e)
            if e.mod in MOD_IDENTITY and e.com_ap and e.com_ap != code:
                if e.com_ap not in r["identites"]: r["identites"].append(e.com_ap)
                self._collect(e.com_ap, r, visited)
        for e in self.db.by_ap.get(code, []):
            if self._ok(e) and not self._bruit(e) and e not in r["directs"]:
                r["directs"].append(e)
            if e.com_av and e.com_av != code and e.mod in MOD_ABSORPTION and e.com_av not in visited:
                r["absorbees"][e.com_av] = self._sub(e.com_av, e, visited)

    def _sub(self, code, evt, visited):
        if code in visited:
            return {"lib": evt.libelle_av, "date": evt.date_eff, "mod": evt.mod,
                    "evts": [], "sub": {}}
        visited.add(code)
        node = {"lib": evt.libelle_av, "date": evt.date_eff, "mod": evt.mod, "evts": [], "sub": {}}
        for e in self.db.by_av.get(code, []):
            if self._ok(e) and not self._bruit(e): node["evts"].append(e)
        for e in self.db.by_ap.get(code, []):
            if e.com_av and e.com_av != code and e.mod in MOD_ABSORPTION and e.com_av not in visited:
                node["sub"][e.com_av] = self._sub(e.com_av, e, visited)
        return node

    @staticmethod
    def _bruit(e):
        return (e.com_av == e.com_ap and e.typecom_av != e.typecom_ap and e.mod in MOD_ABSORPTION)

    def _ok(self, e):
        if self.depuis is None: return True
        try: return int(e.date_eff[:4]) >= self.depuis
        except: return True

# ── Rendu console ────────────────────────────────────────────────────────────

SEP = "═" * 70

def print_fiche(f):
    print(f"\n{S.B}{S.BL}{SEP}{S.R}\n{S.B}  FICHE COMMUNE{S.R}\n{S.BL}{SEP}{S.R}\n")
    lignes = [("Code INSEE", f.code), ("Nom", f.libelle), ("Type", f.typecom_label)]
    if f.dep_code: lignes.append(("Département", f"{f.dep_nom} ({f.dep_code})"))
    if f.reg_code: lignes.append(("Région", f"{f.reg_nom} ({f.reg_code})"))
    if f.arr_nom: lignes.append(("Arrondissement", f"{f.arr_nom} ({f.arr_code})"))
    elif f.arr_code: lignes.append(("Arrondissement", f.arr_code))
    if f.can_nom: lignes.append(("Canton", f"{f.can_nom} ({f.can_code})"))
    elif f.can_code: lignes.append(("Canton", f.can_code))
    if f.comparent and f.comparent != f.code:
        lignes.append(("Commune parente", f.comparent))
    w = max(len(l) for l, _ in lignes)
    for label, val in lignes: print(f"  {S.D}{label.ljust(w)}{S.R}  {val}")
    print()

def print_evt(e, indent=2):
    pad = " " * indent; mc = _mod_color(e.mod)
    av = f"{e.com_av} {e.libelle_av}"
    if e.typecom_av and e.typecom_av != "COM": av += f" ({TYPECOM.get(e.typecom_av, e.typecom_av)})"
    ap = f"{e.com_ap} {e.libelle_ap}"
    if e.typecom_ap and e.typecom_ap != "COM": ap += f" ({TYPECOM.get(e.typecom_ap, e.typecom_ap)})"
    print(f"{pad}{S.B}{e.date_eff or '????'}{S.R}  {mc}[MOD {e.mod:>2}] {e.mod_label}{S.R}")
    print(f"{pad}  {S.D}{av}  →  {ap}{S.R}\n")

def print_absorbed(code, data, depth=1):
    pad = " " * (2 + depth * 4)
    ml = MOD_LABELS.get(data["mod"], f"MOD={data['mod']}")
    print(f"{pad}{S.YL}{'├─' if depth==1 else '└─'} {code} {data['lib']}{S.R}"
          f"  {S.D}(absorbée le {data['date']}, {ml}){S.R}")
    for e in sorted(data.get("evts", []), key=lambda x: x.date_eff):
        print_evt(e, indent=2 + depth * 4 + 4)
    if data.get("sub"):
        print(f"{' '*(2+depth*4+4)}{S.D}Avait elle-même absorbé :{S.R}")
        for sc, sd in sorted(data["sub"].items(), key=lambda x: x[1]["date"]):
            print_absorbed(sc, sd, depth + 1)

def count_abs(d):
    return sum(1 + count_abs(v.get("sub", {})) for v in d.values())

def print_history(r):
    directs = sorted(r["directs"], key=lambda e: e.date_eff)
    if len(r["identites"]) > 1:
        print(f"  {S.D}Identités successives : {' → '.join(r['identites'])}{S.R}\n")
    print(f"{S.B}{S.BL}{SEP}{S.R}")
    if directs:
        print(f"{S.B}  HISTORIQUE ({len(directs)} événement(s)){S.R}\n{S.BL}{SEP}{S.R}\n")
        for e in directs: print_evt(e)
    else:
        print(f"{S.B}  HISTORIQUE{S.R}\n{S.BL}{SEP}{S.R}\n")
        print(f"  {S.GR}Aucun événement enregistré depuis 1943.{S.R}")
        print(f"  {S.D}Ni fusion, ni changement de nom ou de code.{S.R}\n")
    if r["absorbees"]:
        print(f"{S.B}{S.MG}  Communes absorbées ({len(r['absorbees'])}){S.R}\n  {'─'*66}\n")
        for sc, sd in sorted(r["absorbees"].items(), key=lambda x: x[1]["date"]):
            print_absorbed(sc, sd)
    n = count_abs(r["absorbees"])
    print(f"{S.BL}{SEP}{S.R}\n{S.D}  {len(directs)} événement(s), {n} commune(s) absorbée(s){S.R}")
    print(f"{S.BL}{SEP}{S.R}\n")

# ── JSON ─────────────────────────────────────────────────────────────────────

def to_json(r, fiche=None):
    def ser_abs(d):
        return {c: {"libelle": v["lib"], "date_absorption": v["date"], "mod": v["mod"],
                     "evenements": [e.to_dict() for e in v.get("evts",[])],
                     "sous_absorptions": ser_abs(v.get("sub",{}))} for c, v in d.items()}
    return json.dumps({
        "code": r["code"], "fiche": fiche.to_dict() if fiche else None,
        "identites": r["identites"],
        "evenements": [e.to_dict() for e in r["directs"]],
        "absorbees": ser_abs(r["absorbees"]),
    }, ensure_ascii=False, indent=2)

# ── HTML — Collecte des données ──────────────────────────────────────────────

def collect_html_data(codes: list[str], db: MvtDB, annuaire: Annuaire, title: str) -> dict:
    """Construit la structure de données pour la visualisation HTML."""
    code_set = set(codes)

    # Collecter les événements et découvrir les communes fantômes
    raw_events = db.events_for_codes(code_set)
    all_events = []
    ghost_codes = set()

    for e in raw_events:
        # Filtre bruit
        if e.com_av == e.com_ap and e.typecom_av != e.typecom_ap and e.mod in MOD_ABSORPTION:
            continue
        all_events.append(e)
        # Découvrir les codes hors zone impliqués dans des fusions
        if e.com_av and e.com_av not in code_set:
            ghost_codes.add(e.com_av)
        if e.com_ap and e.com_ap not in code_set:
            ghost_codes.add(e.com_ap)

    # Construire la liste des communes
    communes = []
    for code in sorted(code_set | ghost_codes):
        f = annuaire.get(code)
        if f:
            communes.append({"code": code, "name": f.libelle, "type": f.typecom,
                             "dep": f.dep_code, "parent": f.comparent})
        else:
            # Commune fantôme : reconstruire depuis les événements
            name = code
            for e in all_events:
                if e.com_av == code and e.libelle_av: name = e.libelle_av; break
                if e.com_ap == code and e.libelle_ap: name = e.libelle_ap; break
            communes.append({"code": code, "name": name, "type": "?",
                             "dep": "", "parent": "", "ghost": True})

    # Sérialiser les événements
    events_ser = []
    for e in all_events:
        events_ser.append({
            "date": e.date_eff, "mod": e.mod, "mod_label": e.mod_label,
            "com_av": e.com_av, "lib_av": e.libelle_av, "type_av": e.typecom_av,
            "com_ap": e.com_ap, "lib_ap": e.libelle_ap, "type_ap": e.typecom_ap,
        })

    return {"title": title, "communes": communes, "events": events_ser}

# ── HTML — Template & génération ─────────────────────────────────────────────

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%%TITLE%%</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{--bg:#fafaf8;--bg2:#f0efeb;--fg:#1a1a1a;--fg2:#555;--fg3:#888;
--blue:#0E2841;--teal:#1D9E75;--purple:#534AB7;--coral:#D85A30;
--gray:#888780;--cyan:#2A8BAB;--border:#ddd;--row:26px}
@media(prefers-color-scheme:dark){:root{--bg:#1a1a1a;--bg2:#252525;
--fg:#e0dfd8;--fg2:#aaa;--fg3:#777;--border:#444}}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;
background:var(--bg);color:var(--fg);font-size:13px;line-height:1.5}
header{background:var(--blue);color:#fff;padding:16px 24px;display:flex;
align-items:center;gap:16px;flex-wrap:wrap}
header h1{font-size:17px;font-weight:500}
header .stats{font-size:12px;opacity:.7}
.controls{padding:10px 24px;border-bottom:1px solid var(--border);
display:flex;gap:12px;align-items:center;background:var(--bg2);flex-wrap:wrap}
.controls input[type=search]{padding:5px 10px;border:1px solid var(--border);
border-radius:6px;font-size:13px;width:240px;background:var(--bg);color:var(--fg)}
.controls label{font-size:12px;color:var(--fg2);display:flex;align-items:center;gap:4px}
.controls select,.controls input[type=range]{font-size:12px}
.legend{display:flex;gap:14px;font-size:11px;color:var(--fg2)}
.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;vertical-align:middle;margin-right:2px}
#container{overflow:auto;padding:0}
svg text{font-family:inherit}
.bar{cursor:pointer;transition:filter .1s}.bar:hover{filter:brightness(1.15)}
.merge-line{pointer-events:none}
.tooltip{position:fixed;pointer-events:none;opacity:0;transition:opacity .12s;
background:var(--bg);border:1px solid var(--border);border-radius:8px;
padding:8px 12px;font-size:12px;color:var(--fg);max-width:280px;z-index:100;
box-shadow:0 4px 12px rgba(0,0,0,.15);white-space:pre-line;line-height:1.6}
.tooltip.show{opacity:1}
.row-bg:hover{fill:var(--bg2);opacity:1}
</style>
</head>
<body>
<header>
<h1 id="title"></h1>
<span class="stats" id="stats"></span>
</header>
<div class="controls">
<input type="search" id="search" placeholder="Rechercher une commune ou un code…">
<label>Zoom <input type="range" id="zoom" min="0.5" max="4" step="0.1" value="1"></label>
<div class="legend">
<span><i style="background:var(--teal)"></i>Active</span>
<span><i style="background:var(--purple)"></i>Commune nouvelle</span>
<span><i style="background:var(--gray)"></i>Absorbée</span>
<span><i style="background:var(--coral)"></i>Fusion</span>
<span><i style="background:var(--cyan)"></i>Changement nom/code</span>
</div>
</div>
<div id="container"><svg id="timeline"></svg></div>
<div class="tooltip" id="tip"></div>

<script>
const DATA = %%DATA_JSON%%;
const MOD_ABS = new Set([30,31,32,33,34]);
const svg = document.getElementById("timeline");
const tip = document.getElementById("tip");
const NS = "http://www.w3.org/2000/svg";

// ── Preprocess ──
const communeMap = {};
DATA.communes.forEach(c => communeMap[c.code] = c);

// Déterminer les parents (communes ayant absorbé d'autres)
const absorbedInto = {};
const isParent = new Set();
DATA.events.forEach(e => {
  if (MOD_ABS.has(e.mod) && e.com_av !== e.com_ap) {
    absorbedInto[e.com_av] = {into: e.com_ap, date: e.date};
    isParent.add(e.com_ap);
  }
});

// Identifier les communes nouvelles
const communeNouvelle = new Set();
DATA.events.forEach(e => {
  if (e.mod === 32 && e.com_av !== e.com_ap) communeNouvelle.add(e.com_ap);
});

// Trier : COM en premier, regrouper enfants sous parent
function buildOrder() {
  const parents = [];
  const childrenOf = {};
  DATA.communes.forEach(c => {
    const abs = absorbedInto[c.code];
    if (abs && communeMap[abs.into]) {
      if (!childrenOf[abs.into]) childrenOf[abs.into] = [];
      childrenOf[abs.into].push(c);
    } else {
      parents.push(c);
    }
  });
  parents.sort((a, b) => a.code.localeCompare(b.code));
  const ordered = [];
  parents.forEach(p => {
    ordered.push({...p, _depth: 0});
    const ch = (childrenOf[p.code] || []).sort((a,b) => a.code.localeCompare(b.code));
    ch.forEach(c => ordered.push({...c, _depth: 1}));
  });
  // Ajouter les orphelins
  const placed = new Set(ordered.map(c => c.code));
  DATA.communes.forEach(c => {
    if (!placed.has(c.code)) ordered.push({...c, _depth: 0});
  });
  return ordered;
}

let allRows = buildOrder();
let filteredRows = allRows;

// ── Time range ──
let minYear = 2026, maxYear = 1943;
DATA.events.forEach(e => {
  if (!e.date) return;
  const y = parseInt(e.date.substring(0, 4));
  if (y < minYear) minYear = y;
  if (y > maxYear) maxYear = y;
});
minYear = Math.max(1943, Math.floor(minYear / 10) * 10);
maxYear = Math.min(2030, Math.ceil((maxYear + 2) / 10) * 10);
const NOW_YEAR = new Date().getFullYear();

// ── Layout constants ──
const LABEL_W = 100;
const ROW_H = parseInt(getComputedStyle(document.documentElement).getPropertyValue('--row'));
const PAD_TOP = 40;
const PAD_RIGHT = 20;

function yearToX(y, timeW) {
  return LABEL_W + ((y - minYear) / (maxYear - minYear)) * timeW;
}

function dateToYear(d) {
  if (!d) return minYear;
  return parseFloat(d.substring(0, 4)) + parseFloat(d.substring(5, 7)) / 12;
}

// ── Render ──
function render() {
  const zoomVal = parseFloat(document.getElementById("zoom").value);
  const baseTimeW = 600;
  const timeW = baseTimeW * zoomVal;
  const totalW = LABEL_W + timeW + PAD_RIGHT;
  const totalH = PAD_TOP + filteredRows.length * ROW_H + 30;

  svg.setAttribute("width", totalW);
  svg.setAttribute("height", totalH);
  svg.setAttribute("viewBox", `0 0 ${totalW} ${totalH}`);
  svg.innerHTML = "";

  const rowY = {};
  filteredRows.forEach((c, i) => { rowY[c.code] = PAD_TOP + i * ROW_H; });

  // Time axis
  for (let y = minYear; y <= maxYear; y += (maxYear - minYear > 40 ? 10 : 5)) {
    const x = yearToX(y, timeW);
    addLine(x, PAD_TOP - 10, x, totalH - 10, "#ddd", 0.5, "3 3");
    addText(y, x, PAD_TOP - 16, 10, "var(--fg3)", "middle");
  }

  // Key dates vertical lines
  const keyDates = new Set();
  DATA.events.forEach(e => {
    if (e.date && MOD_ABS.has(e.mod)) keyDates.add(e.date.substring(0, 4));
  });

  // Rows
  filteredRows.forEach((c, i) => {
    const y = rowY[c.code];
    const barY = y + 3;
    const barH = ROW_H - 6;

    // Row background
    const bg = addRect(0, y, totalW, ROW_H, "transparent", 0);
    bg.classList.add("row-bg");
    bg.style.opacity = "0";

    // Label (code only, names shown on segments)
    const indent = c._depth ? 16 : 0;
    const prefix = c._depth ? "└ " : "";
    addText(`${prefix}${c.code}`, 6 + indent, y + ROW_H / 2, 11,
      c._depth ? "var(--fg3)" : "var(--fg2)", "start", "central", "400");

    // Build segments: detect name changes on same code
    const abs = absorbedInto[c.code];
    const endYear = abs ? dateToYear(abs.date) : NOW_YEAR;

    // Collect rename events for this code (MOD 10 or MOD 32 where com_av==com_ap and name differs)
    const renames = [];
    DATA.events.forEach(e => {
      if (e.com_av !== c.code || e.com_ap !== c.code) return;
      if (e.lib_av === e.lib_ap) return;
      if (e.mod === 10 || e.mod === 32 || e.mod === 33 || e.mod === 34) {
        renames.push({date: dateToYear(e.date), nameBefore: e.lib_av, nameAfter: e.lib_ap, mod: e.mod});
      }
    });
    renames.sort((a, b) => a.date - b.date);

    // Build segments from renames
    const segments = [];
    if (renames.length === 0) {
      segments.push({name: c.name, from: minYear, to: endYear, isNew: communeNouvelle.has(c.code) && !abs});
    } else {
      // First segment: from start to first rename
      segments.push({name: renames[0].nameBefore, from: minYear, to: renames[0].date, isNew: false});
      // Middle segments
      for (let j = 0; j < renames.length - 1; j++) {
        const isNew = renames[j].mod === 32 || renames[j].mod === 34;
        segments.push({name: renames[j].nameAfter, from: renames[j].date, to: renames[j+1].date, isNew});
      }
      // Last segment: from last rename to end
      const last = renames[renames.length - 1];
      const isNew = last.mod === 32 || last.mod === 34;
      segments.push({name: last.nameAfter, from: last.date, to: endYear, isNew});
    }

    // Render segments
    segments.forEach(seg => {
      const sx1 = yearToX(Math.max(seg.from, minYear), timeW);
      const sx2 = yearToX(Math.min(seg.to, maxYear), timeW);
      const sw = Math.max(2, sx2 - sx1);

      let color = "var(--teal)";
      let opacity = 0.6;
      if (abs && seg.to <= endYear && !seg.isNew) { color = "var(--gray)"; opacity = 0.4; }
      if (seg.isNew) { color = "var(--purple)"; opacity = 0.7; }
      if (c.ghost) { color = "var(--fg3)"; opacity = 0.3; }

      const bar = addRect(sx1, barY, sw, barH, color, opacity, 3);
      bar.classList.add("bar");

      let tipText = `${c.code} ${seg.name}`;
      tipText += `\n${Math.round(seg.from)} – ${seg.to >= NOW_YEAR ? "auj." : Math.round(seg.to)}`;
      if (abs && seg.to <= endYear + 0.1) tipText += `\nAbsorbée → ${abs.into} le ${abs.date}`;
      bar.dataset.tip = tipText;

      // Name label on segment if wide enough
      if (sw > 40) {
        const lbl = addText(truncate(seg.name, Math.floor(sw / 7)),
          sx1 + 4, barY + barH / 2, 9,
          seg.isNew || c.ghost ? "rgba(255,255,255,.85)" : "rgba(255,255,255,.8)",
          "start", "central", "400");
        lbl.style.pointerEvents = "none";
      }
    });

    // Event markers on bar (non-rename events only, to avoid clutter)
    DATA.events.forEach(e => {
      if (e.com_av !== c.code && e.com_ap !== c.code) return;
      if (!e.date) return;
      // Skip self-rename events (already shown as segment boundaries)
      if (e.com_av === c.code && e.com_ap === c.code && e.lib_av !== e.lib_ap) return;
      const eYear = dateToYear(e.date);
      const ex = yearToX(eYear, timeW);
      const barEndX = yearToX(Math.min(endYear, maxYear), timeW);
      const barStartX = yearToX(minYear, timeW);
      if (ex < barStartX || ex > barEndX) return;

      let mc = "var(--coral)";
      if (e.mod === 10) mc = "var(--cyan)";
      if (e.mod === 50 || e.mod === 41) mc = "var(--cyan)";
      if (e.mod === 20 || e.mod === 21) mc = "var(--teal)";

      const marker = addCircle(ex, barY + barH / 2, 3, mc, 0.9);
      marker.dataset.tip = `${e.date}\n${e.mod_label}\n${e.com_av} ${e.lib_av} → ${e.com_ap} ${e.lib_ap}`;
      marker.style.cursor = "pointer";
    });
  });

  // Merge lines
  DATA.events.forEach(e => {
    if (!MOD_ABS.has(e.mod) || e.com_av === e.com_ap) return;
    if (!(e.com_av in rowY) || !(e.com_ap in rowY)) return;

    const eYear = parseFloat(e.date.substring(0, 4)) + parseFloat(e.date.substring(5, 7))/12;
    const x = yearToX(eYear, timeW);
    const y1 = rowY[e.com_av] + ROW_H / 2;
    const y2 = rowY[e.com_ap] + ROW_H / 2;
    const dist = Math.abs(y2 - y1);
    const cpx = x + Math.min(30, dist * 0.3);

    const path = document.createElementNS(NS, "path");
    path.setAttribute("d", `M${x} ${y1} C${cpx} ${y1} ${cpx} ${y2} ${x} ${y2}`);
    path.setAttribute("fill", "none");
    path.setAttribute("stroke", "var(--coral)");
    path.setAttribute("stroke-width", "1.2");
    path.setAttribute("opacity", "0.35");
    path.classList.add("merge-line");
    svg.appendChild(path);
  });

  // Tooltip handlers
  svg.querySelectorAll("[data-tip]").forEach(el => {
    el.addEventListener("mouseenter", ev => {
      tip.textContent = el.dataset.tip;
      tip.classList.add("show");
      moveTip(ev);
    });
    el.addEventListener("mousemove", moveTip);
    el.addEventListener("mouseleave", () => tip.classList.remove("show"));
  });
}

function moveTip(ev) {
  tip.style.left = (ev.clientX + 12) + "px";
  tip.style.top = (ev.clientY - 10) + "px";
}

// ── SVG helpers ──
function addRect(x, y, w, h, fill, opacity, rx) {
  const r = document.createElementNS(NS, "rect");
  r.setAttribute("x", x); r.setAttribute("y", y);
  r.setAttribute("width", w); r.setAttribute("height", h);
  r.setAttribute("fill", fill); r.setAttribute("opacity", opacity);
  if (rx) r.setAttribute("rx", rx);
  svg.appendChild(r); return r;
}
function addLine(x1, y1, x2, y2, stroke, sw, dash) {
  const l = document.createElementNS(NS, "line");
  l.setAttribute("x1",x1);l.setAttribute("y1",y1);
  l.setAttribute("x2",x2);l.setAttribute("y2",y2);
  l.setAttribute("stroke",stroke);l.setAttribute("stroke-width",sw);
  if (dash) l.setAttribute("stroke-dasharray", dash);
  svg.appendChild(l); return l;
}
function addText(text, x, y, size, fill, anchor, db, weight) {
  const t = document.createElementNS(NS, "text");
  t.setAttribute("x",x);t.setAttribute("y",y);
  t.setAttribute("font-size",size);t.setAttribute("fill",fill);
  t.setAttribute("text-anchor",anchor||"start");
  if (db) t.setAttribute("dominant-baseline", db);
  if (weight) t.setAttribute("font-weight", weight);
  t.textContent = text;
  svg.appendChild(t); return t;
}
function addCircle(cx, cy, r, fill, opacity) {
  const c = document.createElementNS(NS, "circle");
  c.setAttribute("cx",cx);c.setAttribute("cy",cy);c.setAttribute("r",r);
  c.setAttribute("fill",fill);c.setAttribute("opacity",opacity);
  svg.appendChild(c); return c;
}
function truncate(s, n) { return s.length > n ? s.substring(0, n-1) + "…" : s; }

// ── Controls ──
document.getElementById("search").addEventListener("input", function() {
  const q = this.value.toLowerCase().trim();
  if (!q) { filteredRows = allRows; }
  else {
    const matched = new Set();
    allRows.forEach(c => {
      if (c.code.includes(q) || c.name.toLowerCase().includes(q)) matched.add(c.code);
    });
    // Also include parents of matched children and children of matched parents
    allRows.forEach(c => {
      const abs = absorbedInto[c.code];
      if (abs && matched.has(abs.into)) matched.add(c.code);
      if (matched.has(c.code) && abs) matched.add(abs.into);
    });
    filteredRows = allRows.filter(c => matched.has(c.code));
  }
  render();
});
document.getElementById("zoom").addEventListener("input", render);

// ── Init ──
document.getElementById("title").textContent = DATA.title;
const nActive = DATA.communes.filter(c => !absorbedInto[c.code] && c.type === "COM").length;
const nAbsorbed = Object.keys(absorbedInto).length;
document.getElementById("stats").textContent =
  `${DATA.communes.length} communes · ${nActive} actives · ${nAbsorbed} absorbées · ${DATA.events.length} événements`;
render();
</script>
</body>
</html>"""


def generate_html(data: dict, output: Path):
    """Génère le fichier HTML de visualisation et l'ouvre dans le navigateur."""
    html = HTML_TEMPLATE.replace("%%TITLE%%", data["title"])
    html = html.replace("%%DATA_JSON%%", json.dumps(data, ensure_ascii=False))
    output.write_text(html, encoding="utf-8")
    print(f"{S.GR}✓{S.R} HTML généré : {output} ({len(data['communes'])} communes)")
    webbrowser.open(output.resolve().as_uri())
    print(f"{S.D}  Ouverture dans le navigateur…{S.R}")

# ── Téléchargement ───────────────────────────────────────────────────────────

def download(millesime=DEFAULT_MILLESIME):
    if millesime not in _BASE:
        print(f"{S.RD}Millésime inconnu. Choix : {', '.join(_BASE)}{S.R}"); sys.exit(1)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Téléchargement COG {millesime}…\n")
    ok = 0
    for fic in COG_FICHIERS:
        url = _url(millesime, fic)
        dest = DATA_DIR / f"v_{fic}_{millesime}.csv"
        if dest.exists():
            print(f"  {S.D}⊘ {dest.name} (déjà présent){S.R}"); ok += 1; continue
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "COGHistory/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                content = resp.read()
            dest.write_bytes(content)
            print(f"  {S.GR}✓{S.R} {dest.name} ({len(content)/1024:.0f} Ko)"); ok += 1
        except Exception as e:
            print(f"  {S.RD}✗{S.R} {dest.name} — {e}")
    print(f"\n{ok}/{len(COG_FICHIERS)} fichiers prêts.")

def find_mvt():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    c = sorted(DATA_DIR.glob("v_mvt_commune_*.csv"), reverse=True)
    if c: return c[0]
    print(f"{S.RD}Données absentes. Lancez : python {__file__} --download{S.R}", file=sys.stderr)
    sys.exit(1)

# ── Stats ────────────────────────────────────────────────────────────────────

def show_stats(db):
    mc = defaultdict(int); yrs = set()
    for e in db.events:
        mc[e.mod] += 1
        if e.date_eff and len(e.date_eff) >= 4: yrs.add(e.date_eff[:4])
    print(f"\n{S.B}Statistiques COG{S.R}")
    print(f"  {len(db.events):,} événements  ·  {min(yrs)}–{max(yrs)}\n")
    for mod, n in sorted(mc.items()):
        print(f"  MOD {mod:>2} │ {n:>6,} │ {MOD_LABELS.get(mod, '?')}")
    print()

# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(
        description="Fiche et historique d'une commune (COG INSEE)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples :
  %(prog)s 01015                          Fiche + historique
  %(prog)s 73010 --html entrelacs.html    Arbre HTML d'une commune
  %(prog)s --dep 73 --html savoie.html    Arbre HTML d'un département
  %(prog)s --arr 73-1 --html arr.html     Arbre HTML d'un arrondissement
  %(prog)s --canton 73-05 --html can.html Arbre HTML d'un canton
        """)
    p.add_argument("code_insee", nargs="?", help="Code INSEE (ex: 01015, 69008)")
    p.add_argument("--depuis", type=int, metavar="ANNEE")
    p.add_argument("--json", action="store_true")
    p.add_argument("--download", action="store_true")
    p.add_argument("--millesime", default=DEFAULT_MILLESIME, choices=_BASE.keys())
    p.add_argument("--data", type=Path, metavar="FICHIER", help="CSV mvtcommune custom")
    p.add_argument("--stats", action="store_true")
    p.add_argument("--html", metavar="FICHIER", help="Générer une visualisation HTML")
    p.add_argument("--dep", metavar="DEP", help="Département (ex: 73)")
    p.add_argument("--arr", metavar="DEP-ARR", help="Arrondissement (ex: 73-1)")
    p.add_argument("--canton", metavar="DEP-CAN", help="Canton (ex: 73-05)")
    a = p.parse_args()

    if a.download:
        download(a.millesime)
        if not a.code_insee and not a.stats and not a.html: return

    mvt_path = a.data or find_mvt()
    db = MvtDB(mvt_path)
    annuaire = Annuaire(mvt_path.parent)

    if a.stats:
        show_stats(db)
        if not a.code_insee and not a.html: return

    # ── Mode HTML ──
    if a.html:
        html_dir = Path(__file__).parent / "html"
        html_dir.mkdir(parents=True, exist_ok=True)
        output = html_dir / Path(a.html).name
        if a.dep:
            nom = annuaire.dep_names.get(a.dep, a.dep)
            fiches = annuaire.filter(dep=a.dep)
            title = f"Département {nom} ({a.dep})"
        elif a.arr:
            d, ar = a.arr.split("-", 1)
            nom = annuaire.arr_names.get((d, ar), a.arr)
            fiches = annuaire.filter(arr=a.arr)
            title = f"Arrondissement {nom} ({a.arr})"
        elif a.canton:
            d, ca = a.canton.split("-", 1)
            nom = annuaire.can_names.get((d, ca), a.canton)
            fiches = annuaire.filter(canton=a.canton)
            title = f"Canton {nom} ({a.canton})"
        elif a.code_insee:
            code = a.code_insee.strip().zfill(5)
            fiche = annuaire.get(code)
            nom = fiche.libelle if fiche else code
            # Inclure la commune + toutes celles absorbées
            tracer = Tracer(db, depuis=a.depuis)
            r = tracer.trace(code)
            all_codes = [code] + list(r["absorbees"].keys())
            # Ajouter récursivement les sous-absorptions
            def collect_subs(d):
                for k, v in d.items():
                    all_codes.append(k)
                    collect_subs(v.get("sub", {}))
            collect_subs(r["absorbees"])
            fiches = [annuaire.get(c) for c in set(all_codes) if annuaire.get(c)]
            title = f"{code} {nom}"
        else:
            print(f"{S.RD}Spécifiez un code, --dep, --arr ou --canton avec --html{S.R}")
            sys.exit(1)

        if not fiches:
            print(f"{S.RD}Aucune commune trouvée pour ce filtre.{S.R}"); sys.exit(1)

        codes = [f.code for f in fiches]
        data = collect_html_data(codes, db, annuaire, title)
        generate_html(data, output)
        return

    # ── Mode CLI classique ──
    if not a.code_insee: p.print_help(); return

    code = a.code_insee.strip().zfill(5)
    fiche = annuaire.get(code)

    if not fiche and not db.has(code):
        print(f"{S.RD}Code INSEE '{code}' introuvable.{S.R}")
        print(f"{S.D}Vérifiez le code ou changez de millésime.{S.R}"); sys.exit(1)

    r = Tracer(db, depuis=a.depuis).trace(code)

    if a.json:
        # En JSON, inclure la fiche du successeur si le code est historique
        if not fiche and len(r["identites"]) > 1:
            fiche = annuaire.get(r["identites"][-1])
        print(to_json(r, fiche))
    else:
        if fiche:
            print_fiche(fiche)
        else:
            nom = next((e.libelle_av for e in r["directs"] if e.com_av == code and e.libelle_av), code)
            print(f"\n{S.B}{S.YL}  {code} — {nom}{S.R}")

            # Si succession connue → afficher la chaîne et la fiche actuelle
            if len(r["identites"]) > 1:
                chain = r["identites"]
                print(f"  {S.D}Code historique, remplacé par :{S.R}")
                for i in range(len(chain) - 1):
                    av, ap = chain[i], chain[i + 1]
                    # Trouver la date et le motif
                    for e in r["directs"]:
                        if e.com_av == av and e.com_ap == ap and e.mod in MOD_IDENTITY:
                            print(f"  {S.CY}  {av} → {ap}  ({e.date_eff}, {e.mod_label}){S.R}")
                            break
                # Fiche de la commune actuelle
                successor = annuaire.get(chain[-1])
                if successor:
                    print(f"\n  {S.B}Commune actuelle :{S.R}")
                    print_fiche(successor)
                else:
                    print()
            else:
                print(f"  {S.D}(absente de l'annuaire actuel — probablement disparue){S.R}\n")
        print_history(r)

if __name__ == "__main__":
    main()
