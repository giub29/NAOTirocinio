# -*- coding: utf-8 -*-

def condizione(mondo, stato_runtime):
    testo = mondo.lower()
    eventi = stato_runtime.get("eventi", {})
    return eventi.get("mano_sinistra", False) and eventi.get("volto_riconosciuto", False)


def comportamento():
    return {
        "stato_interno": "curioso",
        "obiettivo": "interagire con Giulia",
        "azioni": [
            {"tipo": "occhi", "colore": "green"},
            {"tipo": "guarda", "x": 0.5, "y": -0.2},
            {"tipo": "parla", "testo": "Ciao Giulia, come stai?"},
            {"tipo": "fermati"}
        ],
        "memoria": []
    }