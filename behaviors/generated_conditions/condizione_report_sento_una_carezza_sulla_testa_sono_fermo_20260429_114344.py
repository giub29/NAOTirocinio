# -*- coding: utf-8 -*-

def condizione(mondo, stato_runtime):
    return u"carezza sulla testa" in mondo

def comportamento():
    return {
        "stato_interno": "contento",
        "obiettivo": "rispondere alla carezza",
        "azioni": [
            {"tipo": "parla", "testo": "Grazie per la carezza!"},
            {"tipo": "occhi", "stato": "felice"}
        ],
        "memoria": []
    }