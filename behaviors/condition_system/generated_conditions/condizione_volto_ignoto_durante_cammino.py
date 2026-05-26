# -*- coding: utf-8 -*-

def condizione(mondo, stato_runtime):
    testo = mondo.lower()
    return u"volto ignoto" in testo and u"sto camminando" in testo


def comportamento():
    return {
        "stato_interno": "allerta",
        "obiettivo": "evitare ostacolo e osservare volto",
        "azioni": [
            {"tipo": "fermati"},
            {"tipo": "occhi", "colore": "yellow"},
            {"tipo": "guarda", "x": -0.5, "y": -0.2},
            {"tipo": "parla", "testo": "Attenzione, c'è un ostacolo e vedo un volto."}
        ],
        "memoria": []
    }