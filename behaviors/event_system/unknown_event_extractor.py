# -*- coding: utf-8 -*-
"""
Estrattore prudente di eventi sconosciuti.

Obiettivo:
- riconoscere concetti nuovi nel report sensoriale;
- trasformarli in eventi candidati riusabili;
- NON modificare condizioni autogenerate;
- NON chiamare LLM;
- NON eseguire azioni su NAO.

Questo modulo prepara il passaggio:
testo sensoriale nuovo -> evento candidato -> futura condizione autonoma.
"""

import re
try:
    from behaviors.event_system.event_novelty_memory import registra_evento_sconosciuto
except Exception:
    registra_evento_sconosciuto = None

PAROLE_BANALI = [
    "report",
    "evento",
    "recente",
    "sento",
    "vedo",
    "rilevo",
    "percepisco",
    "sono",
    "fermo",
    "sto",
    "camminando",
    "una",
    "uno",
    "un",
    "il",
    "lo",
    "la",
    "gli",
    "le",
    "di",
    "a",
    "da",
    "in",
    "con",
    "su",
    "sul",
    "sulla",
    "sullo",
    "al",
    "allo",
    "alla",
    "ai",
    "agli",
    "alle",
    "dal",
    "dallo",
    "dalla",
    "dai",
    "dagli",
    "dalle",
    "del",
    "dello",
    "della",
    "dei",
    "degli",
    "delle",
    "nel",
    "nello",
    "nella",
    "nei",
    "negli",
    "nelle",
    "col",
    "coi",

    # marcatori tecnici/autonomi
    "prendi",
    "liniziativa",
    "iniziativa",
    "osservazione",
    "autonoma",
    "autonomo",
    "autonomamente",

    # parole troppo generiche
    "destra",
    "sinistra",
    "qualcosa",
    "persona",
    "volto",
    "mano",
    "testa",
    "piede",
    "ostacolo",
    "rumore",
    "tocco",
    "carezza"
]

PAROLE_NOTE = [
    "mano_destra",
    "mano_sinistra",
    "carezza_testa",
    "volto_ignoto",
    "volto_riconosciuto",
    "ostacolo_destra",
    "ostacolo_sinistra",
    "ostacolo_frontale",
    "rumore_improvviso",
    "camminando",
    "fermo"
]

PAROLE_INTERESSANTI = [
    "porta",
    "finestra",
    "bottiglia",
    "bicchiere",
    "telefono",
    "borsa",
    "zaino",
    "chiavi",
    "fischio",
    "voce",
    "grido",
    "caduta",
    "fuoco",
    "fumo",
    "acqua",
    "oggetto",
    "animale",
    "cane",
    "gatto",
    "persona",
    "sconosciuto",
    "laboratorio",
    "aperta",
    "chiusa",
    "aperto",
    "chiuso",
    "rosso",
    "verde",
    "blu",
    "grande",
    "piccolo",
    "libro",
    "sedia",     # solo se combinata con altro
    "tavolo",
    "schermo",
    "computer",
    "robot",
    "cibo",
    "tazza",
    "vicino",
    "davanti",
    "dietro",
    "accanto",
    "spostata",
    "spostato",
    "rotto",
    "rotta",
    "insolito",
    "insolita"
]

PAROLE_NEUTRE_DA_SOLE = [
    "tavolo",
    "sedia",
    "muro",
    "pavimento",
    "soffitto",
    "luce",
    "lampada",
    "stanza",
    "parete"
]

def _normalizza_testo(testo):
    testo = (testo or "").lower()

    marcatori = [
        "report:",
        "evento recente:",
        "interazione_utente",
        "prendi l'iniziativa",
        "prendi l iniziativa",
        "prendi liniziativa",
        "osservazione_autonoma",
        "osservazione autonoma",
        "vedo:",
        "sono fermo",
        "sto camminando"
    ]

    for m in marcatori:
        testo = testo.replace(m, " ")

    testo = re.sub(r"[^a-z0-9àèéìòù_ ]+", " ", testo)
    testo = re.sub(r"\s+", " ", testo).strip()
    return testo

def _slug(parole):
    parole_pulite = []

    for parola in parole:
        parola = parola.strip().lower()

        if not parola:
            continue

        parola = re.sub(r"[^a-z0-9àèéìòù_]+", "", parola)

        if len(parola) < 4:
            continue

        if parola in PAROLE_BANALI:
            continue

        if parola not in parole_pulite:
            parole_pulite.append(parola)

    if not parole_pulite:
        return None

    return "_".join(parole_pulite[:3])


def estrai_eventi_sconosciuti(mondo, eventi_noti=None):
    """
    Restituisce un dizionario di eventi candidati sconosciuti.

    Esempio:
    mondo = "REPORT: Vedo una bottiglia rossa sul tavolo. SONO FERMO."

    output:
    {
        "bottiglia_rossa_tavolo": True
    }
    """

    if eventi_noti is None:
        eventi_noti = {}

    testo = _normalizza_testo(mondo)

    if not testo:
        return {}

    parole = testo.split(" ")

    candidati = []

    for parola in parole:
        parola = parola.strip().lower()

        if len(parola) < 4:
            continue

        if parola in PAROLE_BANALI:
            continue

        candidati.append(parola)

    if not candidati:
        return {}
    
    nome_evento = _slug(candidati)

    if not nome_evento:
        return {}

    parole_evento = nome_evento.split("_")

    solo_neutre = all(
        parola in PAROLE_NEUTRE_DA_SOLE
        for parola in parole_evento
    )

    if solo_neutre:
        return {}

    # Evita eventi formati da una sola parola troppo generica.
    # Però consente concetti nuovi composti, anche se non presenti
    # in una lista manuale di oggetti.
    if len(parole_evento) < 2:
        return {}

    if nome_evento in PAROLE_NOTE:
        return {}

    if eventi_noti.get(nome_evento, False):
        return {}

    # Memoria di novità:
    # la prima volta osservo soltanto;
    # dalla soglia in poi l'evento diventa generabile.
    if registra_evento_sconosciuto is not None:
        stato = registra_evento_sconosciuto(nome_evento, mondo)

        if not stato.get("generabile", False):
            return {}

    return {
        nome_evento: True
    }


def arricchisci_eventi_con_sconosciuti(mondo, eventi_noti=None):
    """
    Unisce eventi già noti + eventi sconosciuti candidati.
    Non sovrascrive gli eventi noti.
    """

    if eventi_noti is None:
        eventi_noti = {}

    eventi_finali = {}

    for chiave, valore in eventi_noti.items():
        eventi_finali[chiave] = valore

    eventi_sconosciuti = estrai_eventi_sconosciuti(mondo, eventi_noti)

    for chiave, valore in eventi_sconosciuti.items():
        if chiave not in eventi_finali:
            eventi_finali[chiave] = valore

    return eventi_finali