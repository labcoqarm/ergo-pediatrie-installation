"""
e2 : table communale et départementale à partir des sources brutes.

Sortie : donnees/cache/base.pkl (communes, départements, structures adresseuses, éditions)
"""
import pickle
import re
import sys
import unicodedata
import zipfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import config as C

B = C.BRUT


def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", s)


def arr_to_com(c):
    """Arrondissements de Paris, Lyon, Marseille -> commune."""
    c = str(c).zfill(5)
    if c.startswith("751"): return "75056"
    if c.startswith("6938"): return "69123"
    if c.startswith("132"): return "13055"
    return c


def prank(s, inverse=False):
    r = s.rank(pct=True)
    return 1 - r if inverse else r


def un(motif):
    """Le fichier de donnees/brut qui correspond au motif (le plus récent s'il y en a plusieurs)."""
    f = sorted(B.glob(motif), key=lambda p: p.stat().st_mtime)
    if not f:
        raise FileNotFoundError(f"donnees/brut/{motif} introuvable : lancer e1_telecharger.py")
    return f[-1]


def dans_zip(z, motif):
    noms = [n for n in z.namelist() if re.search(motif, n, re.I) and "meta" not in n.lower()]
    if not noms:
        raise FileNotFoundError(f"{motif} absent de {z.filename}")
    return noms[0]


def communes():
    gpkg = un("adminexpress/**/*.gpkg")
    com = gpd.read_file(gpkg, layer="commune")[["code_insee", "nom_officiel", "code_insee_du_departement", "geometry"]]
    com = com.rename(columns={"code_insee": "codgeo", "nom_officiel": "nom", "code_insee_du_departement": "dep"})
    dep = gpd.read_file(gpkg, layer="departement")[["code_insee", "nom_officiel", "geometry"]]
    dep = dep.rename(columns={"code_insee": "dep", "nom_officiel": "nom_dep"})
    p = com.geometry.representative_point()
    com["x"], com["y"] = p.x, p.y
    return com, dep


def population():
    z = zipfile.ZipFile(un("population/*.zip"))
    pop = pd.read_csv(z.open(dans_zip(z, r"TD_POP1A.*\.csv$")), sep=";", dtype={"CODGEO": str, "AGEPYR10": str})
    pop = pop[pop.NIVGEO == "COM"]
    pop["codgeo"] = pop.CODGEO.map(arr_to_com)
    pop["enf"] = pop.AGEPYR10.isin(["00", "03", "06", "11"]) * pop.NB # 0-17 ans
    return pop.groupby("codgeo").agg(pop22=("NB", "sum"), enf22=("enf", "sum")).reset_index()


def ergos_liberaux():
    r = pd.read_csv(un("rpps/rpps_ergo.csv"), sep="|", dtype=str)
    lib = r[r["mode"].fillna("").str.startswith("Lib") & r.ccom.notna()].copy()
    lib["codgeo"] = lib.ccom.map(arr_to_com)
    lib = lib.drop_duplicates(["id", "codgeo"])
    lib["poids"] = 1 / lib.groupby("id").codgeo.transform("count") # un ergo sur plusieurs sites compte 1
    return lib.groupby("codgeo").poids.sum().rename("ergo_lib").reset_index()


def naissances():
    z = zipfile.ZipFile(un("naissances/*.zip"))
    nais = pd.read_excel(z.open(dans_zip(z, r"\.xlsx$")), sheet_name="COM", dtype={"Code géographique": str})
    nais = nais.rename(columns={"Code géographique": "codgeo"})
    nais.columns = [str(c) for c in nais.columns]
    ans = sorted(int(c) for c in nais.columns if re.fullmatch(r"\d{4}", c))
    for a in ans:
        nais[str(a)] = pd.to_numeric(nais[str(a)], errors="coerce")
    recent = [str(a) for a in ans[-5:]] # cinq dernières années, comparées à dix ans plus tôt
    ancien = [str(a - 10) for a in ans[-5:] if str(a - 10) in nais]
    nais["nais_old"] = nais[ancien].sum(axis=1, min_count=3)
    nais["nais_new"] = nais[recent].sum(axis=1, min_count=3)
    nais["codgeo"] = nais.codgeo.map(arr_to_com)
    return nais.groupby("codgeo")[["nais_old", "nais_new"]].sum().reset_index(), f"{recent[0]}-{recent[-1]}"


def revenus():
    z = zipfile.ZipFile(un("revenus/*.zip"))
    noms = [n for n in z.namelist() if n.lower().endswith(".csv") and "meta" not in n.lower()]
    fn = next((n for n in noms if "disp" in n.lower()), noms[0])
    fil = pd.read_csv(z.open(fn), sep=";", dtype={"CODGEO": str}, low_memory=False, encoding="latin-1")
    med = next(c for c in fil.columns if re.fullmatch(r"Q2\d\d", c)) # médiane du niveau de vie
    fil = fil[["CODGEO", med]].rename(columns={"CODGEO": "codgeo", med: "med_nv"})
    fil["med_nv"] = pd.to_numeric(fil.med_nv.astype(str).str.replace(",", "."), errors="coerce")
    fil["codgeo"] = fil.codgeo.map(arr_to_com)
    return fil.groupby("codgeo").med_nv.mean().reset_index()


def adresseurs():
    rows, geo = [], {}
    with open(un("finess/*.csv"), encoding="latin-1") as f:
        for line in f:
            p = line.rstrip("\n").split(";")
            if p[0] == "structureet" and len(p) > 19 and p[18] in C.CAT_ADRESSEURS:
                rows.append((p[1], p[18], p[13] + p[12]))
            elif p[0] == "geolocalisation" and p[2] and p[3]: # 2 établissements sur 100 000 n'ont pas de coordonnées
                geo[p[1]] = (float(p[2]), float(p[3]))
    fin = pd.DataFrame(rows, columns=["finess", "cat", "ccom"])
    fin["type"] = fin.cat.map(C.CAT_ADRESSEURS)
    fin["x"] = fin.finess.map(lambda k: geo.get(k, (np.nan, np.nan))[0])
    fin["y"] = fin.finess.map(lambda k: geo.get(k, (np.nan, np.nan))[1])
    fin = fin.dropna(subset=["x"])
    return fin[(fin.x > 0) & (fin.x < 1.3e6) & (fin.y > 6.0e6) & (fin.y < 7.2e6)] # métropole, Lambert-93


def drees():
    """Ergos libéraux par département au début et à la fin de la série DREES."""
    dr = pd.read_excel(un("drees/*.xlsx"), sheet_name="Effectifs")
    m = (dr.sexe.str.startswith("0") & dr.tranche_age.str.startswith("0") & dr.secteur_activite.str.startswith("00") & ~dr.departement.str.startswith("00"))
    lib = dr[m & dr.exercice.str.contains("ib", case=False) & ~dr.exercice.str.contains("Ensemble")].copy()
    lib["dep"] = lib.departement.str.split("-").str[0].str.zfill(2)
    fin = max(c for c in lib.columns if re.fullmatch(r"effectif_\d{4}", c))
    lib = lib.groupby("dep")[["effectif_2016", fin]].sum()
    duree = int(fin[-4:]) - 2016
    lib["evol_lib_16_24_pct"] = 100 * (lib[fin] / lib.effectif_2016.replace(0, np.nan) - 1)
    lib["taux_an"] = (lib[fin] - lib.effectif_2016) / duree / lib[fin].replace(0, np.nan)
    return lib[["evol_lib_16_24_pct", "taux_an"]].reset_index(), f"2016-{fin[-4:]}"


def omphale(dep):
    z = zipfile.ZipFile(un("omphale/*.zip"))
    om = pd.read_excel(z.open(dans_zip(z, r"Central.*\.xlsx$")), sheet_name="Population", header=5)
    w = {"[0;5[": 1, "[5;10[": 1, "[10;15[": 1, "[15;20[": 0.6} # 0-17 ≈ 0-14 + 3/5 des 15-19
    om = om[om.TRAGE.isin(w)].copy()
    an = [2022, 2024] + C.ANNEES
    for a in an:
        om[f"P{a}"] = om[f"POP_{a}"] * om.TRAGE.map(w)
        om[f"Q{a}"] = om[f"POP_{a}"] * (om.TRAGE != "[15;20[") # 0-14 ans
    om = om.groupby("ZONE")[[f"P{a}" for a in an] + [f"Q{a}" for a in an]].sum().reset_index()
    om["k"] = om.ZONE.map(norm)
    dk = dep[["dep", "nom_dep"]].copy()
    dk["k"] = dk.nom_dep.map(norm)
    om = om.merge(dk[["k", "dep"]], on="k")
    for a in C.ANNEES:
        om[f"R{a}"] = om[f"P{a}"] / om.P2022
    om["evol_enf_24_35_pct"] = 100 * (om.Q2035 / om.Q2024 - 1)
    return om[["dep", "evol_enf_24_35_pct"] + [f"R{a}" for a in C.ANNEES]]


def run():
    print("=== e2 : base communale ===")
    com, dep = communes()
    com = com.merge(population(), on="codgeo", how="left")
    com = com.merge(ergos_liberaux(), on="codgeo", how="left")
    nais, periode_nais = naissances()
    com = com.merge(nais, on="codgeo", how="left").merge(revenus(), on="codgeo", how="left")
    fin = adresseurs()
    lib, periode_drees = drees()
    om = omphale(dep)
    for c in ["pop22", "enf22", "ergo_lib"]:
        com[c] = com[c].fillna(0)

    # indicateurs départementaux et score départemental
    dg = com.groupby("dep").agg(enf22=("enf22", "sum"), pop22=("pop22", "sum"), ergo_lib=("ergo_lib", "sum")).reset_index()
    rv = com.dropna(subset=["med_nv"])
    rv = rv.groupby("dep").apply(lambda d: np.average(d.med_nv, weights=d.pop22.clip(lower=1))).rename("revenu_med")
    dg = dg.merge(rv.reset_index(), on="dep", how="left")
    fin["dep"] = fin.ccom.str[:2]
    dg = dg.merge(fin.groupby("dep").size().rename("adresseurs").reset_index(), on="dep", how="left")
    dg = dg.merge(lib, on="dep", how="left").merge(om[["dep", "evol_enf_24_35_pct"]], on="dep", how="left")
    dg["dens_lib_10k_enf"] = 1e4 * dg.ergo_lib / dg.enf22
    dg["adresseurs_10k_enf"] = 1e4 * dg.adresseurs.fillna(0) / dg.enf22
    dg["score"] = 100 * (0.35 * prank(dg.dens_lib_10k_enf, inverse=True) + 0.25 * prank(dg.evol_enf_24_35_pct) + 0.15 * prank(dg.revenu_med) + 0.10 * prank(dg.evol_lib_16_24_pct.fillna(dg.evol_lib_16_24_pct.median()), inverse=True) + 0.15 * prank(dg.adresseurs_10k_enf))
    dep = dep.merge(dg.drop(columns=["ergo_lib", "enf22"]), on="dep", how="left")
    dep["rang"] = dep.score.rank(ascending=False, method="min")

    com = com.merge(lib[["dep", "taux_an"]], on="dep", how="left").merge(om.drop(columns="evol_enf_24_35_pct"), on="dep", how="left")
    com["taux_an"] = com.taux_an.fillna(lib.taux_an.median()).clip(0, 0.25)
    editions = dict(naissances=periode_nais, drees=periode_drees)
    pickle.dump(dict(com=com, dep=dep, fin=fin, editions=editions), open(C.CACHE / "base.pkl", "wb"))
    print(f"  {len(com)} communes, {int(com.enf22.sum())} enfants, {com.ergo_lib.sum():.0f} ergos libéraux, {len(fin)} CAMSP/CMPP/SESSAD")
    return True


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
