# -*- coding: utf-8 -*-

def condizione(mondo, stato_runtime):
    testo = mondo.lower()
    eventi = stato_runtime.get("eventi", {})
    return eventi.get("ostacolo_destra", False) and eventi.get("camminando", False)


def comportamento():
    return {
        "stato_interno": "allerta",
        "obiettivo": "Evitare ostacolo a destra.",
        "azioni": [
            {"tipo": "occhi", "colore": "red"},
            {"tipo": "guarda", "x": 0.0, "y": -0.25},
            {"tipo": "cammina", "x": 0.16, "g": 0.12},
            {"tipo": "parla", "testo": "Attenzione, ostacolo a destra!"}
        ],
        "memoria": []
    }