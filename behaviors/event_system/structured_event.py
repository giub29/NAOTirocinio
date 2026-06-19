# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import re
import unicodedata
import logging


logger = logging.getLogger(__name__)


def _diag(label, valore):
    return None

try:
    basestring
except NameError:
    basestring = str

try:
    text_type = unicode
except NameError:
    text_type = str

try:
    from behaviors.event_system.unknown_situation_reasoner import (
        ragiona_situazione_sconosciuta
    )
except Exception:
    ragiona_situazione_sconosciuta = None


def _normalizza(testo):
    if not testo:
        return u""

    if isinstance(testo, text_type):
        testo_unicode = testo
    else:
        try:
            testo_unicode = testo.decode("utf-8")
        except Exception:
            try:
                testo_unicode = text_type(testo)
            except Exception:
                testo_unicode = u""

    testo_unicode = testo_unicode.lower()
    testo_unicode = unicodedata.normalize("NFKD", testo_unicode)
    testo_unicode = u"".join(
        c for c in testo_unicode
        if not unicodedata.combining(c)
    )
    testo_unicode = re.sub(u"[^a-z0-9\\s_]", u" ", testo_unicode)
    testo_unicode = re.sub(u"\\s+", u" ", testo_unicode).strip()
    return testo_unicode

def _eventi_booleani(eventi_grezzi):
    eventi = {}

    if not isinstance(eventi_grezzi, dict):
        return eventi

    sorgenti = [
        eventi_grezzi,
        eventi_grezzi.get("eventi", {}),
        eventi_grezzi.get("eventi_reali", {}),
        eventi_grezzi.get("eventi_booleani", {})
    ]

    for sorgente in sorgenti:
        if not isinstance(sorgente, dict):
            continue

        for chiave, valore in sorgente.items():
            if valore not in [False, None, "", [], {}]:
                eventi[chiave] = valore

    return eventi


def _evento_attivo(eventi, nome):
    if not isinstance(eventi, dict):
        return False

    return eventi.get(nome) not in [False, None, "", [], {}]


def _sanitizza_eventi_supporto_informativo(eventi):
    if not isinstance(eventi, dict):
        return eventi

    eventi_forti = [
        "informazione_operativa",
        "contenuto_informativo_rilevante",
        "vincolo_comportamentale",
        "accesso_non_disponibile",
        "accesso_disponibile",
        "accesso_o_percorso_limitato",
        "oggetto_in_zona_rilevante",
        "oggetto_funzione_sconosciuta",
        "elemento_ambientale_anomalo",
        "elemento_fuori_posto"
    ]

    if any(_evento_attivo(eventi, nome) for nome in eventi_forti):
        eventi.pop("supporto_informativo_potenziale", None)
        eventi.pop("supporto_informativo_non_disponibile", None)
        return eventi

    if _evento_attivo(eventi, "supporto_informativo_non_disponibile"):
        eventi.pop("supporto_informativo_potenziale", None)

    return eventi


def _origine_da_mondo(testo, eventi):
    if any(k in eventi for k in [
        "mano_destra",
        "mano_sinistra",
        "entrambe_mani",
        "carezza_testa",
        "urto_piedi",
        "piede_sinistro",
        "piede_destro"
    ]):
        return "tatto"

    if any(k in eventi for k in [
        "rumore_improvviso",
        "rumore_singolo",
        "battiti_mani"
    ]):
        return "audio"

    if "vedo" in testo or "osservazione" in testo or "immagine" in testo:
        return "visione"

    return "report"


def _base_evento(mondo, eventi):
    testo = _normalizza(mondo)
    origine = _origine_da_mondo(testo, eventi)

    return {
        "origine": origine,
        "testo_originale": mondo or "",
        "categoria": "neutra",
        "stato": "osservato",
        "rilevanza": 0.0,
        "azione_cognitiva": "ignora",
        "genera_condizione": False,
        "confidenza": 0.0,
        "eventi_booleani": dict(eventi),
        # Campi legacy usati dalla pipeline attuale.
        "tipo": "generico",
        "direzione": None,
        "gravita": "bassa",
        "camminando": bool(eventi.get("camminando", False)),
        "fermo": bool(eventi.get("fermo", False)),
        "durante_cammino": bool(eventi.get("camminando", False)),
        "eventi": dict(eventi),
        "eventi_attivi": [
            k for k, v in eventi.items()
            if v not in [False, None, "", [], {}]
        ],
        "eventi_core": [],
        "evento_composto": False
    }


def _applica_evento_noto(evento, eventi):
    mapping = [
        ("pericolo", "pericolo", "safety", "critico", 1.0, "fermati", True, "alta", None),
        ("urto_piedi", "urto_piedi", "safety", "contatto", 1.0, "fermati", True, "alta", None),
        ("ostacolo_frontale", "ostacolo", "spaziale", "presente", 0.85, "osserva_con_prudenza", False, "media", "frontale"),
        ("ostacolo_destra", "ostacolo", "spaziale", "presente", 0.8, "osserva_con_prudenza", False, "media", "destra"),
        ("ostacolo_sinistra", "ostacolo", "spaziale", "presente", 0.8, "osserva_con_prudenza", False, "media", "sinistra"),
        ("carezza_testa", "carezza", "sociale", "rilevato", 0.6, "risposta_sociale_controllata", False, "bassa", None),
        ("entrambe_mani", "tocco_mani", "sociale", "rilevato", 0.65, "risposta_sociale_controllata", False, "bassa", None),
        ("mano_sinistra", "tocco_mano", "sociale", "rilevato", 0.6, "risposta_sociale_controllata", False, "bassa", "sinistra"),
        ("mano_destra", "tocco_mano", "sociale", "rilevato", 0.6, "risposta_sociale_controllata", False, "bassa", "destra"),
        ("volto_riconosciuto", "volto_riconosciuto", "sociale", "rilevato", 0.55, "risposta_sociale_controllata", False, "bassa", None),
        ("volto_ignoto", "volto_ignoto", "sociale", "rilevato", 0.5, "risposta_sociale_controllata", False, "bassa", None),
        ("rumore_improvviso", "rumore_improvviso", "audio", "rilevato", 0.55, "osserva_con_prudenza", False, "media", None)
    ]

    for chiave, tipo, categoria, stato, rilevanza, azione, genera, gravita, direzione in mapping:
        if not eventi.get(chiave, False):
            continue

        evento.update({
            "tipo": tipo,
            "categoria": categoria,
            "stato": stato,
            "rilevanza": rilevanza,
            "azione_cognitiva": azione,
            "genera_condizione": genera,
            "confidenza": 0.9,
            "gravita": gravita,
            "direzione": direzione,
            "eventi_core": [chiave]
        })
        return True

    return False


def _categoria_da_ragionamento(ragionamento):
    evento = str(ragionamento.get("evento", "") or "").lower()
    tipo = str(ragionamento.get("tipo", "") or "").lower()

    if evento in [
        "accesso_non_disponibile",
        "accesso_o_percorso_limitato"
    ]:
        return "accesso", "non_disponibile"

    if evento == "accesso_disponibile":
        return "accesso", "disponibile"

    if evento in [
        "oggetto_in_zona_rilevante",
        "percorso_potenzialmente_ostruito"
    ] or tipo in ["zona_rilevante", "spaziale_safety"]:
        return "ostacolo_spazio", "potenzialmente_ostruito"

    if evento == "oggetto_funzione_sconosciuta":
        return "oggetto_funzione", "da_chiarire"

    if evento in [
        "elemento_ambientale_anomalo",
        "elemento_fuori_posto"
    ] or tipo == "anomalia":
        return "anomalia", "anomalo"

    if evento in [
        "informazione_operativa",
        "contenuto_informativo_rilevante"
    ] or tipo == "informazione_visiva":
        return "informazione", "rilevante"

    if evento == "vincolo_comportamentale":
        return "informazione", "vincolo"

    if evento == "supporto_informativo_non_disponibile":
        return "supporto_informativo", "non_disponibile"

    if evento == "supporto_informativo_potenziale":
        return "supporto_informativo", "potenziale"

    if tipo in [
        "informazione_visiva_incerta",
        "supporto_informativo_potenziale",
        "ambiguita_visiva",
        "contenuto_testuale_incerto"
    ]:
        return "ambiguita", "incerto"

    if evento == "contenuto_testuale_da_approfondire":
        return "ambiguita", "incerto"

    if evento == "ambiente_didattico_probabile":
        return "contesto_ambientale", "didattico_probabile"

    if evento == "contesto_da_approfondire":
        return "contesto_ambientale", "da_approfondire"

    return "neutra", "osservato"


def _applica_ragionamento(evento, mondo):
    if ragiona_situazione_sconosciuta is None:
        return

    try:
        ragionamento = ragiona_situazione_sconosciuta(mondo)
    except Exception:
        ragionamento = {}

    if not isinstance(ragionamento, dict):
        ragionamento = {}

    categoria, stato = _categoria_da_ragionamento(ragionamento)
    significativa = bool(ragionamento.get("significativa", False))
    genera = bool(ragionamento.get("genera_condizione", False))
    azione = ragionamento.get("azione_cognitiva") or "ignora"
    nome_evento = ragionamento.get("evento")
    rilevanza = 0.75 if significativa else 0.2
    confidenza = 0.7 if significativa else 0.4

    if categoria == "ambiguita" or str(azione).lower() == "osserva_meglio":
        rilevanza = max(rilevanza, 0.7)
        confidenza = max(confidenza, 0.6)

    evento.update({
        "categoria": categoria,
        "stato": stato,
        "rilevanza": rilevanza,
        "azione_cognitiva": azione,
        "genera_condizione": genera,
        "confidenza": confidenza,
        "tipo": nome_evento or ragionamento.get("tipo", "generico"),
        "ragionamento_unknown": ragionamento
    })

    if nome_evento:
        evento["eventi_core"] = [nome_evento]

    if categoria in ["accesso", "ostacolo_spazio", "anomalia"]:
        evento["gravita"] = "media"


def costruisci_evento_strutturato(mondo, eventi_grezzi=None):
    """
    Costruisce un layer strutturato sopra report e booleani esistenti.

    Non sostituisce la pipeline string-based: aggiunge una vista stabile che
    puo' essere salvata in stato_runtime["evento_strutturato"].
    """
    _diag("input_mondo", mondo)
    _diag("input_eventi_grezzi", eventi_grezzi)

    eventi = _sanitizza_eventi_supporto_informativo(
        _eventi_booleani(eventi_grezzi)
    )
    evento = _base_evento(mondo, eventi)

    if not _applica_evento_noto(evento, eventi):
        _applica_ragionamento(evento, mondo)

    eventi_core = evento.get("eventi_core", [])
    if not isinstance(eventi_core, list):
        eventi_core = []

    evento["evento_composto"] = len(eventi_core) >= 2
    if evento.get("camminando") and len(eventi_core) >= 1:
        evento["evento_composto"] = True

    _diag("output", evento)
    return evento
