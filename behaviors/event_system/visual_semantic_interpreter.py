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

    Non riconosce oggetti specifici.
    Cerca di capire la FUNZIONE del contenuto osservato:
    - istruzione ambientale
    - regola/divieto
    - stato di accesso
    - informazione digitale
    - avviso/poster
    - contenuto leggibile generico
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

    # 1. ISTRUZIONI AMBIENTALI / OPERATIVE
    # Esempi: "conferisci qui", "inserire", "mettere", "usare", "premere".
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
            "categoria": "istruzione_ambientale",
            "evento": "istruzione_ambientale_visibile",
            "significato": "il contenuto osservato sembra indicare come usare un oggetto o uno spazio",
            "rilevanza": "alta",
            "genera_condizione": True,
            "azione_cognitiva": "interpreta_e_memorizza"
        }

    # 2. REGOLE, DIVIETI, OBBLIGHI
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
            "categoria": "regola_o_divieto",
            "evento": "regola_ambientale_visibile",
            "significato": "il contenuto osservato sembra comunicare una regola, un divieto o un avviso operativo",
            "rilevanza": "alta",
            "genera_condizione": True,
            "azione_cognitiva": "rispetta_regola"
        }

    # 3. STATO DI ACCESSO / PASSAGGIO
    if _contiene(testo, [
        "porta aperta",
        "porta chiusa",
        "chiuso",
        "aperto",
        "bloccato",
        "non accessibile",
        "entrata",
        "uscita",
        "passaggio",
        "accesso",
        "laboratorio chiuso",
        "aula chiusa"
    ]):
        return {
            "categoria": "stato_accesso",
            "evento": "stato_accesso_visibile",
            "significato": "il contenuto osservato sembra indicare lo stato di un accesso o di un passaggio",
            "rilevanza": "alta",
            "genera_condizione": True,
            "azione_cognitiva": "valuta_accesso"
        }

    # 4. INFORMAZIONE DIGITALE / TECNICA
    if (
        _contiene(testo, [
            "monitor",
            "schermo",
            "display",
            "computer",
            "terminale",
            "interfaccia"
        ])
        and
        _contiene(testo, [
            "codice",
            "programma",
            "file",
            "errore",
            "finestra",
            "testo leggibile",
            "contenuto leggibile"
        ])
    ):
        return {
            "categoria": "informazione_digitale",
            "evento": "informazione_digitale_visibile",
            "significato": "il contenuto osservato sembra provenire da un supporto digitale o tecnico",
            "rilevanza": "alta",
            "genera_condizione": True,
            "azione_cognitiva": "analizza_contenuto_digitale"
        }

    # 5. POSTER / AVVISO / INFORMAZIONE SU PARETE
    if (
        _contiene(testo, [
            "poster",
            "cartello",
            "avviso",
            "locandina",
            "foglio appeso",
            "documento appeso",
            "parete",
            "muro",
            "bacheca"
        ])
        and
        _contiene(testo, [
            "testo",
            "scritto",
            "leggibile",
            "informazione",
            "messaggio",
            "evento",
            "attivita"
        ])
    ):
        return {
            "categoria": "informazione_ambientale",
            "evento": "informazione_ambientale_visibile",
            "significato": "il contenuto osservato sembra comunicare informazioni sull'ambiente",
            "rilevanza": "media",
            "genera_condizione": True,
            "azione_cognitiva": "memorizza_informazione"
        }

    # 6. TESTO LEGGIBILE GENERICO
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
            "categoria": "contenuto_testuale_generico",
            "evento": "contenuto_testuale_visibile",
            "significato": "e' presente testo osservabile, ma la funzione non e' ancora chiara",
            "rilevanza": "media",
            "genera_condizione": False,
            "azione_cognitiva": "osserva_meglio"
        }

    return risultato_base