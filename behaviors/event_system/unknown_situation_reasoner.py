# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import re
import unicodedata


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

    testo = _normalizza(testo)

    if not testo:
        return {
            "significativa": False,
            "genera_condizione": False,
            "tipo": "vuoto",
            "evento": None,
            "ipotesi": None,
            "azione_cognitiva": "ignora"
        }

    # 1. Situazioni che influenzano movimento/accesso
    if _contiene(testo, [
        "chius", "blocc", "ostru", "impedis",
        "non accessibile", "non posso passare",
        "davanti al passaggio", "davanti al percorso",
        "in mezzo al percorso", "sul percorso",
        "ostacolo", "ingombro"
    ]):
        return {
            "significativa": True,
            "genera_condizione": True,
            "tipo": "spaziale_safety",
            "evento": "accesso_o_percorso_limitato",
            "ipotesi": "qualcosa potrebbe limitare il movimento o l'accesso",
            "azione_cognitiva": "prudenza"
        }

    # 2. Situazioni anomale o danneggiate
    if _contiene(testo, [
        "rotto", "rotta", "danneggiato", "danneggiata",
        "crepa", "rovinato", "anomalo", "strano",
        "fuori posto", "caduto", "caduta"
    ]):
        return {
            "significativa": True,
            "genera_condizione": True,
            "tipo": "anomalia",
            "evento": "elemento_ambientale_anomalo",
            "ipotesi": "un elemento dell'ambiente sembra anomalo o fuori posto",
            "azione_cognitiva": "osserva_con_prudenza"
        }

    # 3. Informazione visiva / testo / contenuti osservabili.
    # Gerarchia:
    # - contenuto chiaramente leggibile/importante -> genera condizione
    # - supporto informativo presente ma non leggibile -> osserva_meglio
    # - assenza chiara di contenuti utili -> ignora/curiosita leggera

    supporti_informativi = [
        "schermo", "monitor", "display", "computer",
        "lavagna", "foglio", "fogli", "documento",
        "documenti", "cartello", "scritta", "scritte",
        "testo", "codice", "file", "programma",
        "interfaccia", "finestra", "terminale"
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
        "lontano", "lontana"
        "non e leggibile",
        "non e leggibili",
        "non e chiaro",
        "non e chiara",
        "non e chiaro",
        "parte illeggibili",
        "in parte illeggibili",
        "non possibile discernere",
        "non e possibile discernere",
        "testo scritto",
        "testo sulla lavagna"
    ]

    assenza_informazione = [
        "nessun testo visibile",
        "nessuna informazione leggibile",
        "non ci sono testi",
        "non ci sono contenuti",
        "non ci sono documenti",
        "non ci sono schermi",
        "non ci sono monitor",
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

    # Caso più importante per la nuova fase:
    # c'è qualcosa che potrebbe contenere informazione, ma non è leggibile.
    if ha_supporto and ha_non_chiaro:
        return {
            "significativa": True,
            "genera_condizione": False,
            "tipo": "informazione_visiva_incerta",
            "evento": None,
            "ipotesi": "vedo un possibile contenuto informativo, ma non e' abbastanza chiaro",
            "azione_cognitiva": "osserva_meglio"
        }

    # Se c'è contenuto chiaramente leggibile, allora può diventare condizione unknown.
    if ha_contenuto_chiaro:
        return {
            "significativa": True,
            "genera_condizione": True,
            "tipo": "informazione_visiva",
            "evento": "contenuto_informativo_rilevante",
            "ipotesi": "c'e' informazione visiva utile osservabile",
            "azione_cognitiva": "approfondisci_osservazione"
        }

    # Se viene detto esplicitamente che non c'è nulla di utile, non generare.
    if ha_assenza and not ha_supporto:
        return {
            "significativa": False,
            "genera_condizione": False,
            "tipo": "descrizione_generica",
            "evento": None,
            "ipotesi": "non c'e' informazione visiva utile",
            "azione_cognitiva": "curiosita_leggera"
        }

    # Supporto informativo presente, ma senza contenuto chiaro:
    # non genero ancora, chiedo osservazione mirata.
    if ha_supporto:
        return {
            "significativa": True,
            "genera_condizione": False,
            "tipo": "supporto_informativo_potenziale",
            "evento": None,
            "ipotesi": "vedo un supporto che potrebbe contenere informazioni utili",
            "azione_cognitiva": "osserva_meglio"
        }
    
    # 4. Oggetto/elemento generico interessante ma senza stato utile
    # Qui NON generiamo condizione: solo curiosità.
    if _contiene(testo, [
        "oggetto", "elemento", "dispositivo", "strumento",
        "macchina", "contenitore", "struttura", "apparecchio"
    ]):
        return {
            "significativa": True,
            "genera_condizione": False,
            "tipo": "curiosita_esplorativa",
            "evento": None,
            "ipotesi": "vedo un elemento potenzialmente interessante, ma non so ancora se influenza il comportamento",
            "azione_cognitiva": "osserva_meglio"
        }

    # 5. Descrizione ambientale normale
    return {
        "significativa": False,
        "genera_condizione": False,
        "tipo": "descrizione_generica",
        "evento": None,
        "ipotesi": "descrizione ambientale senza implicazioni comportamentali",
        "azione_cognitiva": "curiosita_leggera"
    }