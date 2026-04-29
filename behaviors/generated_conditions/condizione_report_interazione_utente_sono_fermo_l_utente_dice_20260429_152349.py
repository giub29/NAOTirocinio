# -*- coding: utf-8 -*-

def condizione(mondo, stato_runtime):
    testo = mondo.lower()
    return u"ostacolo" in testo or u"sinistra" in testo

def comportamento():
    return {
        "stato_interno": "allerta",
        "obiettivo": "evitare ostacolo a sinistra",
        "azioni": [
            {"tipo": "occhi", "colore": "red"},
            {"tipo": "guarda", "x": -0.5, "y": -0.2},
            {"tipo": "parla", "testo": "Attenzione, c'è un ostacolo a sinistra."},
            {"tipo": "fermati"}
        ],
        "memoria": []
    }