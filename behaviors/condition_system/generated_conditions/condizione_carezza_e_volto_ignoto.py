# -*- coding: utf-8 -*-

def condizione(mondo, stato_runtime):
    testo = mondo.lower()
    eventi = stato_runtime.get("eventi", {})
    return eventi.get("carezza_testa", False) and eventi.get("volto_ignoto", False)


def comportamento():
    return {
        "stato_interno": "curioso",
        "obiettivo": "osservare l'interazione",
        "azioni": [
            {"tipo": "occhi", "colore": "green"},
            {"tipo": "guarda", "x": 0.5, "y": -0.2},
            {"tipo": "parla", "testo": "Ciao! Chi sei?"},
            {"tipo": "fermati"}
        ],
        "memoria": []
    }