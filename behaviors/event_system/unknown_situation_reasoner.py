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
            "evento": "percorso_o_accesso_problematico",
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

        # 3. Informazione visiva rilevante:
    # prima filtro i casi negativi, poi accetto solo contenuto utile.
    negativi_info = [
        "non sembra contenere informazioni leggibili",
        "non sembra contenere informazione leggibile",
        "non contiene informazioni leggibili",
        "non contiene informazione leggibile",
        "non contiene codice",
        "non sembra contenere codice",
        "non ci sono schermi",
        "non ci sono documenti",
        "non ci sono schermi o documenti",
        "non ci sono monitor",
        "non sono visibili schermi",
        "nessun testo visibile",
        "nessuna informazione leggibile",
        "testo non leggibile",
        "codice non leggibile",
        "non riesco a leggere",
        "non leggo testo",
        "senza informazioni leggibili",
        "senza testo leggibile",
        "prive di attrezzatura tecnologica visibile"
    ]

    if _contiene(testo, negativi_info):
        return {
            "significativa": False,
            "genera_condizione": False,
            "tipo": "descrizione_generica",
            "evento": None,
            "ipotesi": "non c'e' informazione visiva leggibile",
            "azione_cognitiva": "curiosita_leggera"
        }

    if (
        _contiene(testo, [
            "codice",
            "codice sorgente",
            "file di codice",
            "visualizza codice",
            "testo visibile",
            "testo leggibile",
            "scritta visibile",
            "messaggio visibile",
            "errore visibile",
            "documento leggibile",
            "contenuto leggibile",
            "informazione leggibile",
            "informazioni leggibili",
            "testo visibile"
        ])
        or
        (
            _contiene(testo, [
                "schermo",
                "monitor",
                "display",
                "computer acceso",
                "documenti",
                "fogli"
            ])
            and
            _contiene(testo, [
                "codice",
                "testo",
                "leggibile",
                "informazione",
                "informazioni",
                "documento",
                "messaggio",
                "errore",
                "programma",
                "file"
            ])
        )
    ):
        return {
            "significativa": True,
            "genera_condizione": True,
            "tipo": "informazione_visiva",
            "evento": "informazione_visiva_rilevante",
            "ipotesi": "potrebbe esserci informazione utile da osservare meglio",
            "azione_cognitiva": "approfondisci_osservazione"
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