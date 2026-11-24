# Carte du score départemental pour le README (figures/score_departements.png), à partir des fichiers de l'appli. Lancer depuis la racine du projet.

library(ggplot2)
source("R/donnees.R")

dep <- lire_couche("resultats/carte_interactive/data_departements.js")

ggplot(dep) +
  geom_sf(aes(fill = score), colour = "white", linewidth = 0.2) +
  scale_fill_distiller(palette = "YlGnBu", direction = 1, name = "Score\n(0-100)") +
  labs(title = "Score d'opportunité départemental", subtitle = "Ergothérapie pédiatrique libérale, France métropolitaine", caption = "Sources : RPPS, DREES, Insee, FINESS. Calcul du 22/11/2026.") +
  theme_void(base_family = "sans")
ggsave("figures/score_departements.png", width = 7, height = 7, dpi = 200, bg = "white")
