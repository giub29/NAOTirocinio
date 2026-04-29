# -*- coding: utf-8 -*-

def condizione(mondo, stato_runtime):
    return "Ostacolo a sinistra" in mondo and "sto camminando" in mondo

def comportamento():
    return {
        "stato_interno": "attento",
        "obiettivo": "evitare ostacolo",
        "azioni": [
            {"tipo": "fermati", "testo": ""},
            {"tipo": "guarda", "testo": "guarda a destra"}
        ],
        "memoria": []
    }