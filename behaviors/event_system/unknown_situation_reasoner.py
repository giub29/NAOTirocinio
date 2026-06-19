# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import re
import unicodedata
import logging


logger = logging.getLogger(__name__)


def _diag(label, valore):
    return None

try:
    from behaviors.event_system.visual_semantic_interpreter import (
        interpreta_contenuto_visivo
    )
except Exception:
    interpreta_contenuto_visivo = None


def _normalizza(testo):
    if not testo:
        return u""

    testo = testo.lower()
    testo = testo.replace("_", " ")
    testo = unicodedata.normalize("NFKD", testo)
    testo = u"".join(c for c in testo if not unicodedata.combining(c))
    testo = re.sub(r"[^a-z0-9\s_]", " ", testo)
    testo = re.sub(r"\s+", " ", testo).strip()
    return testo


def _contiene(testo, parole):
    return any(p in testo for p in parole)


def _ha_contesto_accesso(testo):
    return _contiene(testo, [
        "porta", "ingresso", "uscita", "accesso",
        "entrata", "varco", "passaggio", "percorso",
        "corridoio"
    ])


def _ha_limite_movimento(testo):
    return _contiene(testo, [
        "non accessibile", "non posso passare",
        "davanti al passaggio", "davanti al percorso",
        "in mezzo al percorso", "sul percorso",
        "sul passaggio", "passaggio impedito",
        "passaggio ostruito", "percorso ostruito",
        "ostacolo", "ingombro"
    ])


def _ha_oggetto_funzione_incerta(testo):
    oggetti_funzione = [
        "oggetto", "elemento", "dispositivo", "strumento",
        "macchina", "apparecchio", "contenitore", "scatola",
        "pacco", "cartone", "pulsante", "leva", "maniglia"
    ]
    segnali_funzione_possibile = [
        "etichetta", "etichette", "simbolo", "simboli",
        "meccanismo", "parti", "comando", "controllo",
        "chiuso", "chiusa", "sigillato", "sigillata",
        "funzione non chiara", "non capisco la funzione",
        "non so a cosa serve", "non e chiaro a cosa serve"
    ]
    return _contiene(testo, oggetti_funzione) and _contiene(
        testo,
        segnali_funzione_possibile
    )


def _ha_contesto_da_approfondire(testo):
    return _contiene(testo, [
        "ambiente nuovo", "zona nuova", "area nuova",
        "situazione nuova", "non riconosco la scena",
        "dettagli potenzialmente utili",
        "dettaglio potenzialmente utile",
        "contesto non chiaro", "contesto da capire"
    ])


def _categoria_stato(evento, tipo):
    evento = (evento or "").lower()
    tipo = (tipo or "").lower()

    if evento in ["accesso_non_disponibile", "accesso_o_percorso_limitato"]:
        return "accesso", "non_disponibile"

    if evento == "accesso_disponibile":
        return "accesso", "disponibile"

    if evento in ["oggetto_in_zona_rilevante", "percorso_potenzialmente_ostruito"]:
        return "ostacolo_spazio", "potenzialmente_ostruito"

    if evento == "oggetto_funzione_sconosciuta":
        return "oggetto_funzione", "da_chiarire"

    if evento in ["elemento_ambientale_anomalo", "elemento_fuori_posto"]:
        return "anomalia", "anomalo"

    if evento in ["informazione_operativa", "contenuto_informativo_rilevante"]:
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


def _arricchisci_strutturato(esito):
    evento = esito.get("evento")
    tipo = esito.get("tipo")
    categoria, stato = _categoria_stato(evento, tipo)
    significativa = bool(esito.get("significativa", False))

    esito["evento_strutturato"] = {
        "origine": "visione",
        "categoria": categoria,
        "stato": stato,
        "rilevanza": 0.75 if significativa else 0.2,
        "azione_cognitiva": esito.get("azione_cognitiva", "ignora"),
        "genera_condizione": bool(esito.get("genera_condizione", False)),
        "confidenza": 0.7 if significativa else 0.4,
        "eventi_core": [evento] if evento else []
    }

    _diag("output", esito)
    return esito


def ragiona_situazione_sconosciuta(testo):
    """
    Ragionatore cognitivo per osservazioni sconosciute.

    NON decide in base a oggetti specifici.
    Decide in base a funzioni:
    - accessibilita'
    - movimento
    - rischio
    - anomalia
    - informazione visibile
    - necessita' di seconda osservazione
    """

    _diag("input_originale", testo)
    testo = _normalizza(testo)
    _diag("input_normalizzato", testo)
    zone_rilevanti = [
        "porta", "ingresso", "uscita",
        "corridoio", "passaggio", "accesso", "entrata"
    ]

    indicatori_prossimita = [
        "vicino", "davanti", "ostruisce",
        "accanto", "in mezzo", "sul passaggio", "qualcosa"
    ]

    if (
        any(z in testo for z in zone_rilevanti)
        and any(p in testo for p in indicatori_prossimita)
    ):
        return _arricchisci_strutturato({
            "significativa": True,
            "genera_condizione": False,
            "tipo": "zona_rilevante",
            "evento": "oggetto_in_zona_rilevante",
            "ipotesi": (
                "un elemento si trova vicino a una zona funzionalmente rilevante"
            ),
            "azione_cognitiva": "osserva_con_prudenza"
        })

    if not testo:
        return _arricchisci_strutturato({
            "significativa": False,
            "genera_condizione": False,
            "tipo": "vuoto",
            "evento": None,
            "ipotesi": None,
            "azione_cognitiva": "ignora"
        })

    # 1. Significato funzionale di contenuti visivi leggibili.
    # Deve venire prima di accesso/anomalia: un cartello operativo
    # non e' un'anomalia solo perche' e' su un contenitore o una parete.
    if interpreta_contenuto_visivo is not None:
        try:
            interpretazione_visiva = interpreta_contenuto_visivo(testo)
        except Exception:
            interpretazione_visiva = {}

        if (
            isinstance(interpretazione_visiva, dict)
            and interpretazione_visiva.get("evento")
        ):
            evento_visivo = interpretazione_visiva.get("evento")
            azione_visiva = interpretazione_visiva.get(
                "azione_cognitiva",
                "osserva_e_memorizza"
            )
            return _arricchisci_strutturato({
                "significativa": interpretazione_visiva.get(
                    "rilevanza"
                ) in ["media", "alta"],
                "genera_condizione": bool(
                    interpretazione_visiva.get(
                        "genera_condizione",
                        False
                    )
                ),
                "tipo": evento_visivo,
                "evento": evento_visivo,
                "ipotesi": interpretazione_visiva.get(
                    "significato",
                    "contenuto visivo funzionalmente rilevante"
                ),
                "azione_cognitiva": azione_visiva
            })

        if isinstance(interpretazione_visiva, dict):
            categoria_visiva = interpretazione_visiva.get("categoria")
            azione_visiva = interpretazione_visiva.get("azione_cognitiva")

            if (
                categoria_visiva == "contenuto_visivo_incerto"
                or azione_visiva == "osserva_meglio"
            ):
                return _arricchisci_strutturato({
                    "significativa": False,
                    "genera_condizione": False,
                    "tipo": "contenuto_visivo_incerto",
                    "evento": None,
                    "ipotesi": interpretazione_visiva.get(
                        "significato",
                        "il contenuto informativo non e' leggibile o disponibile"
                    ),
                    "azione_cognitiva": azione_visiva or "osserva_meglio"
                })

    indicatori_ambiguita = [
        "sfocato", "sfocata",
        "lontano", "lontana",
        "confuso", "confusa",
        "non leggibile"
    ]

    if any(x in testo for x in indicatori_ambiguita):
        if _ha_oggetto_funzione_incerta(testo):
            return _arricchisci_strutturato({
                "significativa": True,
                "genera_condizione": False,
                "tipo": "oggetto_funzione_sconosciuta",
                "evento": "oggetto_funzione_sconosciuta",
                "ipotesi": (
                    "un elemento sembra avere una funzione, ma serve "
                    "osservazione mirata prima di memorizzarlo"
                ),
                "azione_cognitiva": "osserva_meglio"
            })

        return _arricchisci_strutturato({
            "significativa": False,
            "genera_condizione": False,
            "tipo": "ambiguita_visiva",
            "evento": None,
            "ipotesi": (
                "la scena osservata non e' ancora abbastanza chiara"
            ),
            "azione_cognitiva": "osserva_meglio"
        })

    # 2. Situazioni che influenzano movimento/accesso
    if (
        _ha_limite_movimento(testo)
        or (
            _ha_contesto_accesso(testo)
            and _contiene(testo, ["chius", "blocc", "ostru", "impedis"])
        )
    ):
        return _arricchisci_strutturato({
            "significativa": True,
            "genera_condizione": True,
            "tipo": "spaziale_safety",
            "evento": "accesso_o_percorso_limitato",
            "ipotesi": "qualcosa potrebbe limitare il movimento o l'accesso",
            "azione_cognitiva": "prudenza"
        })

    # 3. Situazioni anomale o danneggiate.
    # Cartelli, documenti, contenitori o armadietti non sono anomalie:
    # qui servono segnali espliciti di danno, rottura o fuori posto.
    if _contiene(testo, [
        "rotto", "rotta", "danneggiato", "danneggiata",
        "crepa", "rovinato", "anomalo", "strano",
        "fuori posto", "caduto", "caduta"
    ]):
        return _arricchisci_strutturato({
            "significativa": True,
            "genera_condizione": True,
            "tipo": "anomalia",
            "evento": "elemento_ambientale_anomalo",
            "ipotesi": "un elemento dell'ambiente sembra anomalo o fuori posto",
            "azione_cognitiva": "osserva_con_prudenza"
        })

    # 4. Informazione visiva / testo / contenuti osservabili.
    # Gerarchia:
    # - contenuto chiaramente leggibile/importante -> genera condizione
    # - supporto informativo presente ma non leggibile -> osserva_meglio
    # - assenza chiara di contenuti utili -> ignora/curiosita leggera

    supporti_informativi = [
        "schermo", "monitor", "display", "computer",
        "lavagna", "foglio", "fogli", "documento",
        "documenti", "cartello", "scritta", "scritte",
        "testo", "codice", "file", "programma",
        "interfaccia", "finestra", "terminale",
        "segni", "superfici", "dettagli visivi marcati",
        "supporto visivo"
    ]

    segnali_non_chiari = [
        "non leggibile", "non leggibili",
        "non chiaro", "non chiara", "non chiare",
        "non visibile", "non visibili",
        "non riesco a leggere",
        "non leggo",
        "scritte non chiare",
        "testo non leggibile",
        "codice non leggibile",
        "contenuto non leggibile",
        "contenuti informativi chiari",
        "senza contenuti informativi chiari",
        "parzialmente visibile",
        "parzialmente illeggibile",
        "non completamente leggibile",
        "non possibile discernere",
        "possibile discernere",
        "dettagli specifici",
        "sfocato", "sfocata", "sfocata sopra",
        "lontano", "lontana", "confusa", "confuso",
        "non e leggibile",
        "non e leggibili",
        "non e chiaro",
        "non e chiara",
        "non e chiaro",
        "senza testo leggibile",
        "nessun testo leggibile",
        "senza informazioni chiare",
        "senza contenuti informativi",
        "monitor spento",
        "schermo spento",
        "schermo nero",
        "display spento",
        "nessun elemento leggibile",
        "non ci sono elementi leggibili",
        "parte illeggibili",
        "in parte illeggibili",
        "non possibile discernere",
        "non e possibile discernere",
        "scritte non leggibili",
        "non leggibili localmente",
        "segni o scritte"
    ]

    assenza_informazione = [
        "nessun testo visibile",
        "nessuna informazione leggibile",
        "nessun testo leggibile",
        "nessun elemento leggibile",
        "non ci sono elementi leggibili",
        "non ci sono testi",
        "non ci sono contenuti",
        "non ci sono documenti",
        "non ci sono schermi",
        "non ci sono monitor",
        "non ci sono documenti testi monitor utili",
        "non ci sono documenti utili",
        "non ci sono testi utili",
        "non ci sono monitor utili",
        "non sono visibili schermi",
        "non e presente alcun testo",
        "non e presente testo",
        "senza testo",
        "senza informazioni",
        "solo muro",
        "muro bianco"
    ]

    contenuto_chiaro = [
        "testo leggibile",
        "testo visibile",
        "scritta visibile",
        "scritta leggibile",
        "contenuto leggibile",
        "informazione leggibile",
        "informazioni leggibili",
        "documento leggibile",
        "messaggio visibile",
        "errore visibile",
        "codice",
        "codice sorgente",
        "file di codice",
        "programma",
        "terminale"
    ]

    ha_supporto = _contiene(testo, supporti_informativi)
    ha_non_chiaro = _contiene(testo, segnali_non_chiari)
    ha_assenza = _contiene(testo, assenza_informazione)
    ha_contenuto_chiaro = _contiene(testo, contenuto_chiaro)

    # La negazione/inattivita' del contenuto informativo vince sui trigger
    # come "monitor", "testo", "documenti" o "schermo".
    if ha_assenza:
        return _arricchisci_strutturato({
            "significativa": False,
            "genera_condizione": False,
            "tipo": "contenuto_visivo_incerto",
            "evento": None,
            "ipotesi": "non c'e' informazione visiva utile o leggibile",
            "azione_cognitiva": "ignora"
        })

    # Caso più importante per la nuova fase:
    # c'è qualcosa che potrebbe contenere informazione, ma non è leggibile.
    if ha_supporto and ha_non_chiaro:
        return _arricchisci_strutturato({
            "significativa": True,
            "genera_condizione": False,
            "tipo": "informazione_visiva_incerta",
            "evento": None,
            "ipotesi": "vedo un possibile contenuto informativo, ma non e' abbastanza chiaro",
            "azione_cognitiva": "osserva_meglio"
        })

    # Se c'è contenuto chiaramente leggibile, allora può diventare condizione unknown.
    if ha_contenuto_chiaro:
        return _arricchisci_strutturato({
            "significativa": True,
            "genera_condizione": True,
            "tipo": "informazione_visiva",
            "evento": "contenuto_informativo_rilevante",
            "ipotesi": "c'e' informazione visiva utile osservabile",
            "azione_cognitiva": "approfondisci_osservazione"
        })

    # Se viene detto esplicitamente che non c'è nulla di utile, non generare.
    if ha_assenza and not ha_supporto:
        return _arricchisci_strutturato({
            "significativa": False,
            "genera_condizione": False,
            "tipo": "descrizione_generica",
            "evento": None,
            "ipotesi": "non c'e' informazione visiva utile",
            "azione_cognitiva": "curiosita_leggera"
        })

    # Supporto informativo presente, ma senza contenuto chiaro:
    # non genero ancora, chiedo osservazione mirata.
    if ha_supporto:
        return _arricchisci_strutturato({
            "significativa": True,
            "genera_condizione": False,
            "tipo": "supporto_informativo_potenziale",
            "evento": None,
            "ipotesi": "vedo un supporto che potrebbe contenere informazioni utili",
            "azione_cognitiva": "osserva_meglio"
        })

    if _ha_oggetto_funzione_incerta(testo):
        return _arricchisci_strutturato({
            "significativa": True,
            "genera_condizione": False,
            "tipo": "oggetto_funzione_sconosciuta",
            "evento": "oggetto_funzione_sconosciuta",
            "ipotesi": (
                "un elemento sembra avere una funzione, ma non e' ancora "
                "abbastanza chiaro da creare una condizione"
            ),
            "azione_cognitiva": "osserva_meglio"
        })

    if _ha_contesto_da_approfondire(testo):
        return _arricchisci_strutturato({
            "significativa": True,
            "genera_condizione": False,
            "tipo": "contesto_da_approfondire",
            "evento": "contesto_da_approfondire",
            "ipotesi": (
                "la scena contiene dettagli nuovi potenzialmente utili, "
                "ma non ancora una regola comportamentale"
            ),
            "azione_cognitiva": "osserva_meglio"
        })
    
    # 5. Oggetto/elemento generico interessante ma senza stato utile
    # Qui NON generiamo condizione: solo curiosità.
    if _contiene(testo, [
        "oggetto", "elemento", "dispositivo", "strumento",
        "macchina", "contenitore", "struttura", "apparecchio"
    ]):
        return _arricchisci_strutturato({
            "significativa": True,
            "genera_condizione": False,
            "tipo": "curiosita_esplorativa",
            "evento": None,
            "ipotesi": "vedo un elemento potenzialmente interessante, ma non so ancora se influenza il comportamento",
            "azione_cognitiva": "osserva_meglio"
        })

    # 6. Descrizione ambientale normale
    return _arricchisci_strutturato({
        "significativa": False,
        "genera_condizione": False,
        "tipo": "descrizione_generica",
        "evento": None,
        "ipotesi": "descrizione ambientale senza implicazioni comportamentali",
        "azione_cognitiva": "curiosita_leggera"
    })
