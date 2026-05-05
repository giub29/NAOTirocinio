# -*- coding: utf-8 -*-

def condizione(mondo, stato_runtime):
    return "Ostacolo a sinistra" in mondo

def comportamento():
    return {
        "stato_interno": "prudente",
        "obiettivo": "evitare ostacolo",
        "azioni": [
            {"tipo": "fermati"},
            {"tipo": "guarda", "x": -0.2, "y": -0.25},
            {"tipo": "occhi", "colore": "rosso"},
            {"tipo": "parla", "testo": "Attenzione, c'è un ostacolo a sinistra!"}
        ],
        "memoria": []
    }