# -*- coding: utf-8 -*-

def condizione(mondo, stato_runtime):
    testo = mondo.lower()
    eventi = stato_runtime.get("eventi", {})
    return eventi.get("ostacolo_sinistra", False) and eventi.get("camminando", False)


def comportamento():
    return {
        "stato_interno": "prudente",
        "obiettivo": "evitare ostacolo",
        "azioni": [
            {"tipo": "occhi", "colore": "red"},
            {"tipo": "guarda", "x": 0.0, "y": -0.25},
            {"tipo": "parla", "testo": "Attenzione, ostacolo davanti!"},
            {"tipo": "gira", "v": 0.2}
        ],
        "memoria": []
    }