# Version web de l'appli pour GitHub Pages : shinylive fait tourner R dans le navigateur, rien à héberger. Lancer depuis la racine du projet.

if (!requireNamespace("shinylive", quietly = TRUE)) install.packages("shinylive")
library(leaflet)
source("R/donnees.R")

# copie propre de l'appli, sans donnees/ (1 Go) ni anciennes versions
appli <- file.path(tempdir(), "appli_web")
unlink(appli, recursive = TRUE)
dir.create(file.path(appli, "R"), recursive = TRUE)
file.copy("app.R", appli)
file.copy("R/donnees.R", file.path(appli, "R"))

# données lues et converties ici une fois pour toutes : le navigateur n'a plus qu'un fichier compact à ouvrir
E <- charger("resultats/carte_interactive")
saveRDS(E, file.path(appli, "echelles.rds"), compress = "xz")
message("echelles.rds : ", round(file.size(file.path(appli, "echelles.rds")) / 1e6, 1), " Mo")

unlink("docs", recursive = TRUE)
shinylive::export(appli, "docs")
# GitHub Pages ne doit pas filtrer les fichiers de shinylive
file.create("docs/.nojekyll")
message("Site écrit dans docs/. Test en local : httpuv::runStaticServer(\"docs\")")
