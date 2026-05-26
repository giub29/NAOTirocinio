# -*- coding: utf-8 -*-

def condizione(mondo, stato_runtime):
    testo = mondo.lower()
    eventi = stato_runtime.get("eventi", {})
    return eventi.get("rumore_improvviso", False) and eventi.get("camminando", False)


def comportamento():
    return {
        "stato_interno": "allerta",
        "obiettivo": "evitare ostacolo",
        "azioni": [
            {"tipo": "occhi", "colore": "red"},
            {"tipo": "guarda", "x": -0.5, "y": -0.2},
            {"tipo": "cammina", "x": 0.16, "g": -0.12},
            {"tipo": "parla", "testo": "Attenzione, ostacolo a sinistra!"}
        ],
        "memoria": []
    }