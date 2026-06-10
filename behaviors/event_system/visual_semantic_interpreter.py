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
    testo = re.sub(r"[^a-z0-9\s]", " ", testo)
    testo = re.sub(r"\s+", " ", testo).strip()
    return testo


def _contiene(testo, parole):
    for parola in parole:
        if parola in testo:
            return True
    return False


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

    risultato_base = {
        "categoria": "nessuna_interpretazione",
        "evento": None,
        "significato": None,
        "rilevanza": "bassa",
        "genera_condizione": False,
        "azione_cognitiva": "ignora"
    }

    if not testo:
        return risultato_base

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
        return {
            "categoria": "vincolo_azione",
            "evento": "vincolo_comportamentale",
            "significato": "il contenuto osservato limita o condiziona il comportamento possibile",
            "rilevanza": "alta",
            "genera_condizione": True,
            "azione_cognitiva": "rispetta_vincolo"
        }

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
        return {
            "categoria": "stato_accesso",
            "evento": "accesso_non_disponibile",
            "significato": "l'osservazione suggerisce che un accesso o passaggio non sia disponibile",
            "rilevanza": "alta",
            "genera_condizione": True,
            "azione_cognitiva": "valuta_accesso"
        }

    if _contiene(testo, [
        "aperto",
        "aperta",
        "accessibile",
        "passaggio libero",
        "accesso libero"
    ]):
        return {
            "categoria": "stato_accesso",
            "evento": "accesso_disponibile",
            "significato": "l'osservazione suggerisce che un accesso o passaggio sia disponibile",
            "rilevanza": "media",
            "genera_condizione": True,
            "azione_cognitiva": "valuta_esplorazione"
        }

    # 3. INFORMAZIONE OPERATIVA: indica come usare un oggetto/spazio/interfaccia.
    if _contiene(testo, [
        "conferisci qui",
        "conferire",
        "inserire",
        "inserisci",
        "mettere",
        "metti",
        "depositare",
        "usa",
        "usare",
        "premere",
        "premi",
        "seguire",
        "istruzioni",
        "indica cosa",
        "cosa conferire",
        "materiali accettabili"
    ]):
        return {
            "categoria": "informazione_operativa",
            "evento": "informazione_operativa",
            "significato": "il contenuto osservato fornisce indicazioni utili per agire o usare qualcosa",
            "rilevanza": "alta",
            "genera_condizione": True,
            "azione_cognitiva": "interpreta_e_memorizza"
        }

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
        return {
            "categoria": "contenuto_informativo",
            "evento": "contenuto_informativo_rilevante",
            "significato": "il contenuto osservato contiene informazioni potenzialmente utili per comprendere l'ambiente",
            "rilevanza": "media",
            "genera_condizione": True,
            "azione_cognitiva": "analizza_o_memorizza"
        }

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
        return {
            "categoria": "contenuto_testuale_incerto",
            "evento": "contenuto_testuale_da_approfondire",
            "significato": "e' presente testo osservabile, ma la sua funzione non e' ancora chiara",
            "rilevanza": "media",
            "genera_condizione": False,
            "azione_cognitiva": "osserva_meglio"
        }

    return risultato_base