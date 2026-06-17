# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import re
import unicodedata
import logging


logger = logging.getLogger(__name__)


def _diag(label, valore):
    return None


def _ritorna(esito):
    _diag("output", esito)
    return esito


def _normalizza(testo):
    if not testo:
        return u""

    testo = testo.lower()
    testo = testo.replace("_", " ")
    testo = unicodedata.normalize("NFKD", testo)
    testo = u"".join(c for c in testo if not unicodedata.combining(c))
    testo = re.sub(r"[^a-z0-9\s]", " ", testo)
    testo = re.sub(r"\s+", " ", testo).strip()
    return testo


def _contiene(testo, parole):
    for parola in parole:
        if parola in testo:
            return True
    return False


def _ha_supporto_informativo(testo):
    return _contiene(testo, [
        "monitor", "schermo", "display", "computer",
        "terminale", "interfaccia", "lavagna", "bacheca",
        "cartello", "cartelli", "segnale", "segnali",
        "documento", "documenti", "foglio", "fogli",
        "poster", "avviso", "locandina"
    ])


def _ha_supporto_didattico(testo):
    return _contiene(testo, [
        "lavagna", "banchi", "banco", "cattedra",
        "aula", "lezione", "proiettore"
    ])


def _ha_dispositivo_informativo(testo):
    return _contiene(testo, [
        "monitor", "schermo", "display", "computer",
        "terminale", "interfaccia", "proiettore"
    ])


def _ha_inattivita_supporto(testo):
    return _contiene(testo, [
        "monitor spento", "schermo spento", "display spento",
        "schermo nero", "non attivo", "inattivo",
        "non acceso", "spento", "spenta"
    ])


def _ha_negazione_informativa(testo):
    return _contiene(testo, [
        "non ce nulla di leggibile",
        "non c e nulla di leggibile",
        "non c e niente di leggibile",
        "nulla di leggibile",
        "niente di leggibile",
        "nessun testo leggibile",
        "nessun testo visibile",
        "nessuna informazione leggibile",
        "nessun elemento leggibile",
        "non ci sono elementi leggibili",
        "non ci sono testi",
        "non ci sono documenti",
        "non ci sono monitor",
        "non ci sono schermi",
        "non contiene informazioni leggibili",
        "non contiene testo leggibile",
        "non e presente testo",
        "non e presente alcun testo",
        "senza testo leggibile",
        "senza informazioni chiare",
        "senza contenuti informativi"
    ])


def _ha_assenza_totale_informativa(testo):
    return _contiene(testo, [
        "non ci sono elementi leggibili",
        "non ci sono testi",
        "non ci sono documenti",
        "non ci sono monitor",
        "non ci sono schermi",
        "non ci sono documenti testi monitor utili",
        "non ci sono documenti utili",
        "non ci sono testi utili",
        "non ci sono monitor utili",
        "nessun elemento leggibile",
        "nessun testo visibile",
        "nessun testo leggibile",
        "nessuna informazione leggibile"
    ])


def _ha_testo_incerto(testo):
    return _contiene(testo, [
        "testo non leggibile",
        "contenuto non leggibile",
        "cartello non leggibile",
        "scritte non leggibili",
        "non sufficientemente chiaro",
        "non abbastanza chiaro",
        "non chiaro",
        "non chiara",
        "sfocato",
        "sfocata",
        "illeggibile"
    ])

def _oggetto_in_zona_rilevante(testo):
    testo = testo.lower()

    zone_rilevanti = [
        "porta", "ingresso", "uscita",
        "corridoio", "passaggio",
        "accesso", "entrata"
    ]

    indicatori_prossimita = [
        "vicino", "davanti", "ostruisce",
        "accanto", "sul passaggio",
        "in mezzo", "qualcosa"
    ]

    presenza_zona = any(z in testo for z in zone_rilevanti)
    presenza_prossimita = any(p in testo for p in indicatori_prossimita)

    if presenza_zona and presenza_prossimita:
        return {
            "categoria": "zona_rilevante",
            "evento": "oggetto_in_zona_rilevante",
            "significato": (
                "elemento osservato vicino a una zona funzionalmente rilevante"
            ),
            "rilevanza": "media",
            "genera_condizione": False,
            "azione_cognitiva": "osserva_con_prudenza"
        }

    return None

def interpreta_contenuto_visivo(testo_osservato):
    """
    Interprete semantico visuale generalista.

    Non classifica oggetti specifici.
    Cerca l'implicazione funzionale per NAO:
    - informazione_operativa
    - vincolo_comportamentale
    - accesso_non_disponibile / accesso_disponibile
    - contenuto_informativo_rilevante
    - contenuto_testuale_da_approfondire
    """

    testo = _normalizza(testo_osservato)
    _diag("input_originale", testo_osservato)
    _diag("input_normalizzato", testo)

    zona = _oggetto_in_zona_rilevante(testo)
    if zona:
        return _ritorna(zona)

    risultato_base = {
        "categoria": "nessuna_interpretazione",
        "evento": None,
        "significato": None,
        "rilevanza": "bassa",
        "genera_condizione": False,
        "azione_cognitiva": "ignora"
    }

    if not testo:
        return _ritorna(risultato_base)

    # Semantica funzionale prima del testo: se vedo un supporto spento,
    # non e' "contenuto rilevante", ma informazione non disponibile.
    if _ha_supporto_informativo(testo) and _ha_inattivita_supporto(testo):
        return _ritorna({
            "categoria": "supporto_informativo",
            "evento": "supporto_informativo_non_disponibile",
            "significato": "un supporto informativo osservato non sembra attivo o disponibile",
            "rilevanza": "bassa",
            "genera_condizione": False,
            "azione_cognitiva": "ignora"
        })

    if (
        _ha_supporto_informativo(testo)
        and (
            _ha_assenza_totale_informativa(testo)
            or (
                _ha_dispositivo_informativo(testo)
                and _ha_negazione_informativa(testo)
            )
        )
    ):
        return _ritorna({
            "categoria": "supporto_informativo",
            "evento": "supporto_informativo_non_disponibile",
            "significato": "la scena contiene un possibile supporto informativo, ma non offre contenuto leggibile utile",
            "rilevanza": "bassa",
            "genera_condizione": False,
            "azione_cognitiva": "ignora"
        })

    ha_contenuto_chiaro_senza_negazione = (
        _contiene(testo, [
            "testo leggibile",
            "testo visibile",
            "errore visibile",
            "codice visibile"
        ])
        and not _ha_negazione_informativa(testo)
    )

    if _ha_supporto_didattico(testo) and not ha_contenuto_chiaro_senza_negazione:
        return _ritorna({
            "categoria": "contesto_ambientale",
            "evento": "ambiente_didattico_probabile",
            "significato": "la scena contiene elementi compatibili con un ambiente didattico o informativo",
            "rilevanza": "media",
            "genera_condizione": False,
            "azione_cognitiva": "osserva_meglio"
        })

    if _ha_supporto_informativo(testo) and _ha_testo_incerto(testo):
        return _ritorna({
            "categoria": "supporto_informativo",
            "evento": "supporto_informativo_potenziale",
            "significato": "un supporto informativo e' presente, ma il contenuto non e' ancora chiaro",
            "rilevanza": "media",
            "genera_condizione": False,
            "azione_cognitiva": "osserva_meglio"
        })

    # 1. VINCOLI COMPORTAMENTALI / LIMITI ALL'AZIONE
    if _contiene(testo, [
        "vietato",
        "non entrare",
        "non usare",
        "non toccare",
        "non conferire",
        "obbligo",
        "obbligatorio",
        "attenzione",
        "pericolo",
        "riservato",
        "accesso vietato",
        "solo personale",
        "uscita di emergenza"
    ]):
        return _ritorna({
            "categoria": "vincolo_azione",
            "evento": "vincolo_comportamentale",
            "significato": "il contenuto osservato limita o condiziona il comportamento possibile",
            "rilevanza": "alta",
            "genera_condizione": True,
            "azione_cognitiva": "rispetta_vincolo"
        })

    # 2. STATO FUNZIONALE DI ACCESSO / PASSAGGIO
    if _contiene(testo, [
        "chiuso",
        "chiusa",
        "bloccato",
        "bloccata",
        "non accessibile",
        "accesso impedito",
        "passaggio impedito",
        "non posso passare"
    ]):
        return _ritorna({
            "categoria": "stato_accesso",
            "evento": "accesso_non_disponibile",
            "significato": "l'osservazione suggerisce che un accesso o passaggio non sia disponibile",
            "rilevanza": "alta",
            "genera_condizione": True,
            "azione_cognitiva": "valuta_accesso"
        })

    if _contiene(testo, [
        "aperto",
        "aperta",
        "accessibile",
        "passaggio libero",
        "accesso libero"
    ]):
        return _ritorna({
            "categoria": "stato_accesso",
            "evento": "accesso_disponibile",
            "significato": "l'osservazione suggerisce che un accesso o passaggio sia disponibile",
            "rilevanza": "media",
            "genera_condizione": True,
            "azione_cognitiva": "valuta_esplorazione"
        })

    # 3. INFORMAZIONE OPERATIVA: indica come usare un oggetto/spazio/interfaccia.
    if _contiene(testo, [
        "conferisci qui",
        "conferire",
        "conferisci",
        "conferimento",
        "differenzia",
        "differenziata",
        "raccolta",
        "rifiuti",
        "carta",
        "fogli",
        "fotocopie",
        "quaderni",
        "materiale cartaceo",
        "inserire",
        "inserisci",
        "mettere",
        "metti",
        "depositare",
        "deposita",
        "usa",
        "usare",
        "premere",
        "premi",
        "spingere",
        "spingi",
        "tirare",
        "tira",
        "seguire",
        "istruzioni",
        "uscita",
        "uscire",
        "indica cosa",
        "cosa conferire",
        "materiali accettabili"
    ]):
        return _ritorna({
            "categoria": "informazione_operativa",
            "evento": "informazione_operativa",
            "significato": "il contenuto osservato fornisce indicazioni utili per agire o usare qualcosa",
            "rilevanza": "alta",
            "genera_condizione": True,
            "azione_cognitiva": "osserva_e_memorizza"
        })

    # 4. CONTENUTO INFORMATIVO RILEVANTE: digitale, cartaceo, ambientale.
    if (
        _contiene(testo, [
            "monitor", "schermo", "display", "computer",
            "terminale", "interfaccia", "poster", "cartello",
            "avviso", "locandina", "foglio appeso",
            "documento appeso", "parete", "muro", "bacheca"
        ])
        and
        _contiene(testo, [
            "codice", "programma", "file", "errore",
            "testo", "scritto", "leggibile", "informazione",
            "messaggio", "evento", "attivita",
            "contenuto leggibile"
        ])
    ):
        return _ritorna({
            "categoria": "contenuto_informativo",
            "evento": "contenuto_informativo_rilevante",
            "significato": "il contenuto osservato contiene informazioni potenzialmente utili per comprendere l'ambiente",
            "rilevanza": "media",
            "genera_condizione": True,
            "azione_cognitiva": "analizza_o_memorizza"
        })

    # 5. TESTO LEGGIBILE MA FUNZIONE ANCORA INCERTA
    if _contiene(testo, [
        "testo leggibile",
        "testi visibili",
        "testo visibile",
        "scritta",
        "scritte",
        "parole",
        "testo_visibile"
    ]):
        return _ritorna({
            "categoria": "contenuto_testuale_incerto",
            "evento": "contenuto_testuale_da_approfondire",
            "significato": "e' presente testo osservabile, ma la sua funzione non e' ancora chiara",
            "rilevanza": "media",
            "genera_condizione": False,
            "azione_cognitiva": "osserva_meglio"
        })

    return _ritorna(risultato_base)
