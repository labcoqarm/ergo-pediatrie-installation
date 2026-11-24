"""
e5 : fichiers lus par l'appli Shiny (resultats/carte_interactive/ : data_*.js, voisins.bin, editions.json).
"""
import json
import pickle
import sys
import tempfile
from datetime import date
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import config as C
from e4_scores import voisinage

COLONNES = {
    "dep": ("data_departements.js", "DATA_DEP", 800, ["dep", "nom_dep", "score", "rang", "dens_lib_10k_enf", "evol_enf_24_35_pct", "revenu_med", "evol_lib_16_24_pct", "adresseurs_10k_enf", "ergo_lib", "enf22", "enf2030", "enf2035", "besoin_2026", "besoin_2030", "besoin_2035", "offre_tend_2030", "offre_tend_2035", "solde_const_2035", "solde_tend_2035"]),
    "epci": ("data_epci.js", "DATA_EPCI", 400, ["epci", "nom_epci", "dep", "n_com", "pop22", "score", "dens_lib_10k_enf", "evol_enf_22_35_pct", "evol_nais_pct", "revenu_med", "ergo_lib", "enf22", "enf2030", "enf2035", "besoin_2035", "offre_tend_2035", "solde_const_2035", "solde_tend_2035", "solde_tend_pct"]),
    "com": ("data_communes.js", "DATA_COM", 250, ["codgeo", "nom", "dep", "pop22", "score", "apl_ergo_10k", "enf_zone", "ergo_zone", "evol_nais_pct", "revenu_zone", "adresseurs_zone", "couv_const_2035", "couv_tend_2035", "ergo_lib", "enf22", "enf2030", "enf2035", "besoin_2026", "besoin_2030", "besoin_2035", "offre_tend_2030", "offre_tend_2035"]),
}


def ecrire(g, fichier, var, tol, cols):
    import pyogrio
    g = gpd.GeoDataFrame(g[cols + ["geometry"]].copy(), geometry="geometry", crs="EPSG:2154")
    g["geometry"] = g.geometry.simplify(tol, preserve_topology=True)
    g = g.to_crs(4326)
    for c in cols:
        if pd.api.types.is_float_dtype(g[c]):
            g[c] = g[c].round(2)
    tmp = Path(tempfile.mkdtemp()) / "x.geojson"
    pyogrio.write_dataframe(g, tmp, driver="GeoJSON", layer_options={"COORDINATE_PRECISION": 4, "RFC7946": "YES"})
    txt = tmp.read_text(encoding="utf-8")
    (C.WEB / fichier).write_text(f"window.{var} = {txt};", encoding="utf-8")
    print(f"  {fichier} : {len(g)} territoires, {len(txt) / 1e6:.1f} Mo")


def run():
    print("=== e5 : export pour l'appli ===")
    s = pickle.load(open(C.CACHE / "scores.pkl", "rb"))
    com = s["com"].copy()
    for k in ["enf22", "enf2030", "enf2035", "enf_zone", "ergo_zone", "pop22"]:
        com[k] = com[k].round(0)
    for cle, table in (("dep", s["dep"]), ("epci", s["epci"]), ("com", com)):
        ecrire(table, *COLONNES[cle])
    # zone de chaque commune, pour la dessiner dans l'appli : n, départs, arrivées (base 0), poids en centièmes
    M = voisinage(s["com"]).tocoo()
    with open(C.WEB / "voisins.bin", "wb") as f:
        np.array([M.nnz], "<i4").tofile(f)
        M.row.astype("<i4").tofile(f)
        M.col.astype("<i4").tofile(f)
        np.round(M.data * 100).astype("u1").tofile(f)
    man = json.loads((C.BRUT / "manifeste.json").read_text(encoding="utf-8")) if (C.BRUT / "manifeste.json").exists() else {}
    editions = {k: v.get("edition") for k, v in man.items()}
    editions.update({f"periode_{k}": v for k, v in s["editions"].items()})
    editions["calcul"] = date.today().strftime("%d/%m/%Y")
    editions["densite_ref"] = round(s["ref"] * 1e4, 2)
    (C.WEB / "editions.json").write_text(json.dumps(editions, ensure_ascii=False, indent=1), encoding="utf-8")
    return True


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
