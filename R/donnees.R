# Lecture des fichiers de resultats/carte_interactive (écrits par chaine/e5_export.py) et liste des indicateurs de chaque échelle.

lire_couche <- function(f) {
  txt <- readChar(f, file.size(f), useBytes = TRUE)
  txt <- sub(";\\s*$", "", sub("^window\\.[A-Z_]+ = ", "", txt))
  geo <- tempfile(fileext = ".geojson")
  writeChar(txt, geo, eos = NULL, useBytes = TRUE)
  g <- sf::st_read(geo, quiet = TRUE)
  # quelques polygones arrivent emballés dans une collection : leaflet refuse de les dessiner
  gc <- sf::st_is(g, "GEOMETRYCOLLECTION")
  if (any(gc)) {
    sf::st_geometry(g)[gc] <- sf::st_cast(sf::st_collection_extract(sf::st_geometry(g)[gc], "POLYGON"), "MULTIPOLYGON")
  }
  g
}

# polygones convertis une seule fois pour leaflet : sans ça, le navigateur refait la conversion des 35 000 communes à chaque affichage
registerS3method("polygonData", "polygones_prets", function(obj) { class(obj) <- NULL; obj }, envir = asNamespace("leaflet"))

# clé, libellé, sens (1 : plus haut = plus favorable, -1 : plus bas = plus favorable, 0 : ni l'un ni l'autre), explication
indic <- function(...) {
  x <- list(...)
  data.frame(cle = sapply(x, `[`, 1), nom = sapply(x, `[`, 2), sens = as.integer(sapply(x, `[`, 3)), aide = sapply(x, `[`, 4))
}

ECHELLES <- list(
  dep = list(
    fichier = "data_departements.js", id = "dep", libelle = "nom_dep",
    indic = indic(
      c("score", "Score d'opportunité (0-100)", 1, "Concurrence 35 %, projection des enfants 25 %, revenus 15 %, croissance des ergos 10 %, structures adresseuses 15 %."),
      c("dens_lib_10k_enf", "Ergos libéraux pour 10 000 enfants", -1, "RPPS. Moins il y en a, moins il y a de concurrence."),
      c("solde_tend_2035", "Solde ergos 2035 si la hausse continue", -1, "Offre prolongeant la hausse 2016-2024 moins besoin projeté. Négatif = manque."),
      c("solde_const_2035", "Solde ergos 2035 à offre figée", -1, "Offre 2026 moins besoin 2035. Négatif = manque."),
      c("evol_enf_24_35_pct", "Évolution des 0-14 ans 2024-2035 (%)", 1, "INSEE Omphale 2022, scénario central."),
      c("revenu_med", "Niveau de vie médian (€)", 1, "Filosofi 2021. Les séances libérales ne sont pas remboursées."),
      c("evol_lib_16_24_pct", "Croissance des ergos libéraux 2016-2024 (%)", -1, "DREES, libéraux et mixtes. Forte croissance = concurrence qui arrive. Sur de petits effectifs, les pourcentages s'envolent."),
      c("adresseurs_10k_enf", "CAMSP, CMPP, SESSAD pour 10 000 enfants", 1, "FINESS."),
      c("ergo_lib", "Ergos libéraux (nombre)", 0, ""),
      c("enf22", "Enfants 0-17 ans (2022)", 0, ""),
      c("besoin_2035", "Besoin en ergos libéraux 2035", 0, "Enfants projetés × densité nationale actuelle d'ergos libéraux.")
    )),
  epci = list(
    fichier = "data_epci.js", id = "epci", libelle = "nom_epci",
    indic = indic(
      c("score", "Score d'opportunité moyen (0-100)", 1, "Moyenne des scores communaux pondérée par le nombre d'enfants."),
      c("dens_lib_10k_enf", "Ergos libéraux pour 10 000 enfants", -1, "RPPS."),
      c("solde_tend_2035", "Solde ergos 2035 si la hausse continue", -1, "Négatif = manque."),
      c("solde_tend_pct", "Solde 2035 tendanciel (% du besoin)", -1, "Négatif = déficit."),
      c("solde_const_2035", "Solde ergos 2035 à offre figée", -1, ""),
      c("evol_enf_22_35_pct", "Évolution des 0-17 ans 2022-2035 (%)", 1, "Omphale départemental corrigé par les naissances locales."),
      c("evol_nais_pct", "Naissances 2021-25 / 2011-15 (%)", 1, "État civil INSEE."),
      c("revenu_med", "Niveau de vie médian (€)", 1, ""),
      c("ergo_lib", "Ergos libéraux (nombre)", 0, ""),
      c("enf22", "Enfants 0-17 ans (2022)", 0, "")
    )),
  com = list(
    fichier = "data_communes.js", id = "codgeo", libelle = "nom",
    indic = indic(
      c("score", "Score d'opportunité (0-100)", 1, "Concurrence 35 %, taille du marché 20 %, naissances 15 %, revenus 15 %, structures adresseuses 15 %, mesurés dans la zone de la commune (voir l'aide)."),
      c("apl_ergo_10k", "Ergos libéraux accessibles pour 10 000 enfants", -1, "Ergos de la zone, partagés avec les enfants de leur propre zone (méthode de l'APL de la DREES)."),
      c("couv_tend_2035", "Besoin 2035 couvert, hausse continue (%)", -1, "Moins de 100 % = déficit."),
      c("couv_const_2035", "Besoin 2035 couvert, offre figée (%)", -1, "Moins de 100 % = déficit."),
      c("enf_zone", "Enfants 0-17 ans dans la zone", 1, "La clientèle possible : enfants à moins de 10 min de route comptés entièrement, puis de moins en moins jusqu'à 30 min."),
      c("ergo_zone", "Ergos libéraux dans la zone", -1, "La concurrence, comptée comme les enfants : entièrement jusqu'à 10 min, de moins en moins jusqu'à 30 min."),
      c("evol_nais_pct", "Naissances 2021-25 / 2011-15 dans la zone (%)", 1, ""),
      c("revenu_zone", "Niveau de vie médian dans la zone (€)", 1, ""),
      c("adresseurs_zone", "CAMSP, CMPP, SESSAD dans la zone", 1, ""),
      c("pop22", "Population 2022", 0, "")
    ))
)

charger <- function(dossier) {
  for (e in names(ECHELLES)) {
    f <- file.path(dossier, ECHELLES[[e]]$fichier)
    if (!file.exists(f)) stop("Fichier absent : ", f)
    g <- lire_couche(f)
    ECHELLES[[e]]$data <- g
    ECHELLES[[e]]$poly <- structure(leaflet:::polygonData(g), class = "polygones_prets")
    ECHELLES[[e]]$ids <- as.character(g[[ECHELLES[[e]]$id]])
    ECHELLES[[e]]$noms <- paste0(g[[ECHELLES[[e]]$libelle]], " (", g$dep, ")")
  }
  # zone de chaque commune : n, puis les n départs, les n arrivées (base 0) et les n poids en centièmes
  vb <- file.path(dossier, "voisins.bin")
  if (file.exists(vb)) {
    con <- file(vb, "rb")
    n <- readBin(con, "integer", 1, size = 4, endian = "little")
    i <- readBin(con, "integer", n, size = 4, endian = "little")
    j <- readBin(con, "integer", n, size = 4, endian = "little")
    w <- readBin(con, "integer", n, size = 1, signed = FALSE)
    close(con)
    if (max(i) < nrow(ECHELLES$com$data)) {
      f <- factor(i + 1L, levels = seq_len(nrow(ECHELLES$com$data)))
      ECHELLES$com$voisins <- split(j + 1L, f)
      ECHELLES$com$poids <- split(w / 100, f)
    }
  }
  ed <- jsonlite::fromJSON(file.path(dossier, "editions.json"))
  # les périodes changent avec les éditions DREES et INSEE
  d <- strsplit(ed$periode_drees, "-")[[1]]
  n <- as.integer(strsplit(ed$periode_naissances, "-")[[1]])
  nais <- sprintf("%d-%02d / %d-%02d", n[1], n[2] %% 100, n[1] - 10, (n[2] - 10) %% 100)
  for (e in names(ECHELLES)) {
    for (k in c("nom", "aide")) {
      x <- ECHELLES[[e]]$indic[[k]]
      x <- gsub("2016-2024", paste(d, collapse = "-"), x, fixed = TRUE)
      ECHELLES[[e]]$indic[[k]] <- gsub("2021-25 / 2011-15", nais, x, fixed = TRUE)
    }
  }
  attr(ECHELLES, "editions") <- ed
  ECHELLES
}
