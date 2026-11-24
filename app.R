# Ergothérapie pédiatrique libérale : où s'installer en France métropolitaine. Version Shiny. Paquets : shiny, leaflet, sf, jsonlite. Lancer : shiny::runApp() depuis ce dossier. Données : produites par chaine/lancer.py (mise à jour mensuelle par mise_a_jour.bat).

library(shiny)
library(leaflet)

E <- charger("resultats/carte_interactive")
IDF <- c("75", "77", "78", "91", "92", "93", "94", "95")
PALETTE <- c("#FFFFCC", "#C7E9B4", "#7FCDBB", "#41B6C4", "#2C7FB8", "#253494")
GRIS <- "#D9D9D9"
ROUGE <- "#C0143C"

fmt <- function(v) {
  ifelse(is.na(v), "–", ifelse(abs(v) >= 1000, formatC(round(v), format = "d", big.mark = " "), trimws(formatC(round(v, 1), format = "fg", digits = 6, decimal.mark = ","))))
}
communes <- function(n) paste(n, if (n > 1) "communes" else "commune")
clic <- function(id, valeur) sprintf("Shiny.setInputValue('%s', %s, {priority: 'event'})", id, valeur)

ign <- function(couche, format) {
  paste0("https://data.geopf.fr/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=", couche, "&STYLE=normal&FORMAT=", format, "&TILEMATRIXSET=PM&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}")
}
# aucun de ces fonds ne demande de clé
FONDS <- list(
  "Plan IGN" = list(ign("GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2", "image/png"), "© IGN Géoplateforme"),
  "Photo IGN" = list(ign("ORTHOIMAGERY.ORTHOPHOTOS", "image/jpeg"), "© IGN Géoplateforme"),
  "Photo Esri" = list("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", "Esri, Maxar")
)

contours_dep <- sf::st_boundary(sf::st_geometry(E$dep$data))

css <- "
* { font-family: Arial, Helvetica, sans-serif; box-sizing: border-box; }
html, body { height: 100%; margin: 0; font-size: 14px; color: #111; }
.app { display: flex; flex-direction: column; height: 100vh; }
.barre { display: flex; flex-wrap: wrap; align-items: center; gap: 5px; padding: 6px 10px; background: #ececec; border-bottom: 1px solid #999; }
.barre .titre { font-weight: bold; margin-right: 8px; }
.barre .btn, .barre select { border: 1px solid #888; border-radius: 0; background: #fff; height: 28px; padding: 2px 8px; font-size: 13px; box-shadow: none; }
.barre .btn.actif { background: #222; color: #fff; border-color: #222; }
.barre .form-group { margin: 0; width: auto !important; }
.barre select.form-control { width: auto; display: inline-block; }
.barre .selectize-control { width: 190px; margin: 0; }
.barre #indic { max-width: 270px; }
.barre .selectize-input { border-radius: 0; min-height: 28px; padding: 4px 8px; box-shadow: none; border-color: #888; }
.barre .sep { width: 1px; height: 22px; background: #999; margin: 0 5px; }
.corps { flex: 1; min-height: 0; display: grid; grid-template-columns: minmax(0, 1fr) 370px; }
#carte { height: 100% !important; }
.panneau { overflow-y: auto; border-left: 1px solid #999; padding: 8px 12px 20px; }
.panneau h2 { font-size: 18px; margin: 4px 0 2px; }
.panneau h3 { font-size: 14px; margin: 16px 0 6px; padding-bottom: 2px; border-bottom: 1px solid #bbb; }
.gris { color: #555; font-size: 12px; }
.leg { display: flex; align-items: center; gap: 8px; font-size: 12px; margin: 2px 0; }
.leg i { width: 18px; height: 12px; border: 1px solid #999; }
table.t { width: 100%; border-collapse: collapse; font-size: 13px; }
table.t td { padding: 3px 4px; border-bottom: 1px solid #e2e2e2; }
table.t td.n { text-align: right; white-space: nowrap; }
table.t tr.lien { cursor: pointer; }
table.t tr.lien:hover { background: #f2f2f2; }
.fiche { border: 2px solid #C0143C; padding: 8px 10px; margin: 6px 0 4px; }
.fiche .entete { display: flex; justify-content: space-between; align-items: baseline; }
.jauge { height: 8px; background: #e2e2e2; min-width: 90px; }
.jauge i { display: block; height: 100%; }
.cle i { display: inline-block; width: 14px; height: 3px; vertical-align: middle; margin: 0 4px 0 8px; }
.modal-content { border-radius: 0; }
"

js <- "
Shiny.addCustomMessageHandler('echelle', function(e) {
  ['dep', 'epci', 'com'].forEach(function(k) { document.getElementById('e_' + k).classList.toggle('actif', k === e); });
});
Shiny.addCustomMessageHandler('idf', function(on) { document.getElementById('idf').classList.toggle('actif', on); });
document.addEventListener('DOMContentLoaded', function() {
  // recolore les polygones déjà dessinés, sans les renvoyer au navigateur
  LeafletWidget.methods.recolorer = function(ids, couleurs, opacite) {
    for (var i = 0; i < ids.length; i++) {
      var l = this.layerManager.getLayer('shape', ids[i]);
      if (l) l.setStyle({fillColor: couleurs[i], fillOpacity: opacite});
    }
  };
});
"

ui <- fillPage(
  tags$head(tags$style(HTML(css)), tags$title("Ergothérapie pédiatrique libérale")),
  div(class = "app",
    div(class = "barre",
      span(class = "titre", "Ergothérapie pédiatrique libérale"),
      actionButton("e_dep", "Départements", class = "actif"),
      actionButton("e_epci", "Intercos"),
      actionButton("e_com", "Communes"),
      span(class = "sep"),
      selectInput("indic", NULL, setNames(E$dep$indic$cle, E$dep$indic$nom), selectize = FALSE),
      actionButton("idf", "Hors Île-de-France"),
      span(class = "sep"),
      selectizeInput("cherche", NULL, choices = NULL, options = list(placeholder = "Rechercher un territoire")),
      selectInput("fond", NULL, names(FONDS), selectize = FALSE),
      selectInput("opacite", NULL, c("Aplats 85 %" = 0.85, "Aplats 65 %" = 0.65, "Aplats 45 %" = 0.45), selected = 0.65, selectize = FALSE),
      actionButton("aide", "Aide")
    ),
    div(class = "corps",
      leafletOutput("carte"),
      div(class = "panneau",
        uiOutput("fiche"),
        h3(textOutput("titre_indic", inline = TRUE)),
        div(class = "gris", textOutput("aide_indic")),
        uiOutput("legende"),
        plotOutput("histo", height = "110px"),
        h3("Classement"),
        uiOutput("classement")
      )
    )
  ),
  tags$script(HTML(js))
)

enfants <- function(g, i) {
  v <- sapply(c("enf22", "enf2030", "enf2035"), function(k) g[[k]][i])
  span(class = "gris", sprintf("Enfants 0-17 ans : %s en 2022, %s en 2030, %s en 2035.", fmt(v[1]), fmt(v[2]), fmt(v[3])))
}

positions <- function(g, ind, i) {
  ind <- ind[ind$sens != 0, ] # population, nombre d'enfants... : ni bon ni mauvais
  lignes <- lapply(seq_len(nrow(ind)), function(k) {
    v <- g[[ind$cle[k]]]
    if (is.na(v[i])) return(tags$tr(tags$td(ind$nom[k]), tags$td(), tags$td(class = "n", "–")))
    autres <- v[!is.na(v)]
    # part des territoires strictement moins favorables : les ex aequo ne comptent pas
    r <- 100 * if (ind$sens[k] > 0) mean(autres < v[i]) else mean(autres > v[i])
    tags$tr(tags$td(ind$nom[k]), tags$td(div(class = "jauge", tags$i(style = sprintf("width:%d%%;background:%s", round(r), if (r >= 50) "#2C7FB8" else ROUGE)))), tags$td(class = "n", paste("mieux que", round(r), "%")))
  })
  tags$table(class = "t", lignes)
}

sources <- function() {
  ed <- attr(E, "editions")
  v <- function(k) if (is.null(ed[[k]])) "?" else format(ed[[k]], decimal.mark = ",")
  an <- function(k) sub(".*(\\d{4})-\\d{2}-\\d{2}$", "\\1", v(k)) # année d'édition IGN
  sprintf("Sources : RPPS (%s), FINESS (%s), DREES (%s), INSEE %s, %s, naissances %s, %s, IGN Admin Express %s et ROUTE 500 %s. Calcul du %s ; densité nationale de référence %s ergos libéraux pour 10 000 enfants. Fond de carte : IGN ou Esri.", v("rpps"), v("finess"), v("periode_drees"), v("population"), v("revenus"), v("periode_naissances"), v("omphale"), an("adminexpress"), an("route500"), v("calcul"), v("densite_ref"))
}

server <- function(input, output, session) {
  echelle <- reactiveVal("dep")
  hors_idf <- reactiveVal(FALSE)
  choix <- reactiveVal(NA_integer_)
  carte_prete <- reactiveVal(FALSE)

  ech <- reactive(E[[echelle()]])
  info <- reactive({
    ind <- ech()$indic
    if (input$indic %in% ind$cle) ind[ind$cle == input$indic, ] else ind[1, ]
  })
  valeurs <- reactive(ech()$data[[info()$cle]])
  garder <- reactive(if (hors_idf()) !(ech()$data$dep %in% IDF) else rep(TRUE, nrow(ech()$data)))

  # six classes de même effectif ; foncé = plus favorable (ou plus élevé si l'indicateur est neutre)
  bornes <- reactive({
    v <- valeurs()[garder() & !is.na(valeurs())]
    unique(quantile(v, seq(0, 1, length.out = 7), names = FALSE, type = 1))
  })
  couleurs <- reactive({
    pal <- if (info()$sens >= 0) PALETTE else rev(PALETTE)
    b <- bornes()
    k <- findInterval(valeurs(), b, rightmost.closed = TRUE, all.inside = TRUE)
    out <- pal[pmin(k, 6)]
    out[is.na(valeurs())] <- GRIS
    out
  })

  changer_echelle <- function(e) {
    if (e == echelle()) return()
    echelle(e)
    choix(NA_integer_)
    ind <- E[[e]]$indic
    garde <- if (input$indic %in% ind$cle) input$indic else "score"
    updateSelectInput(session, "indic", choices = setNames(ind$cle, ind$nom), selected = garde)
  }
  observeEvent(input$e_dep, changer_echelle("dep"))
  observeEvent(input$e_epci, changer_echelle("epci"))
  observeEvent(input$e_com, changer_echelle("com"))
  observeEvent(echelle(), {
    session$sendCustomMessage("echelle", echelle())
    updateSelectizeInput(session, "cherche", choices = setNames(seq_along(ech()$noms), ech()$noms), selected = character(0), server = TRUE)
  })
  observeEvent(input$idf, hors_idf(!hors_idf()))
  observeEvent(hors_idf(), session$sendCustomMessage("idf", hors_idf()))

  observeEvent(input$carte_zoom, carte_prete(TRUE), once = TRUE)

  output$carte <- renderLeaflet({
    leaflet(options = leafletOptions(preferCanvas = TRUE, zoomSnap = 0.5)) |>
      addScaleBar("bottomleft", scaleBarOptions(imperial = FALSE)) |>
      setView(2.5, 46.6, 6)
  })

  observe({
    req(carte_prete(), input$fond)
    f <- FONDS[[input$fond]]
    leafletProxy("carte") |>
      clearGroup("fond") |>
      addTiles(f[[1]], attribution = f[[2]], group = "fond", options = tileOptions(maxZoom = 19))
  })

  # polygones : dessinés une fois par échelle
  observe({
    req(carte_prete())
    e <- echelle()
    isolate({
      g <- E[[e]]
      leafletProxy("carte") |>
        clearGroup("territoires") |>
        clearGroup("contours") |>
        addPolygons(data = g$data, layerId = g$ids, group = "territoires", fillColor = couleurs(), fillOpacity = as.numeric(input$opacite), color = "#ffffff", weight = if (e == "com") 0.2 else 0.6, opacity = 0.8, label = g$noms) |>
        addPolylines(data = contours_dep, group = "contours", color = "#333", weight = 0.8, opacity = 0.9, options = pathOptions(interactive = FALSE))
    })
  })

  # couleurs : changées sur place quand l'indicateur, le filtre ou l'opacité bougent
  observe({
    req(carte_prete())
    cols <- couleurs()
    op <- as.numeric(input$opacite)
    leafletProxy("carte") |> invokeMethod(NULL, "recolorer", ech()$ids, cols, op)
  })

  observeEvent(input$carte_shape_click, {
    i <- match(input$carte_shape_click$id, ech()$ids)
    if (!is.na(i)) choix(i)
  })
  aller <- function(i) {
    choix(i)
    bb <- unname(sf::st_bbox(ech()$data[i, ]))
    leafletProxy("carte") |> fitBounds(bb[1], bb[2], bb[3], bb[4], options = list(maxZoom = 10, padding = c(60, 60)))
  }
  observeEvent(input$cherche, if (nzchar(input$cherche)) aller(as.integer(input$cherche)))
  observeEvent(input$clic_rang, aller(input$clic_rang))
  observeEvent(input$fermer, choix(NA_integer_))

  zone <- reactive({
    i <- choix()
    if (is.na(i) || echelle() != "com" || is.null(E$com$voisins)) return(integer(0))
    E$com$voisins[[i]]
  })
  poids_zone <- reactive(if (length(zone())) E$com$poids[[choix()]] else numeric(0))

  observe({
    z <- zone()
    p <- leafletProxy("carte") |> clearGroup("zone")
    if (length(z)) {
      p |> addPolygons(data = E$com$data[z, ], group = "zone", fillColor = ROUGE, fillOpacity = 0.05 + 0.35 * poids_zone(), color = ROUGE, weight = 0.6, opacity = 0.6, options = pathOptions(interactive = FALSE))
    }
  })

  observe({
    i <- choix()
    p <- leafletProxy("carte") |> clearGroup("choix")
    if (!is.na(i)) {
      p |> addPolylines(data = sf::st_boundary(sf::st_geometry(ech()$data[i, ])), group = "choix", color = ROUGE, weight = 3, opacity = 1, options = pathOptions(interactive = FALSE))
    }
  })

  output$titre_indic <- renderText(info()$nom)
  output$aide_indic <- renderText(info()$aide)

  output$legende <- renderUI({
    pal <- if (info()$sens >= 0) PALETTE else rev(PALETTE)
    b <- bornes()
    lignes <- lapply(seq_len(length(b) - 1), function(k) {
      div(class = "leg", tags$i(style = paste0("background:", pal[k])), paste(fmt(b[k]), "à", fmt(b[k + 1])))
    })
    gris <- if (echelle() == "com" && info()$cle %in% c("score", "apl_ergo_10k", "evol_nais_pct", "revenu_zone", "couv_const_2035", "couv_tend_2035")) {
      "Moins de 2 000 enfants dans la zone : marché trop petit"
    } else "Sans donnée"
    tagList(lignes, div(class = "leg", tags$i(style = paste0("background:", GRIS)), gris), div(class = "gris", switch(as.character(info()$sens), "-1" = "Foncé = valeur basse = plus favorable.", "1" = "Foncé = plus favorable.", "Foncé = valeur élevée.")))
  })

  output$histo <- renderPlot({
    v <- valeurs()[garder()]
    v <- v[!is.na(v)]
    par(mar = c(2, 2.5, 0.5, 0.5), family = "sans", cex.axis = 0.75, mgp = c(1.5, 0.4, 0), tcl = -0.2)
    h <- hist(v, breaks = 24, plot = FALSE)
    x <- if (!is.na(choix())) valeurs()[choix()] else NA
    col <- ifelse(!is.na(x) & h$breaks[-length(h$breaks)] <= x & h$breaks[-1] > x, ROUGE, "#2C7FB8")
    plot(h, col = col, border = "white", main = "", xlab = "", ylab = "", las = 1)
  }, res = 96)

  output$classement <- renderUI({
    g <- ech()$data
    v <- valeurs()
    ok <- garder() & !is.na(v)
    if (echelle() == "com") ok <- ok & g$pop22 >= 2000
    idx <- which(ok)[order(v[ok] * -(if (info()$sens == 0) 1 else info()$sens))][1:min(25, sum(ok))]
    lignes <- lapply(seq_along(idx), function(r) {
      i <- idx[r]
      tags$tr(class = "lien", onclick = clic("clic_rang", i), tags$td(r), tags$td(ech()$noms[i]), tags$td(class = "n", fmt(v[i])))
    })
    tagList(tags$table(class = "t", lignes), if (echelle() == "com") div(class = "gris", "Communes de 2 000 habitants et plus."))
  })

  output$fiche <- renderUI({
    i <- choix()
    if (is.na(i)) return(div(class = "gris", "Clique sur un territoire pour voir ses indicateurs et sa projection 2026-2035."))
    g <- ech()$data
    sous <- switch(echelle(), dep = paste("Département", g$dep[i]), epci = paste("Intercommunalité, département", g$dep[i]), com = paste0("Commune ", g$codgeo[i], ", département ", g$dep[i]))
    ind <- ech()$indic
    tagList(
      div(class = "fiche",
        div(class = "entete", h2(g[[ech()$libelle]][i]), actionLink("fermer", "fermer")),
        div(class = "gris", sous),
        if (length(zone())) p(style = "margin:6px 0 0", sprintf(
          "Zone de %s (en rose sur la carte, plus foncé = plus proche) : %s à moins de 10 min de route, %s entre 10 et 30 min. Comptés avec leur poids : %s enfants de 0 à 17 ans, %s ergos libéraux.",
          g$nom[i], communes(sum(poids_zone() >= 1)), communes(sum(poids_zone() < 1)),
          fmt(round(sum(g$enf22[zone()] * poids_zone()))), fmt(round(sum(g$ergo_lib[zone()] * poids_zone())))))),
      h3("Besoin et offre d'ergos libéraux"),
      plotOutput("projection", height = "150px"),
      div(class = "gris cle", tags$i(style = paste0("background:", ROUGE)), "besoin", tags$i(style = "background:#2C7FB8"), "offre si la hausse continue", tags$i(style = "background:#888"), "offre figée"),
      div(style = "margin-top:6px", enfants(g, i)),
      h3("Comparaison avec les autres territoires"),
      div(class = "gris", "« Mieux que 80 % » : plus favorable à une installation que 80 % des territoires."),
      positions(g, ind, i),
      h3("Toutes les données"),
      tags$table(class = "t", lapply(seq_len(nrow(ind)), function(k) {
        tags$tr(tags$td(ind$nom[k]), tags$td(class = "n", fmt(g[[ind$cle[k]]][i])))
      }))
    )
  })

  output$projection <- renderPlot({
    i <- choix()
    req(!is.na(i))
    g <- sf::st_drop_geometry(ech()$data[i, ])
    val <- function(k) if (k %in% names(g)) g[[k]] else NA
    an <- c(2026, 2030, 2035)
    besoin <- sapply(c("besoin_2026", "besoin_2030", "besoin_2035"), val)
    tend <- c(val("ergo_lib"), val("offre_tend_2030"), val("offre_tend_2035"))
    fige <- rep(val("ergo_lib"), 3)
    par(mar = c(2.2, 3, 0.5, 0.5), family = "sans", cex.axis = 0.75, mgp = c(1.6, 0.4, 0), tcl = -0.2)
    yl <- range(c(besoin, tend, fige), na.rm = TRUE) * c(0.9, 1.1)
    plot(an, fige, type = "l", lty = 2, col = "grey50", ylim = yl, xlab = "", ylab = "", las = 1, xaxt = "n")
    axis(1, at = an)
    ok <- !is.na(besoin)
    lines(an[ok], besoin[ok], type = "b", pch = 19, col = ROUGE)
    ok <- !is.na(tend)
    lines(an[ok], tend[ok], type = "b", pch = 19, col = "#2C7FB8")
  }, res = 96)

  observeEvent(input$aide, showModal(modalDialog(
    title = "Lire la carte", easyClose = TRUE, footer = modalButton("Fermer"),
    p(strong("Zone d'une commune"), " : les communes d'où viendraient les familles. Jusqu'à 10 min de voiture, elles comptent entièrement ; ensuite de moins en moins, plus du tout à 30 min (à 20 min, pour moitié). C'est l'APL de la DREES, étendue à 30 min pour des séances hebdomadaires. Cliquer sur une commune montre sa zone en rose."),
    p(strong("Couleurs"), " : six classes de même effectif ; le plus foncé est le plus favorable à une installation (le plus élevé pour la population ou le nombre d'enfants)."),
    p(strong("Score communal"), " : concurrence 35 %, enfants 20 %, naissances 15 %, niveau de vie 15 %, CAMSP, CMPP et SESSAD 15 %, tous mesurés dans la zone. En gris : moins de 2 000 enfants dans la zone, trop peu pour un cabinet."),
    p(strong("Score départemental"), " : concurrence 35 %, évolution des enfants 25 %, niveau de vie 15 %, croissance des ergos 10 %, CAMSP, CMPP et SESSAD 15 %."),
    p(strong("Projection"), " : enfants projetés (Omphale, corrigé par les naissances locales) × densité nationale actuelle d'ergos libéraux. Deux offres : figée, ou prolongeant la hausse récente du département."),
    p(strong("Limites"), " : le RPPS ne dit pas qui travaille avec des enfants ; les PCO TND et les ergos étrangers près des frontières ne sont pas comptés ; la moyenne nationale n'est pas une norme médicale. Sur de petits effectifs, les évolutions en % s'envolent (de 1 à 13 ergos : +1 200 %)."),
    p(class = "gris", sources())
  )))
}

shinyApp(ui, server)
