"""
e3 : temps de route entre communes sur le réseau IGN ROUTE 500.

Vitesses par type de route (config.VITESSES), centre de chaque commune rattaché au nœud le plus proche (à 30 km/h avec un détour de 1,3), puis Dijkstra depuis chaque nœud. Seules les paires qui peuvent tomber sous la limite de la zone une fois recalées (ZONE_MAX / CALIB) sont gardées.

Sortie : donnees/cache/matrice.npz (i, j, t en minutes non recalées, communes dans l'ordre de base.pkl). Refait seulement si la liste des communes ou ZONE_MAX change (2 à 5 min).
"""
import hashlib
import pickle
import sys
import time
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).parent))
import config as C

SORTIE = C.CACHE / "matrice.npz"


def graphe(coms_xy):
    f = C.BRUT / "route500" / "troncons.npz"
    if not f.exists():
        raise FileNotFoundError("ROUTE 500 absent de donnees/brut/route500 : lancer e1_telecharger.py")
    z = np.load(f, allow_pickle=True)
    xy, voc = z["xy"].astype(float), z["vocation"]
    v = np.array([C.VITESSES.get(x, 45.0) for x in voc])
    v[(voc == "Liaison principale") & (z["chaussees"] == "2 chaussées")] = 90
    t = z["longueur"].astype(float) / v * 60 # minutes
    pts = np.r_[xy[:, :2], xy[:, 2:]].round(0)
    noeuds, inv = np.unique(pts, axis=0, return_inverse=True)
    n = len(xy)
    G = csr_matrix((np.r_[t, t] + 1e-4, (np.r_[inv[:n], inv[n:]], np.r_[inv[n:], inv[:n]])), shape=(len(noeuds),) * 2)
    G.sum_duplicates()
    dist, noeud = cKDTree(noeuds).query(coms_xy)
    acces = dist * 1.3 / 1000 / 30 * 60 # minutes jusqu'au réseau
    print(f"  Réseau : {len(noeuds)} nœuds, {n} tronçons ; accès médian au réseau {np.median(acces):.1f} min")
    return G, noeud, acces


def run(force=False):
    print("=== e3 : temps de route ===")
    base = pickle.load(open(C.CACHE / "base.pkl", "rb"))["com"]
    lim = C.ZONE_MAX / C.CALIB
    cle = hashlib.sha1(("".join(base.codgeo) + f"{lim:.3f}").encode()).hexdigest()
    if SORTIE.exists() and not force and str(np.load(SORTIE)["cle"]) == cle:
        print("  [à jour] matrice des temps de route")
        return True
    G, noeud, acces = graphe(base[["x", "y"]].to_numpy())

    sources = np.unique(noeud)
    ordre = np.argsort(noeud)
    tri = noeud[ordre]
    I, J, T = [], [], []
    t0 = time.time()
    for k in range(0, len(sources), 50): # par paquets : 50 lignes de distances par nœud du réseau
        s = sources[k:k + 50]
        D = dijkstra(G, directed=False, indices=s, limit=lim)[:, noeud] + acces[None, :]
        for r, sv in enumerate(s):
            dest = np.nonzero(D[r] <= lim)[0]
            for o in ordre[np.searchsorted(tri, sv):np.searchsorted(tri, sv, side="right")]:
                tt = D[r, dest] + acces[o]
                ok = tt <= lim
                I.append(np.full(ok.sum(), o, np.int32))
                J.append(dest[ok].astype(np.int32))
                T.append(tt[ok].astype(np.float32))
        if k % 4000 == 0:
            print(f"    {k + len(s)}/{len(sources)} nœuds, {time.time() - t0:.0f} s")
    np.savez(SORTIE, i=np.concatenate(I), j=np.concatenate(J), t=np.concatenate(T), cle=cle)
    print(f"  {sum(len(x) for x in I)} paires de communes en {time.time() - t0:.0f} s -> {SORTIE.name}")
    return True


if __name__ == "__main__":
    sys.exit(0 if run(force="--force" in sys.argv) else 1)
