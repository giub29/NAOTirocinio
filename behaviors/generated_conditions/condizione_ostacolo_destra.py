# -*- coding: utf-8 -*-

def condizione(mondo, stato_runtime):
    testo = mondo.lower()
    return u"ostacolo" in testo and u"destra" in testo


def comportamento():
    return {
        "stato_interno": "allerta",
        "obiettivo": "evitare ostacolo",
        "azioni": [
            {"tipo": "fermati"},
            {"tipo": "occhi", "colore": "red"},
            {"tipo": "guarda", "x": 0.5, "y": -0.2},
            {"tipo": "parla", "testo": "Attenzione, ostacolo rilevato a destra!"}
        ],
        "memoria": []
    }