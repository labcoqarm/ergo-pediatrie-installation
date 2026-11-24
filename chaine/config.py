"""Réglages de la chaîne : dossiers, paramètres du calcul, sources."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRUT = ROOT / "donnees" / "brut"
CACHE = ROOT / "donnees" / "cache"
OUT = ROOT / "resultats"
WEB = OUT / "carte_interactive"
for _d in (BRUT, CACHE, OUT, WEB):
    _d.mkdir(parents=True, exist_ok=True)

ZONE_PLEIN = 10.0 # minutes de route : jusque-là, une commune compte entièrement dans la zone d'un cabinet
ZONE_MAX = 30.0 # au-delà, plus du tout ; entre les deux, son poids baisse régulièrement (comme l'APL de la DREES)
CALIB = 1.4 # recalage des vitesses théoriques sur des trajets connus
URBAIN = 4.0 # minutes ajoutées au départ et à l'arrivée en commune dense (> 2 000 hab/km²)
MARCHE_MIN = 2000 # en dessous de 2 000 enfants dans la zone (pondérés), la commune n'a pas de score
ANNEES = [2030, 2035]
IDF = ["75", "77", "78", "91", "92", "93", "94", "95"]
CAT_ADRESSEURS = {"190": "CAMSP", "189": "CMPP", "182": "SESSAD"}
VITESSES = {"Type autoroutier": 110, "Liaison principale": 75, "Liaison régionale": 65, "Bretelle": 50} # sinon 45

# Trouvées seules à chaque lancement : jeu data.gouv.fr, motif du titre, âge maximal avant retéléchargement (jours)
DATAGOUV = {
    "rpps": ("annuaire-sante-extractions-des-donnees-en-libre-acces-des-professionnels-intervenant-dans-le-systeme-de-sante-rpps", r"personne-activite", 180),
    "finess": ("finess-extraction-du-fichier-des-etablissements", r"g[ée]olocalis", 120),
    "drees": ("la-demographie-des-professionnels-de-sante-depuis-2012", r"^Ergoth.*ADELI", 300),
}
# Catalogue de l'IGN : ressource, motif de l'édition
IGN = {
    "adminexpress": ("ADMIN-EXPRESS-COG-CARTO-PE", "GPKG_LAMB93_FXX"),
    "route500": ("ROUTE500", "SHP_LAMB93_FXX"),
}
# Adresse fixe : l'INSEE change d'adresse à chaque édition. Pour passer à la suivante, remplacer la ligne.
FIXES = {
    "population": ("RP 2022", "https://www.insee.fr/fr/statistiques/fichier/8581810/TD_POP1A_2022_csv.zip"),
    "revenus": ("Filosofi 2021", "https://www.insee.fr/fr/statistiques/fichier/7756855/indic-struct-distrib-revenu-2021-COMMUNES_csv.zip"),
    "naissances": ("état civil 2008-2025", "https://www.insee.fr/fr/statistiques/fichier/1893255/base_naissances_2008-2025_geo2026_xlsx.zip"),
    "omphale": ("Omphale 2022", "https://www.insee.fr/fr/statistiques/fichier/7747107/donnees_detaillees_departementales.zip"),
}
