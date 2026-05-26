# -*- coding: utf-8 -*-

def condizione(mondo, stato_runtime):
    testo = mondo.lower()
    return u"carezza" in testo and u"testa" in testo and u"sto camminando" in testo


def comportamento():
    return {
        "stato_interno": "prudente",
        "obiettivo": "evitare ostacolo e rispondere alla carezza",
        "azioni": [
            {"tipo": "fermati"},
            {"tipo": "occhi", "colore": "green"},
            {"tipo": "guarda", "x": 0.5, "y": -0.2},
            {"tipo": "parla", "testo": "Grazie per la carezza!"}
        ],
        "memoria": []
    }