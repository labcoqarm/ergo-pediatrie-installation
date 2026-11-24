"""
lancer.py : toute la chaîne, dans l'ordre. Depuis le dossier du projet :

python chaine/lancer.py : télécharge ce qui a changé, recalcule si besoin
python chaine/lancer.py --force : recalcule tout, temps de route compris
python chaine/lancer.py --sans-telechargement : garde les sources déjà là

Premier lancement : 1 Go à télécharger et 5 à 10 min de calcul. Ensuite, quelques secondes s'il n'y a rien de neuf.
"""
import hashlib
import importlib
import json
import sys
import time
from pathlib import Path

ICI = Path(__file__).parent
sys.path.insert(0, str(ICI))
import config as C

SORTIES = [C.WEB / f for f in ("data_departements.js", "data_epci.js", "data_communes.js", "editions.json")]


def empreinte():
    h = hashlib.sha1()
    for p in [C.BRUT / "manifeste.json", *sorted(ICI.glob("*.py"))]:
        if p.exists():
            h.update(p.read_bytes())
    return h.hexdigest()


def main():
    t0 = time.time()
    force = "--force" in sys.argv
    print(f"Ergothérapie pédiatrique : mise à jour du {time.strftime('%d/%m/%Y %H:%M')}")
    if "--sans-telechargement" not in sys.argv and not importlib.import_module("e1_telecharger").run():
        return 1
    etat_path = C.CACHE / "etat.json"
    etat = json.loads(etat_path.read_text(encoding="utf-8")) if etat_path.exists() else {}
    signature = empreinte()
    if etat.get("empreinte") == signature and not force and all(p.exists() for p in SORTIES):
        print(f"\nRien de neuf depuis le {etat.get('date')} : résultats inchangés.")
        return 0
    for nom in ("e2_base", "e3_routes", "e4_scores", "e5_export"):
        print()
        mod = importlib.import_module(nom)
        ok = mod.run(force=force) if nom == "e3_routes" else mod.run()
        if not ok:
            print(f"\nArrêt à {nom}. Corriger le point signalé puis relancer.")
            return 1
    etat_path.write_text(json.dumps(dict(empreinte=signature, date=time.strftime("%d/%m/%Y %H:%M"))), encoding="utf-8")
    print(f"\nTerminé en {(time.time() - t0) / 60:.0f} min. Voir la carte : app.R dans RStudio, Run App.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
