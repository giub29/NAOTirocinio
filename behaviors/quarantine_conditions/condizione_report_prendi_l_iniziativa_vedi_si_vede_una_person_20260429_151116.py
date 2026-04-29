# -*- coding: utf-8 -*-

def condizione(mondo, stato_runtime):
    testo = mondo.lower()
    return u"persona" in testo or u"monitor" in testo or u"decorativi" in testo

def comportamento():
    return {
        "stato_interno": "curioso",
        "obiettivo": "osservare e interagire",
        "azioni": [
            {"tipo": "occhi", "colore": "cyan"},
            {"tipo": "guarda", "x": 0.5, "y": -0.2},
            {"tipo": "parla", "testo": "Cosa faresti tu?"},
            {"tipo": "fermati"}
        ],
        "memoria": []
    }