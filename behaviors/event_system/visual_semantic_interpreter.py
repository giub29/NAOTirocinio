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
        "senza testo",
        "senza informazioni",
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
        "non leggo",
        "non leggo testo",
        "non chiaro",
        "non chiara",
        "sfocato",
        "sfocata",
        "illeggibile"
    ])


def _blocco_testo_visibile(testo):
    marker = "testo visibile"
    posizione = testo.find(marker)
    while posizione >= 0:
        prima = testo[max(0, posizione - 24):posizione]
        dopo = testo[posizione + len(marker):].strip()

        prima_pulita = prima.strip()
        if (
            _contiene(prima, [
            "nessun", "nessuna", "senza", "non c e", "non ce"
            ])
            or prima_pulita.endswith("ne")
            or " ne " in prima
        ):
            posizione = testo.find(marker, posizione + len(marker))
            continue

        if not dopo:
            posizione = testo.find(marker, posizione + len(marker))
            continue

        inizio = dopo[:90]
        if _contiene(inizio, [
            "nessun testo", "nessuna informazione",
            "nessun elemento", "non e presente",
            "non ci sono"
        ]):
            posizione = testo.find(marker, posizione + len(marker))
            continue

        parole_vuote = [
            "e", "o", "ma", "report", "ocr", "sono", "fermo",
            "nessun", "nessuna", "informazione", "leggibile",
            "visibile"
        ]
        parole = [
            p for p in dopo.split()[:12]
            if p not in parole_vuote and len(p) > 1
        ]
        if parole:
            return dopo

        posizione = testo.find(marker, posizione + len(marker))

    return u""


def _ha_testo_leggibile(testo):
    if _blocco_testo_visibile(testo):
        return True

    if _ha_negazione_informativa(testo) or _ha_testo_incerto(testo):
        return False

    return _contiene(testo, [
        "testo leggibile",
        "testo visibile",
        "scritta leggibile",
        "scritta visibile",
        "scritte leggibili",
        "parole leggibili",
        "parole visibili",
        "contenuto leggibile",
        "informazione leggibile",
        "informazioni leggibili",
        "documento leggibile",
        "messaggio visibile",
        "si legge",
        "leggo"
    ])


def _ha_funzione_operativa_testuale(testo):
    if not _ha_testo_leggibile(testo):
        return False

    return _ha_indicatori_operativi(testo)


def _ha_indicatori_operativi(testo):
    indicatori_azione = [
        "vietato", "obbligo", "obbligatorio", "attenzione",
        "pericolo", "riservato", "accesso vietato",
        "solo personale", "non entrare", "non usare",
        "non toccare", "non conferire",
        "istruzioni", "procedura", "procedere",
        "seguire", "usa", "usare", "utilizzare",
        "premere", "premi", "spingere", "spingi",
        "tirare", "tira", "inserire", "inserisci",
        "mettere", "metti", "depositare", "deposita",
        "conferire", "conferisci", "conferimento",
        "differenzia", "differenziata", "differenziare",
        "materiali", "accettabili", "consentiti",
        "ammessi", "non ammessi", "destinato a",
        "destinazione", "raccolta", "elenco", "avviso",
        "fogli", "fotocopie", "quaderni"
    ]

    return _contiene(testo, indicatori_azione)


def _testo_visibile_operativo(testo):
    blocco = _blocco_testo_visibile(testo)
    if not blocco:
        return False

    # Se l'OCR espone un blocco leggibile, quel contenuto deve prevalere
    # su frasi precedenti tipo "scritte non leggibili".
    return _ha_indicatori_operativi(blocco)


def _ha_contesto_accesso(testo):
    return _contiene(testo, [
        "porta", "ingresso", "uscita", "accesso",
        "entrata", "varco", "passaggio", "percorso",
        "corridoio"
    ])


def _ha_funzione_oggetto_chiara(testo):
    oggetti_funzione = [
        "oggetto", "elemento", "dispositivo", "strumento",
        "macchina", "apparecchio", "contenitore", "scatola",
        "pacco", "cartone", "pulsante", "leva", "maniglia",
        "etichetta", "etichette", "simbolo", "simboli"
    ]

    funzione_chiara = [
        "funzione chiara", "funzione evidente", "serve per",
        "usato per", "usata per", "destinato a", "destinata a",
        "ha la funzione", "per avviare", "per aprire",
        "per chiudere", "per controllare", "per raccogliere",
        "per contenere", "per segnalare", "per guidare"
    ]

    return _contiene(testo, oggetti_funzione) and _contiene(
        testo,
        funzione_chiara
    )


def _ha_oggetto_funzione_incerta(testo):
    if _ha_testo_leggibile(testo):
        return False

    oggetti_funzione = [
        "oggetto", "elemento", "dispositivo", "strumento",
        "macchina", "apparecchio", "contenitore", "scatola",
        "pacco", "cartone", "pulsante", "leva", "maniglia"
    ]

    segnali_funzione_possibile = [
        "etichetta", "etichette", "simbolo", "simboli",
        "meccanismo", "parti", "comando", "controllo",
        "chiuso", "chiusa", "sigillato", "sigillata",
        "non capisco la funzione", "funzione non chiara",
        "non so a cosa serve", "non e chiaro a cosa serve",
        "non leggibile", "non leggibili", "illeggibile"
    ]

    return _contiene(testo, oggetti_funzione) and _contiene(
        testo,
        segnali_funzione_possibile
    )


def _ha_dettaglio_temporale_o_orientativo(testo):
    return _contiene(testo, [
        "orologio", "ora visibile", "orario visibile",
        "calendario", "data visibile", "agenda",
        "indicatore temporale", "riferimento temporale",
        "segnale direzionale", "freccia", "mappa",
        "indicatore", "segnaletica"
    ])


def _ha_supporto_visivo_non_operativo(testo):
    return (
        _ha_supporto_informativo(testo)
        and _contiene(testo, [
            "acceso", "accesa", "attivo", "attiva",
            "immagine", "figura", "grafica", "visuale",
            "astratta", "astratto", "colori", "schema"
        ])
        and not _ha_testo_leggibile(testo)
        and not _ha_indicatori_operativi(testo)
    )


def _ha_contesto_ambientale_osservabile(testo):
    return _contiene(testo, [
        "ripiano", "ripiani", "scaffale", "scaffali",
        "mensola", "mensole", "banco", "bancone",
        "tavolo", "tavoli", "sedie", "sedia",
        "postazione", "postazioni", "area di lavoro",
        "oggetti disposti", "oggetti appoggiati",
        "materiali appoggiati", "contenitori", "strumenti",
        "arredi", "zona organizzata"
    ])


def _dettaglio_funzionale_osservabile(testo):
    if _ha_funzione_oggetto_chiara(testo) and not _ha_funzione_operativa_testuale(testo):
        return {
            "categoria": "oggetto_funzione",
            "evento": "oggetto_funzione_sconosciuta",
            "significato": "la funzione di un elemento osservato e' diventata utile per decisioni future",
            "rilevanza": "alta",
            "genera_condizione": True,
            "azione_cognitiva": "memorizza_funzione"
        }

    if _ha_dettaglio_temporale_o_orientativo(testo):
        return {
            "categoria": "contesto_ambientale",
            "evento": "dettaglio_funzionale_osservabile",
            "significato": (
                "la scena contiene un dettaglio funzionale osservabile "
                "potenzialmente utile per orientamento o decisioni future"
            ),
            "rilevanza": "media",
            "genera_condizione": False,
            "azione_cognitiva": "interpreta_contesto"
        }

    if _ha_supporto_visivo_non_operativo(testo):
        return {
            "categoria": "supporto_informativo",
            "evento": "supporto_informativo_potenziale",
            "significato": (
                "un supporto visivo e' presente, ma il contenuto non sembra "
                "ancora operativo o testuale"
            ),
            "rilevanza": "media",
            "genera_condizione": False,
            "azione_cognitiva": "osserva_meglio"
        }

    if _ha_contesto_ambientale_osservabile(testo):
        return {
            "categoria": "contesto_ambientale",
            "evento": "contesto_da_approfondire",
            "significato": (
                "la scena contiene elementi ambientali osservabili che "
                "possono aiutare a comprenderne la funzione"
            ),
            "rilevanza": "media",
            "genera_condizione": False,
            "azione_cognitiva": "interpreta_contesto"
        }

    return None


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
    - oggetto_funzione_sconosciuta
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

    if _testo_visibile_operativo(testo):
        return _ritorna({
            "categoria": "informazione",
            "evento": "informazione_operativa",
            "significato": "il blocco TESTO_VISIBILE contiene indicazioni pratiche utili per agire",
            "rilevanza": "alta",
            "genera_condizione": True,
            "azione_cognitiva": "osserva_e_memorizza"
        })

    if _blocco_testo_visibile(testo):
        return _ritorna({
            "categoria": "informazione",
            "evento": "contenuto_informativo_rilevante",
            "significato": "il blocco TESTO_VISIBILE contiene testo leggibile utile per comprendere il contesto",
            "rilevanza": "media",
            "genera_condizione": False,
            "azione_cognitiva": "interpreta_contenuto"
        })

    dettaglio = _dettaglio_funzionale_osservabile(testo)
    if dettaglio:
        return _ritorna(dettaglio)

    if _ha_assenza_totale_informativa(testo):
        return _ritorna({
            "categoria": "supporto_informativo",
            "evento": "supporto_informativo_non_disponibile",
            "significato": "la scena non contiene contenuti informativi leggibili o disponibili",
            "rilevanza": "bassa",
            "genera_condizione": False,
            "azione_cognitiva": "ignora"
        })

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
            _ha_dispositivo_informativo(testo)
            and _ha_negazione_informativa(testo)
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

    if (
        _ha_supporto_didattico(testo)
        and not ha_contenuto_chiaro_senza_negazione
        and not _ha_testo_leggibile(testo)
    ):
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

    if _ha_oggetto_funzione_incerta(testo):
        return _ritorna({
            "categoria": "oggetto_funzione",
            "evento": "oggetto_funzione_sconosciuta",
            "significato": "un elemento sembra avere una funzione, ma non e' ancora chiaro come usarlo o interpretarlo",
            "rilevanza": "media",
            "genera_condizione": False,
            "azione_cognitiva": "osserva_meglio"
        })

    # 1. TESTO LEGGIBILE CHE LIMITA ACCESSO/PASSAGGIO.
    if (
        _ha_testo_leggibile(testo)
        and _contiene(testo, [
            "vietato entrare",
            "accesso vietato",
            "non entrare",
            "ingresso vietato",
            "accesso riservato",
            "solo personale"
        ])
    ):
        return _ritorna({
            "categoria": "accesso",
            "evento": "accesso_non_disponibile",
            "significato": "il contenuto leggibile indica che l'accesso e' limitato o non disponibile",
            "rilevanza": "alta",
            "genera_condizione": True,
            "azione_cognitiva": "usa_informazione"
        })

    # 2. TESTO LEGGIBILE CON FUNZIONE PRATICA.
    # Non dipende dall'oggetto osservato: conta che il contenuto dica
    # cosa fare, cosa evitare, come usare qualcosa o quali materiali/azioni
    # sono ammessi.
    if _ha_funzione_operativa_testuale(testo):
        return _ritorna({
            "categoria": "informazione",
            "evento": "informazione_operativa",
            "significato": "il contenuto leggibile fornisce indicazioni pratiche utili per agire",
            "rilevanza": "alta",
            "genera_condizione": True,
            "azione_cognitiva": "osserva_e_memorizza"
        })

    # 3. VINCOLI COMPORTAMENTALI / LIMITI ALL'AZIONE
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

    # 4. STATO FUNZIONALE DI ACCESSO / PASSAGGIO
    if _ha_contesto_accesso(testo) and _contiene(testo, [
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

    if _ha_contesto_accesso(testo) and _contiene(testo, [
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

    if _ha_funzione_oggetto_chiara(testo):
        return _ritorna({
            "categoria": "oggetto_funzione",
            "evento": "oggetto_funzione_sconosciuta",
            "significato": "la funzione di un elemento osservato e' diventata utile per decisioni future",
            "rilevanza": "alta",
            "genera_condizione": True,
            "azione_cognitiva": "memorizza_funzione"
        })

    # 5. INFORMAZIONE OPERATIVA: indica come usare un oggetto/spazio/interfaccia.
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
            "categoria": "informazione",
            "evento": "informazione_operativa",
            "significato": "il contenuto osservato fornisce indicazioni utili per agire o usare qualcosa",
            "rilevanza": "alta",
            "genera_condizione": True,
            "azione_cognitiva": "osserva_e_memorizza"
        })

    # 6. CONTENUTO INFORMATIVO RILEVANTE: digitale, cartaceo, ambientale.
    if (
        _contiene(testo, [
            "monitor", "schermo", "display", "computer",
            "terminale", "interfaccia", "poster", "cartello",
            "avviso", "locandina", "foglio appeso",
            "documento appeso", "parete", "muro", "bacheca"
        ])
        and not _ha_negazione_informativa(testo)
        and
        _contiene(testo, [
            "codice", "programma", "file", "errore",
            "testo", "scritto", "leggibile", "informazione",
            "messaggio", "evento", "attivita",
            "contenuto leggibile"
        ])
    ):
        genera_contenuto_digitale = _contiene(testo, [
            "codice", "programma", "file", "errore", "terminale"
        ])
        return _ritorna({
            "categoria": "contenuto_informativo",
            "evento": "contenuto_informativo_rilevante",
            "significato": "il contenuto osservato contiene informazioni potenzialmente utili per comprendere l'ambiente",
            "rilevanza": "media",
            "genera_condizione": genera_contenuto_digitale,
            "azione_cognitiva": "analizza_o_memorizza"
        })

    # 7. TESTO LEGGIBILE MA NON CHIARAMENTE OPERATIVO.
    if (
        not _ha_testo_incerto(testo)
        and (
            _ha_testo_leggibile(testo)
            or _contiene(testo, [
                "testo leggibile",
                "testi visibili",
                "testo visibile",
                "scritta",
                "scritte",
                "parole",
                "testo_visibile"
            ])
        )
    ):
        return _ritorna({
            "categoria": "informazione",
            "evento": "contenuto_informativo_rilevante",
            "significato": "e' presente testo leggibile utile per comprendere il contesto",
            "rilevanza": "media",
            "genera_condizione": False,
            "azione_cognitiva": "interpreta_contenuto"
        })

    return _ritorna(risultato_base)
