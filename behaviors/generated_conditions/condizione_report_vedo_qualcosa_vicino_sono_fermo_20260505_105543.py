# -*- coding: utf-8 -*-

def condizione(mondo, stato_runtime):
    testo = mondo.lower()
    return u"qualcosa vicino" in testo or u"ostacolo" in testo

def comportamento():
    return {
        "stato_interno": "allerta",
        "obiettivo": "evitare ostacolo",
        "azioni": [
            {"tipo": "occhi", "colore": "yellow"},
            {"tipo": "guarda", "x": 0.5, "y": -0.2},
            {"tipo": "parla", "testo": "Attenzione, c'è qualcosa qui vicino."},
            {"tipo": "fermati"}
        ],
        "memoria": []
    }