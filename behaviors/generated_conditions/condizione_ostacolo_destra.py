# -*- coding: utf-8 -*-

def condizione(mondo, stato_runtime):
    testo = mondo.lower()
    return u"qualcosa" in testo or u"destra" in testo

def comportamento():
    return {
        "stato_interno": "prudente",
        "obiettivo": "osservare l'oggetto a destra",
        "azioni": [
            {"tipo": "occhi", "colore": "green"},
            {"tipo": "guarda", "x": 0.5, "y": -0.2},
            {"tipo": "parla", "testo": "Cosa c'è a destra?"},
            {"tipo": "fermati"}
        ],
        "memoria": []
    }