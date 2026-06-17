# -*- coding: utf-8 -*-
from __future__ import unicode_literals

try:
    basestring
except NameError:
    basestring = str


def _testo(valore):
    try:
        if isinstance(valore, basestring):
            return valore.lower().strip()
        return str(valore or "").lower().strip()
    except Exception:
        return ""


def _numero(valore, default=0.0):
    try:
        return float(valore)
    except Exception:
        return default


def _vero(valore):
    return valore not in [False, None, "", [], {}]


def _lista_eventi(eventi):
    if not isinstance(eventi, list):
        return []

    risultato = []
    for evento in eventi:
        if evento in [None, False, "", [], {}]:
            continue
        if evento not in risultato:
            risultato.append(evento)

    return risultato


def _evento_noto_non_generativo(categoria, origine):
    categorie_note = [
        "sociale",
        "tatto",
        "tattile",
        "audio",
        "spaziale",
        "safety"
    ]
    origini_note = [
        "tatto",
        "audio"
    ]

    return categoria in categorie_note or origine in origini_note


def _costruisci_decisione(evento, stato_interno, obiettivo, azione_memoria):
    categoria = evento.get("categoria")
    stato = evento.get("stato")
    eventi_core = _lista_eventi(evento.get("eventi_core", []))
    ipotesi_temporanea = {
        "origine": "evento_strutturato",
        "azione": azione_memoria,
        "categoria": categoria,
        "stato": stato,
        "eventi_core": eventi_core,
        "confidenza": evento.get("confidenza"),
        "rilevanza": evento.get("rilevanza"),
        "confermata": False,
        "tentativi": 0
    }

    return {
        "stato_interno": stato_interno,
        "obiettivo": obiettivo,
        "azioni": [
            {
                "tipo": "occhi",
                "colore": "yellow"
            },
            {
                "tipo": "guarda",
                "direzione": "ambiente"
            },
            {
                "tipo": "parla",
                "testo": "Osservo meglio questa situazione."
            }
        ],
        "memoria": [
            {
                "tipo": "evento_strutturato",
                "azione": azione_memoria,
                "categoria": categoria,
                "stato": stato,
                "eventi_core": eventi_core
            }
        ],
        "ipotesi_temporanea": ipotesi_temporanea
    }


def decidi_da_evento_strutturato(
    evento_strutturato,
    mondo=None,
    stato_runtime=None
):
    """
    Decide una piccola azione autonoma dal layer strutturato.

    Se la policy non ha una decisione chiara restituisce None, lasciando
    invariata la pipeline esistente di condizioni e generazione.
    """
    if not isinstance(evento_strutturato, dict):
        return None

    categoria = _testo(evento_strutturato.get("categoria"))
    origine = _testo(evento_strutturato.get("origine"))
    azione_cognitiva = _testo(evento_strutturato.get("azione_cognitiva"))
    gravita = _testo(evento_strutturato.get("gravita"))
    rilevanza = _numero(evento_strutturato.get("rilevanza"), 0.0)
    genera_condizione = _vero(
        evento_strutturato.get("genera_condizione", False)
    )

    if genera_condizione:
        return None

    if _evento_noto_non_generativo(categoria, origine):
        return None

    if categoria == "ambiguita" or azione_cognitiva == "osserva_meglio":
        return _costruisci_decisione(
            evento_strutturato,
            "curioso",
            "capire meglio una situazione ambigua",
            "osserva_meglio"
        )

    if (
        azione_cognitiva == "osserva_con_prudenza"
        or gravita in ["media", "alta"]
    ):
        return _costruisci_decisione(
            evento_strutturato,
            "prudente",
            "valutare una situazione potenzialmente rilevante",
            "osserva_con_prudenza"
        )

    if rilevanza < 0.3:
        return None

    return None
