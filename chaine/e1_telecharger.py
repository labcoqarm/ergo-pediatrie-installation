"""
e1 : sources -> donnees/brut/<source>/.

data.gouv.fr et l'IGN ont un catalogue : la dernière édition y est trouvée seule. L'INSEE non : ses adresses sont dans config.FIXES. Une source n'est retéléchargée que si l'édition a changé (et, pour le RPPS, FINESS et la DREES, pas avant l'âge maximal fixé dans config).
"""
import json
import re
import shutil
import sys
import tempfile
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import config as C

MANIFESTE = C.BRUT / "manifeste.json"
ATOM = "{http://www.w3.org/2005/Atom}"


def ouvrir(url, timeout=120):
    req = urllib.request.Request(url, headers={"User-Agent": "ergo-pediatrie/2"})
    return urllib.request.urlopen(req, timeout=timeout)


def telecharger(url, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    t0 = time.time()
    with ouvrir(url, 900) as r, open(part, "wb") as f:
        shutil.copyfileobj(r, f, 1 << 20)
    part.replace(dest)
    print(f"    {dest.name} : {dest.stat().st_size / 1e6:.0f} Mo en {time.time() - t0:.0f} s")


def derniere_datagouv(slug, motif):
    d = json.load(ouvrir(f"https://www.data.gouv.fr/api/1/datasets/{slug}/"))
    res = [r for r in d["resources"] if re.search(motif, r["title"], re.I)]
    if not res:
        raise RuntimeError(f"aucune ressource « {motif} » dans {slug}")
    r = max(res, key=lambda r: r.get("last_modified") or "")
    return r["url"], r["title"]


def derniere_ign(ressource, motif):
    base = f"https://data.geopf.fr/telechargement/resource/{ressource}"
    feed = ET.fromstring(ouvrir(base).read())
    pages = int(next((v for k, v in feed.attrib.items() if k.endswith("pagecount")), 1)) # 10 éditions par page
    titres = [e.findtext(ATOM + "title") for e in feed.findall(ATOM + "entry")]
    for n in range(2, pages + 1):
        feed = ET.fromstring(ouvrir(f"{base}?page={n}").read())
        titres += [e.findtext(ATOM + "title") for e in feed.findall(ATOM + "entry")]
    titres = [t for t in titres if t and motif in t]
    if not titres:
        raise RuntimeError(f"aucune édition {motif} pour {ressource}")
    t = max(titres, key=lambda t: t[-10:]) # les titres finissent par la date d'édition
    return f"https://data.geopf.fr/telechargement/download/{ressource}/{t}/{t}.7z", t


def nom_fichier(url):
    return url.rstrip("/").split("/")[-1].split("?")[0]


def reduire_rpps(txt, dest):
    """Garde les ergothérapeutes : identifiant, profession, mode d'exercice, commune."""
    import pandas as pd
    entete = txt.open(encoding="utf-8", errors="replace").readline().rstrip("\n").split("|")
    norm = [re.sub(r"[^a-z]", "", c.lower().encode("ascii", "ignore").decode()) for c in entete]
    voulu = {"identifiantpp": "id", "libellprofession": "prof", "libellmodeexercice": "mode", "codecommune": "ccom"}
    cols = {}
    for k, v in voulu.items(): # « Code commune (coord. structure) » commence par « codecommune »
        trouve = [entete[i] for i, n in enumerate(norm) if n.startswith(k)]
        if trouve:
            cols[trouve[0]] = v
    if len(cols) < 4:
        raise RuntimeError(f"colonnes du RPPS introuvables : {entete[:12]}")
    morceaux = []
    for m in pd.read_csv(txt, sep="|", usecols=list(cols), dtype=str, chunksize=500_000, encoding="utf-8", encoding_errors="replace"):
        m = m.rename(columns=cols)
        morceaux.append(m[m["prof"].fillna("").str.contains("rgoth", case=False)])
    pd.concat(morceaux).to_csv(dest, sep="|", index=False)
    print(f"    {dest.name} : {sum(len(m) for m in morceaux)} lignes d'ergothérapeutes")


def extraire_7z(archive, dossier, motif):
    """Extrait les fichiers voulus et les remonte à la racine : les archives IGN sont rangées si profond que le chemin complet dépasse la limite de 260 caractères de Windows."""
    import py7zr
    tmp = Path(tempfile.mkdtemp())
    with py7zr.SevenZipFile(archive) as z:
        z.extract(path=tmp, targets=[n for n in z.getnames() if re.search(motif, n)])
    for f in tmp.rglob("*"):
        if f.is_file():
            shutil.move(str(f), dossier / f.name)
    shutil.rmtree(tmp)


def compacter_route500(dossier):
    """Ne garde que ce dont e3 a besoin : extrémités, type de route, longueur (1,3 Go -> environ 40 Mo)."""
    import numpy as np
    import pyogrio
    import shapely
    shp = dossier / "TRONCON_ROUTE.shp"
    d = pyogrio.read_dataframe(shp, columns=["VOCATION", "NB_CHAUSSE", "LONGUEUR"], encoding="latin1")
    a, b = shapely.get_point(d.geometry.values, 0), shapely.get_point(d.geometry.values, -1)
    xy = np.c_[shapely.get_x(a), shapely.get_y(a), shapely.get_x(b), shapely.get_y(b)].round(0).astype("int32") # au mètre, comme les nœuds
    np.savez_compressed(dossier / "troncons.npz", xy=xy, vocation=d.VOCATION.astype(str).to_numpy(), chaussees=d.NB_CHAUSSE.astype(str).to_numpy(), longueur=d.LONGUEUR.to_numpy("float32"))
    for f in dossier.glob("TRONCON_ROUTE.*"):
        f.unlink()
    print(f"    troncons.npz : {len(d)} tronçons")


def obtenir(cle, url, edition, man, age_max=None):
    """Télécharge si l'édition a changé."""
    deja = man.get(cle, {})
    if (C.BRUT / cle).exists() and (deja.get("url") == url or cle in C.IGN and deja.get("edition", "")[-10:] >= edition[-10:]):
        print(f"  [à jour] {cle} : {deja.get('edition')}")
        return
    if deja and age_max and (C.BRUT / cle).exists() and (date.today() - date.fromisoformat(deja["date"])).days < age_max:
        print(f"  [récent] {cle} : {deja.get('edition')} (nouvelle édition prise plus tard)")
        return
    print(f"  {cle} : {edition}")
    nouveau = C.BRUT / (cle + ".nouveau") # l'ancienne copie reste en place tant que tout n'a pas réussi
    if nouveau.exists():
        shutil.rmtree(nouveau)
    fichier = nouveau / nom_fichier(url)
    if not fichier.suffix:
        fichier = fichier.with_suffix(".xlsx" if cle == "drees" else ".dat")
    telecharger(url, fichier)
    if cle == "rpps":
        reduire_rpps(fichier, nouveau / "rpps_ergo.csv")
        fichier.unlink()
    elif cle in C.IGN:
        extraire_7z(fichier, nouveau, r"\.gpkg$" if cle == "adminexpress" else r"TRONCON_ROUTE\.(shp|shx|dbf|prj|cpg)$")
        fichier.unlink()
        if cle == "route500":
            compacter_route500(nouveau)
    # on vide l'ancien dossier puis on y déplace les fichiers : Windows refuse souvent de renommer un dossier qu'il vient de vider (il le garde en suppression différée)
    cible = C.BRUT / cle
    cible.mkdir(exist_ok=True)
    for vieux in cible.iterdir():
        shutil.rmtree(vieux) if vieux.is_dir() else vieux.unlink()
    for f in nouveau.iterdir():
        shutil.move(str(f), cible / f.name)
    shutil.rmtree(nouveau)
    man[cle] = dict(url=url, edition=edition, date=date.today().isoformat())
    MANIFESTE.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")


def run():
    print("=== e1 : sources ===")
    man = json.loads(MANIFESTE.read_text(encoding="utf-8")) if MANIFESTE.exists() else {}
    taches = [(k, lambda s=s, m=m: derniere_datagouv(s, m), age) for k, (s, m, age) in C.DATAGOUV.items()]
    taches += [(k, lambda r=r, m=m: derniere_ign(r, m), None) for k, (r, m) in C.IGN.items()]
    taches += [(k, lambda u=u, e=e: (u, e), None) for k, (e, u) in C.FIXES.items()]
    for cle, trouver, age in taches:
        url, edition = trouver()
        obtenir(cle, url, edition, man, age)
    return True


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
