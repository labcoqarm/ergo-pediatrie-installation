"""
e4 : zones de chalandise, score communal, projections 2030-2035, intercommunalités.

Sorties : donnees/cache/scores.pkl, resultats/ergo_pediatrie.gpkg (communes, departements, epci), resultats/*.csv (classements, projections)
"""
import pickle
import shutil
import sys
import tempfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix

sys.path.insert(0, str(Path(__file__).parent))
import config as C
from e2_base import arr_to_com, prank, un

CSV = dict(index=False, sep=";", decimal=",", encoding="utf-8-sig")


def voisinage(com):
    """Poids de chaque commune dans la zone d'une autre : 1 jusqu'à ZONE_PLEIN minutes de route (recalées), puis décroissance linéaire jusqu'à 0 à ZONE_MAX. Évite qu'une minute de plus ou de moins fasse entrer ou sortir une ville entière de la zone."""
    z = np.load(C.CACHE / "matrice.npz")
    I, J, T = z["i"], z["j"], z["t"].astype(float)
    dens = com.pop22.to_numpy() / (com.geometry.area.to_numpy() / 1e6)
    pen = np.where(dens > 2000, C.URBAIN, 0.0)
    t = T * C.CALIB + pen[I] + pen[J]
    t[I == J] = np.minimum(t[I == J], 10) # sa propre commune est toujours dans la zone
    w = np.clip((C.ZONE_MAX - t) / (C.ZONE_MAX - C.ZONE_PLEIN), 0, 1)
    k = w > 0
    n = len(com)
    M = csr_matrix((w[k], (I[k], J[k])), shape=(n, n))
    M = M.maximum(M.T)
    M.setdiag(1)
    return M


def communes(com, fin):
    M = voisinage(com)
    enf, sup = com.enf22.to_numpy(), com.ergo_lib.to_numpy()
    autour = M @ enf
    R = np.where(sup > 0, sup / np.maximum(autour, 1), 0) # 2SFCA pondéré, comme l'APL
    com["apl_ergo_10k"] = (M @ R) * 1e4
    com["enf_zone"] = autour
    com["ergo_zone"] = M @ sup
    for c in ["nais_old", "nais_new"]:
        com[c + "_zone"] = M @ com[c].fillna(0).to_numpy()
    com["evol_nais_pct"] = 100 * (com.nais_new_zone / com.nais_old_zone.replace(0, np.nan) - 1)
    med = com.med_nv.fillna(0).to_numpy()
    poids = com.med_nv.notna().to_numpy() * com.pop22.to_numpy()
    num, den = M @ (med * poids), M @ poids
    com["revenu_zone"] = np.where(den > 0, num / np.maximum(den, 1), np.nan)
    nb = fin.assign(codgeo=fin.ccom.map(arr_to_com)).groupby("codgeo").size().reindex(com.codgeo).fillna(0).to_numpy()
    com["adresseurs_zone"] = M @ nb

    # enfants projetés : tendance Omphale du département, corrigée par les naissances du bassin (±15 %)
    nd = com.groupby("dep")[["nais_old", "nais_new"]].sum()
    rdep = com.dep.map(nd.nais_new / nd.nais_old)
    f = ((com.nais_new_zone / com.nais_old_zone.replace(0, np.nan)) / rdep).clip(0.85, 1.15).fillna(1)
    for a, e in zip(C.ANNEES, [0.5, 1.0]):
        com[f"enf{a}"] = com.enf22 * com[f"R{a}"] * f ** e

    # besoin = enfants × densité nationale actuelle d'ergos libéraux
    ref = com.ergo_lib.sum() / com.enf22.sum()
    for a in C.ANNEES:
        enf_a = com[f"enf{a}"].to_numpy()
        dem = M @ enf_a
        for sc, offre in [("const", sup), ("tend", sup * (1 + com.taux_an.to_numpy() * (a - 2026)))]:
            acc = M @ np.where(offre > 0, offre / np.maximum(dem, 1), 0)
            com[f"couv_{sc}_{a}"] = 100 * acc / ref
            com[f"manque_{sc}_{a}"] = (ref - acc) * dem
        com[f"besoin_{a}"] = enf_a * ref
        com[f"offre_tend_{a}"] = com.ergo_lib * (1 + com.taux_an * (a - 2026))
    com["besoin_2026"] = com.enf22 * ref

    com["score"] = 100 * (0.35 * prank(com.apl_ergo_10k, inverse=True) + 0.20 * com.enf_zone.clip(upper=30000) / 30000 + 0.15 * prank(com.evol_nais_pct.fillna(com.evol_nais_pct.median())) + 0.15 * prank(com.revenu_zone.fillna(com.revenu_zone.median())) + 0.15 * prank(com.adresseurs_zone))
    # sous 2 000 enfants dans la zone, les rapports portent sur trois fois rien (+500 % de naissances, 4 000 % du besoin couvert)
    petit = com.enf_zone < C.MARCHE_MIN
    com.loc[petit, ["score", "apl_ergo_10k", "evol_nais_pct", "revenu_zone"]] = np.nan
    com.loc[petit, [c for c in com.columns if c.startswith("couv_")]] = np.nan
    print(f"  Densité nationale : {ref * 1e4:.2f} ergos libéraux pour 10 000 enfants ; {int(M.nnz)} paires à moins de {C.ZONE_MAX:.0f} min ; {int(com.score.notna().sum())} communes notées")
    return com, ref


def departements(com, dep):
    agg = {"enf22": "sum", "ergo_lib": "sum", "besoin_2026": "sum", "taux_an": "first"}
    for a in C.ANNEES:
        agg[f"enf{a}"] = "sum"
        agg[f"besoin_{a}"] = "sum"
    d = com.groupby("dep").agg(agg)
    for a in C.ANNEES:
        d[f"offre_tend_{a}"] = d.ergo_lib * (1 + d.taux_an * (a - 2026))
        d[f"solde_const_{a}"] = d.ergo_lib - d[f"besoin_{a}"]
        d[f"solde_tend_{a}"] = d[f"offre_tend_{a}"] - d[f"besoin_{a}"]
    d["solde_2026"] = d.ergo_lib - d.besoin_2026
    return dep.merge(d.drop(columns="taux_an").reset_index(), on="dep", how="left")


def intercos(com):
    gp = un("adminexpress/**/*.gpkg")
    cm = gpd.read_file(gp, layer="commune", ignore_geometry=True)[["code_insee", "codes_siren_des_epci"]]
    cm["epci"] = cm.codes_siren_des_epci.astype(str).str.split("/").str[0]
    ep = gpd.read_file(gp, layer="epci")[["code_siren", "nom_officiel", "geometry"]]
    ep = ep.rename(columns={"code_siren": "epci", "nom_officiel": "nom_epci"})
    c = com.merge(cm[["code_insee", "epci"]], left_on="codgeo", right_on="code_insee", how="left")
    c["w"] = c.enf22.where(c.score.notna(), 0)
    c["sw"] = c.score.fillna(0) * c.w
    c["popr"] = c.pop22.where(c.med_nv.notna(), 0)
    c["revw"] = c.med_nv.fillna(0) * c.popr
    s = {k: (k, "sum") for k in ["pop22", "enf22", "enf2030", "enf2035", "ergo_lib", "besoin_2035", "offre_tend_2035", "nais_old", "nais_new", "sw", "w", "revw", "popr"]}
    e = c.groupby("epci").agg(**s, dep=("dep", "first"), n_com=("codgeo", "count")).reset_index()
    e["score"] = (e.sw / e.w.replace(0, np.nan)).round(1)
    e["dens_lib_10k_enf"] = 1e4 * e.ergo_lib / e.enf22.replace(0, np.nan)
    e["evol_enf_22_35_pct"] = 100 * (e.enf2035 / e.enf22.replace(0, np.nan) - 1)
    e["evol_nais_pct"] = 100 * (e.nais_new / e.nais_old.replace(0, np.nan) - 1)
    e["revenu_med"] = e.revw / e.popr.replace(0, np.nan)
    e["solde_const_2035"] = e.ergo_lib - e.besoin_2035
    e["solde_tend_2035"] = e.offre_tend_2035 - e.besoin_2035
    e["solde_tend_pct"] = 100 * e.solde_tend_2035 / e.besoin_2035.replace(0, np.nan)
    petite = e.enf22 < C.MARCHE_MIN # même règle que pour les communes
    e.loc[petite, ["dens_lib_10k_enf", "solde_tend_pct", "evol_nais_pct"]] = np.nan
    ge = ep.merge(e.drop(columns=["sw", "w", "revw", "popr"]), on="epci", how="inner")
    ge["rang"] = ge.score.rank(ascending=False, method="min")
    ge["rang_hors_idf"] = ge[~ge.dep.isin(C.IDF)].score.rank(ascending=False, method="min")
    return ge


def ecrire(com, dep, ep):
    cols_c = ["codgeo", "nom", "dep", "pop22", "enf22", "enf2030", "enf2035", "ergo_lib", "enf_zone", "ergo_zone", "apl_ergo_10k", "evol_nais_pct", "revenu_zone", "adresseurs_zone", "score", "besoin_2026", "besoin_2030", "besoin_2035", "offre_tend_2030", "offre_tend_2035", "couv_const_2030", "couv_const_2035", "couv_tend_2030", "couv_tend_2035", "manque_const_2035", "manque_tend_2035"]
    gc = gpd.GeoDataFrame(com[cols_c + ["geometry"]], geometry="geometry", crs="EPSG:2154")
    tmp = Path(tempfile.mkdtemp()) / "g.gpkg"
    gc.to_file(tmp, layer="communes", driver="GPKG")
    gpd.GeoDataFrame(dep, geometry="geometry", crs="EPSG:2154").to_file(tmp, layer="departements", driver="GPKG")
    ep.to_file(tmp, layer="epci", driver="GPKG")
    shutil.copyfile(tmp, C.OUT / "ergo_pediatrie.gpkg")

    top = gc.drop(columns="geometry").dropna(subset=["score"]).query("pop22 >= 2000").sort_values("score", ascending=False)
    top.head(100).round(2).to_csv(C.OUT / "top100_communes.csv", **CSV)
    h = top[~top.dep.isin(C.IDF)].head(200).copy()
    h.insert(0, "rang_hors_idf", range(1, len(h) + 1))
    h.round(2).to_csv(C.OUT / "top200_communes_hors_IDF.csv", **CSV)

    d = pd.DataFrame(dep.drop(columns="geometry"))
    cols_d = ["rang", "dep", "nom_dep", "score", "dens_lib_10k_enf", "evol_enf_24_35_pct", "revenu_med", "evol_lib_16_24_pct", "adresseurs_10k_enf", "ergo_lib", "enf22", "besoin_2035", "solde_const_2035", "solde_tend_2035"]
    d.sort_values("score", ascending=False)[cols_d].round(2).to_csv(C.OUT / "classement_departements.csv", **CSV)
    dh = d[~d.dep.isin(C.IDF)].copy()
    dh["rang_hors_idf"] = dh.score.rank(ascending=False, method="min")
    dh.sort_values("rang_hors_idf")[["rang_hors_idf"] + cols_d[1:]].round(2).to_csv(C.OUT / "classement_departements_hors_IDF.csv", **CSV)
    cols_p = ["dep", "nom_dep", "enf22", "enf2030", "enf2035", "ergo_lib", "besoin_2026", "besoin_2030", "besoin_2035", "offre_tend_2030", "offre_tend_2035", "solde_2026", "solde_const_2030", "solde_const_2035", "solde_tend_2030", "solde_tend_2035"]
    d.sort_values("solde_const_2035")[cols_p].round(1).to_csv(C.OUT / "projection_departements.csv", **CSV)
    cols_e = ["rang", "rang_hors_idf", "epci", "nom_epci", "dep", "n_com", "pop22", "enf22", "score", "ergo_lib", "dens_lib_10k_enf", "evol_enf_22_35_pct", "evol_nais_pct", "revenu_med", "besoin_2035", "solde_const_2035", "solde_tend_2035"]
    pd.DataFrame(ep.drop(columns="geometry")).sort_values("score", ascending=False)[cols_e].round(2).to_csv(C.OUT / "classement_intercommunalites.csv", **CSV)


def run():
    print("=== e4 : scores et projections ===")
    b = pickle.load(open(C.CACHE / "base.pkl", "rb"))
    com, ref = communes(b["com"].copy(), b["fin"])
    dep = departements(com, b["dep"])
    ep = intercos(com)
    ecrire(com, dep, ep)
    pickle.dump(dict(com=com, dep=dep, epci=ep, ref=ref, editions=b["editions"]), open(C.CACHE / "scores.pkl", "wb"))
    top = com.dropna(subset=["score"]).query("pop22 >= 2000").nlargest(5, "score")
    print("  Meilleures communes : " + ", ".join(f"{r.nom} ({r.dep}) {r.score:.0f}" for r in top.itertuples()))
    print(f"  -> {C.OUT / 'ergo_pediatrie.gpkg'} et 6 CSV")
    return True


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
