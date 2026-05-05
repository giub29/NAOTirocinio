# -*- coding: utf-8 -*-

def condizione(mondo, stato_runtime):
    return u"carezza" in mondo and u"ostacolo" in stato_runtime["ultimo_evento"]

def comportamento():
    return {
        "stato_interno": "prudente",
        "obiettivo": "evitare ostacolo e interagire",
        "azioni": [
            {"tipo": "occhi", "colore": "green"},
            {"tipo": "guarda", "x": 0.5, "y": -0.2},
            {"tipo": "parla", "testo": "Ciao Giulia, sto evitando un ostacolo."},
            {"tipo": "fermati"}
        ],
        "memoria": []
    }