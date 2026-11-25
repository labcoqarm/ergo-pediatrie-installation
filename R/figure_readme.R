# Carte du score départemental pour le README (figures/score_departements.png), à partir des fichiers de l'appli. Lancer depuis la racine du projet.

library(ggplot2)
source("R/donnees.R")

# Échelle et flèche du nord, dessinées avec ggplot2 seul (carte en longitude/latitude)
echelle_nord <- function(emprise, km) {
  larg <- emprise[["xmax"]] - emprise[["xmin"]]
  haut <- emprise[["ymax"]] - emprise[["ymin"]]
  dx <- km / (111.32 * cos(mean(c(emprise[["ymin"]], emprise[["ymax"]])) * pi / 180)) # km convertis en degrés de longitude
  h <- haut * 0.012
  x0 <- emprise[["xmin"]] + larg * 0.05
  y0 <- emprise[["ymin"]] + haut * 0.04
  xn <- emprise[["xmax"]] - larg * 0.08
  yn <- emprise[["ymax"]] - haut * 0.15
  list(
    annotate("rect", xmin = x0, xmax = x0 + dx / 2, ymin = y0, ymax = y0 + h, fill = "black", colour = "black"),
    annotate("rect", xmin = x0 + dx / 2, xmax = x0 + dx, ymin = y0, ymax = y0 + h, fill = "white", colour = "black"),
    annotate("text", x = c(x0, x0 + dx / 2, x0 + dx), y = y0 + 3 * h, label = c("0", km / 2, paste(km, "km")), size = 3),
    annotate("segment", x = xn, xend = xn, y = yn, yend = yn + 8 * h, arrow = arrow(length = unit(2.5, "mm"), type = "closed")),
    annotate("text", x = xn, y = yn + 11 * h, label = "N", fontface = "bold", size = 4)
  )
}

dep <- lire_couche("resultats/carte_interactive/data_departements.js")

ggplot(dep) +
  geom_sf(aes(fill = score), colour = "white", linewidth = 0.2) +
  scale_fill_distiller(palette = "YlGnBu", direction = 1, name = "Score\n(0-100)") +
  echelle_nord(sf::st_bbox(dep), 200) +
  labs(title = "Score d'opportunité départemental", subtitle = "Ergothérapie pédiatrique libérale, France métropolitaine", caption = "Sources : RPPS, DREES, Insee, FINESS. Calcul du 22/11/2026.") +
  theme_void(base_family = "sans")
ggsave("figures/score_departements.png", width = 7, height = 7, dpi = 200, bg = "white")
