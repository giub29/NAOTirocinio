# -*- coding: utf-8 -*-

def condizione(mondo, stato_runtime):
    testo = mondo.lower()
    return u"sedia" in testo or u"computer" in testo or u"oggetto" in testo

def comportamento():
    return {
        "stato_interno": "curioso",
        "obiettivo": "osservare l'ufficio",
        "azioni": [
            {"tipo": "occhi", "colore": "cyan"},
            {"tipo": "guarda", "x": 0.5, "y": -0.2},
            {"tipo": "parla", "testo": "Cosa faresti tu?"}
        ],
        "memoria": []
    }