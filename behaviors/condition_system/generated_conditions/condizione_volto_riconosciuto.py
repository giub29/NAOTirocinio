# -*- coding: utf-8 -*-

def condizione(mondo, stato_runtime):
    testo = mondo.lower()
    return u"riconosco" in testo


def comportamento():
    return {
        "stato_interno": "curioso",
        "obiettivo": "osservare il volto ignoto",
        "azioni": [
            {"tipo": "occhi", "colore": "cyan"},
            {"tipo": "guarda", "x": 0.5, "y": -0.2},
            {"tipo": "parla", "testo": "Ciao, chi sei?"},
            {"tipo": "fermati"}
        ],
        "memoria": []
    }