# -*- coding: utf-8 -*-

def condizione(mondo, stato_runtime):
    testo = mondo.lower()
    return u"scrivania" in testo or u"computer" in testo or u"sedie" in testo

def comportamento():
    return {
        "stato_interno": "curioso",
        "obiettivo": "osservare l'ambiente",
        "azioni": [
            {"tipo": "occhi", "colore": "green"},
            {"tipo": "guarda", "x": 0.5, "y": -0.2},
            {"tipo": "parla", "testo": "Cosa faresti tu?"}
        ],
        "memoria": []
    }