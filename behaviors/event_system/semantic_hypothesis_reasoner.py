# -*- coding: utf-8 -*-
from __future__ import unicode_literals


def genera_ipotesi_semantica(ragionamento):
    """
    Trasforma un evento percettivo in una ipotesi funzionale.

    NON ragiona sugli oggetti.
    Ragiona sul significato operativo della scena.
    """

    if not isinstance(ragionamento, dict):
        return {}

    evento = str(
        ragionamento.get("evento", "")
    ).lower()

    if evento in [
        "informazione_operativa",
        "contenuto_informativo_rilevante"
    ]:
        return {
            "affordance": "fonte_informativa",
            "funzione_probabile":
                "fornire informazioni utili sul contesto",
            "utilita_contestuale":
                "puo aiutarmi a comprendere meglio l'ambiente",
            "conseguenza":
                "conviene memorizzare o approfondire",
            "frase_cognitiva":
                "Questo elemento sembra fornire informazioni utili sul contesto."
        }

    if evento in [
        "supporto_informativo_non_disponibile"
    ]:
        return {
            "affordance": "fonte_informativa_non_disponibile",
            "funzione_probabile":
                "fornire informazioni",
            "utilita_contestuale":
                "al momento non accessibile",
            "conseguenza":
                "devo cercare altre fonti informative",
            "frase_cognitiva":
                "Potrebbe contenere informazioni utili, ma non riesco ad accedervi."
        }

    if evento in [
        "accesso_non_disponibile",
        "accesso_o_percorso_limitato"
    ]:
        return {
            "affordance": "accesso",
            "funzione_probabile":
                "permettere o limitare il movimento",
            "utilita_contestuale":
                "influenza dove posso andare",
            "conseguenza":
                "serve prudenza",
            "frase_cognitiva":
                "Questa situazione potrebbe influenzare i miei spostamenti."
        }

    if evento == "oggetto_funzione_sconosciuta":
        return {
            "affordance": "funzione_incerta",
            "funzione_probabile":
                "non ancora chiara",
            "utilita_contestuale":
                "potrebbe essere rilevante",
            "conseguenza":
                "serve osservazione aggiuntiva",
            "frase_cognitiva":
                "Ho osservato qualcosa di cui non comprendo ancora la funzione."
        }

    if evento == "elemento_ambientale_anomalo":
        return {
            "affordance": "anomalia",
            "funzione_probabile":
                "stato anomalo dell'ambiente",
            "utilita_contestuale":
                "potrebbe richiedere attenzione",
            "conseguenza":
                "osservo con prudenza",
            "frase_cognitiva":
                "Ho rilevato qualcosa che sembra insolito."
        }

    return {}