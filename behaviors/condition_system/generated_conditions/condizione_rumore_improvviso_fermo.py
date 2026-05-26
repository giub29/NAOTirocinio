# -*- coding: utf-8 -*-

def condizione(mondo, stato_runtime):
    testo = mondo.lower()
    eventi = stato_runtime.get("eventi", {})
    return eventi.get("rumore_improvviso", False) and eventi.get("fermo", False)


def comportamento():
    return {
        "stato_interno": "allerta",
        "obiettivo": "verificare la fonte del rumore",
        "azioni": [
            {"tipo": "occhi", "colore": "red"},
            {"tipo": "guarda", "x": 0.0, "y": -0.2},
            {"tipo": "parla", "testo": "C'è qualcuno qui?"},
            {"tipo": "fermati"}
        ],
        "memoria": []
    }