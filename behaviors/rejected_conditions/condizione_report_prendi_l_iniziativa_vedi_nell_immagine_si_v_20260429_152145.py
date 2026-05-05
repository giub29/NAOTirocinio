# -*- coding: utf-8 -*-

def condizione(mondo, stato_runtime):
    testo = mondo.lower()
    return u"persona" in testo or u"contenitore" in testo or u"stampe" in testo

def comportamento():
    return {
        "stato_interno": "curioso",
        "obiettivo": "osservare l'ambiente",
        "azioni": [
            {"tipo": "occhi", "colore": "cyan"},
            {"tipo": "guarda", "x": -0.5, "y": -0.2},
            {"tipo": "parla", "testo": "Cosa faresti tu?"}
        ],
        "memoria": []
    }