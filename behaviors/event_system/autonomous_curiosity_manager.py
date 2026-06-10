# -*- coding: utf-8 -*-
from __future__ import unicode_literals

try:
    from behaviors.event_system.unknown_situation_reasoner import (
        ragiona_situazione_sconosciuta
    )
except Exception:
    ragiona_situazione_sconosciuta = None


def valuta_curiosita_autonoma(testo_osservato):
    """
    Decide se una osservazione non basta per generare una condizione,
    ma merita una seconda osservazione autonoma.

    Non usa oggetti specifici come regole rigide.
    Valuta se la scena potrebbe contenere:
    - informazione
    - accesso/movimento
    - anomalia
    - elemento da comprendere meglio
    """

    if not testo_osservato:
        return {
            "approfondisci": False,
            "motivo": "nessun testo osservato",
            "azione": None,
            "frase": None
        }

    if ragiona_situazione_sconosciuta is None:
        return {
            "approfondisci": False,
            "motivo": "reasoner non disponibile",
            "azione": None,
            "frase": None
        }

    ragionamento = ragiona_situazione_sconosciuta(testo_osservato)

    # Se è già generativa, non serve curiosità:
    # sarà il generator a creare condizione.
    if ragionamento.get("genera_condizione", False):
        return {
            "approfondisci": False,
            "motivo": "situazione gia' significativa",
            "azione": None,
            "frase": None
        }

    tipo = ragionamento.get("tipo", "")

    # Curiosità leggera: non genera condizioni, ma può produrre
    # un comportamento esplorativo.
    if tipo in [
        "curiosita_esplorativa",
        "descrizione_generica"
    ]:
        testo = testo_osservato.lower()

        indicatori_da_approfondire = [
            "dispositivo",
            "strumento",
            "macchina",
            "apparecchio",
            "sistema",
            "computer",
            "monitor",
            "terminale",
            "schermo",
            "display",
            "testo",
            "scritta",
            "cartello",
            "oggetto",
            "elemento",
            "struttura",
            "porta",
            "passaggio",
            "zona",
            "area"
        ]

        for indicatore in indicatori_da_approfondire:
            if indicatore in testo:
                return {
                    "approfondisci": True,
                    "motivo": "elemento osservato potenzialmente utile ma non ancora significativo",
                    "azione": "osserva_meglio",
                    "frase": "Ho notato qualcosa che potrebbe essere utile. Lo osservo meglio prima di decidere."
                }

    return {
        "approfondisci": False,
        "motivo": "nessuna curiosita' utile",
        "azione": None,
        "frase": None
    }


def costruisci_decisione_curiosa(testo_osservato):
    """
    Crea una decisione comportamentale NON permanente.
    Non genera file condizione.
    Serve solo a guidare NAO verso una seconda osservazione.
    """

    valutazione = valuta_curiosita_autonoma(testo_osservato)

    if not valutazione.get("approfondisci", False):
        return None

    return {
        "stato_interno": "curioso",
        "obiettivo": "approfondire una osservazione potenzialmente utile",
        "azioni": [
            {
                "tipo": "occhi",
                "colore": "yellow"
            },
            {
                "tipo": "guarda",
                "x": 0.0,
                "y": -0.25
            },
            {
                "tipo": "parla",
                "testo": valutazione.get(
                    "frase",
                    "Osservo meglio questa parte dell'ambiente."
                )
            }
        ],
        "memoria": [
            {
                "tipo": "curiosita_autonoma",
                "motivo": valutazione.get("motivo", ""),
                "azione": valutazione.get("azione", "")
            }
        ]
    }