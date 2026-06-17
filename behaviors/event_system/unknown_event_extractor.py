# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import re
import unicodedata
try:
    from behaviors.event_system.visual_semantic_interpreter import (
        interpreta_contenuto_visivo
    )
except Exception:
    interpreta_contenuto_visivo = None
try:
    from behaviors.event_system.unknown_situation_reasoner import (
        ragiona_situazione_sconosciuta
    )
except Exception:
    ragiona_situazione_sconosciuta = None

def _normalizza(testo):
    if not testo:
        return u""

    testo = testo.lower()
    testo = unicodedata.normalize("NFKD", testo)
    testo = u"".join(c for c in testo if not unicodedata.combining(c))
    testo = re.sub(r"[^a-z0-9àèéìòù\s_]", " ", testo)
    testo = re.sub(r"\s+", " ", testo).strip()
    return testo


def _contiene(testo, parole):
    return any(p in testo for p in parole)


def _solo_descrizione_generica(testo):
    """
    True quando il testo descrive solo aspetto/ambiente,
    senza implicazioni su movimento, sicurezza, accessibilità o anomalia.
    """

    parole_significative = [
        "chius", "blocc", "ostru", "impedis", "davanti",
        "vicino", "accanto", "rotto", "rotta", "dannegg",
        "crepa", "anomalo", "strano", "pericol", "rischio",
        "caduto", "fuori posto", "ingombr", "attraversare",
        "passare", "passaggio", "percorso", "accesso"
    ]

    if _contiene(testo, parole_significative):
        return False

    descrittori_generici = [
        "stanza", "ambiente", "ufficio", "pareti", "parete",
        "soffitto", "pavimento", "colore", "rosso", "rossa",
        "bianco", "bianca", "blu", "verde", "tavolo",
        "sedia", "scrivania", "finestra", "luce"
    ]

    count = 0
    for p in descrittori_generici:
        if p in testo:
            count += 1

    return count > 0


def _evento(nome, priorita, motivo):
    return {
        "nome": nome,
        "priorita": priorita,
        "motivo": motivo,
        "origine": "unknown_autonomo"
    }


def _evento_con_struttura(nome, priorita, motivo, struttura=None):
    evento = _evento(nome, priorita, motivo)
    if isinstance(struttura, dict):
        evento["evento_strutturato"] = struttura
    return evento


def estrai_eventi_sconosciuti(testo):
    """
    Estrae eventi unknown da situazioni comportamentalmente utili.

    Prima prova a interpretare semanticamente il contenuto osservato.
    Solo dopo usa il reasoner generico e le regole spaziali/safety.
    """

    testo = _normalizza(testo)

    if not testo:
        return []

    eventi = []

    # Oggetti vicino a zone di passaggio/accesso.
    # Esempio: zaino davanti alla porta.
    if (
        _contiene(testo, [
            "zaino", "borsa", "scatola", "sedia", "oggetto",
            "cartone", "pacco", "ostacolo", "ingombro"
        ])
        and
        _contiene(testo, [
            "davanti", "vicino", "accanto", "in mezzo", "sul"
        ])
        and
        _contiene(testo, [
            "porta", "accesso", "passaggio", "percorso",
            "corridoio", "entrata", "uscita", "varco"
        ])
    ):
        return [
            {
                "nome": "oggetto_in_zona_rilevante",
                "categoria": "sconosciuta",
                "descrizione": "oggetto vicino a una zona utile per movimento, accesso o esplorazione",
                "valore": True,
                "priorita": "media",
                "origine": "unknown_autonomo"
            }
        ]
    
    # 0. Regole semantiche specifiche ad alta priorita'.
    # Devono venire PRIMA dell'interprete visuale generico,
    # altrimenti una porta chiusa rischia di diventare

    if _contiene(testo, ["porta", "varco", "ingresso", "uscita"]):

        if _contiene(testo, ["davanti", "vicino", "accanto", "in mezzo", "sul"]):
            return [
                {
                    "nome": "oggetto_in_zona_rilevante",
                    "categoria": "sconosciuta",
                    "descrizione": "oggetto vicino a porta, accesso o passaggio potenzialmente rilevante",
                    "valore": True,
                    "priorita": "media",
                    "origine": "unknown_autonomo"
                }
            ]

        if _contiene(testo, ["chius", "serrata", "bloccata", "bloccato"]):
            return [
                {
                    "nome": "accesso_non_disponibile",
                    "categoria": "sconosciuta",
                    "descrizione": "accesso o passaggio potenzialmente non disponibile",
                    "valore": True,
                    "priorita": "alta",
                    "origine": "unknown_autonomo"
                }
            ]

        if _contiene(testo, ["apert", "spalancata", "socchiusa"]):
            return [
                {
                    "nome": "accesso_disponibile",
                    "categoria": "sconosciuta",
                    "descrizione": "accesso o passaggio potenzialmente disponibile",
                    "valore": True,
                    "priorita": "media",
                    "origine": "unknown_autonomo"
                }
            ]
        
    # Contenuto presente ma non ancora interpretabile:
    # non deve diventare memoria o informazione operativa.
    indicatori_non_leggibile = [
        "non leggibile",
        "illeggibile",
        "sfocato",
        "sfocata",
        "confuso",
        "confusa",
        "lontano",
        "lontana"
    ]

    if any(x in testo for x in indicatori_non_leggibile):
        return []

    # 1. Interprete semantico visuale:
    # deve venire PRIMA del filtro "descrizione generica",
    # altrimenti testi utili su oggetti/pareti/contenitori vengono ignorati.
    if interpreta_contenuto_visivo is not None:
        interpretazione = interpreta_contenuto_visivo(testo)

        if interpretazione.get("genera_condizione", False):
            nome_evento = interpretazione.get("evento")

            if nome_evento:
                eventi.append({
                    "nome": nome_evento,
                    "categoria": "sconosciuta",
                    "descrizione": interpretazione.get(
                        "significato",
                        "contenuto visivo semanticamente rilevante"
                    ),
                    "valore": True,
                    "interpretazione": interpretazione
                })

    if eventi:
        return eventi

    # 2. Ora posso scartare descrizioni davvero generiche.
    if _solo_descrizione_generica(testo):
        return []

    # 3. Reasoner generale: fallback.
    if ragiona_situazione_sconosciuta is not None:
        ragionamento = ragiona_situazione_sconosciuta(testo)

        if not ragionamento.get("genera_condizione", False):
            return []

        evento = ragionamento.get("evento")

        if evento:
            return [
                _evento_con_struttura(
                    evento,
                    "alta" if ragionamento.get("tipo") == "spaziale_safety" else "media",
                    ragionamento.get("ipotesi", "situazione sconosciuta significativa"),
                    ragionamento.get("evento_strutturato")
                )
            ]

    # 4. Regole simboliche residuali.
    if _contiene(testo, [
        "chius", "serrat", "blocc", "non aper",
        "non accessibile", "accesso impedito",
        "non posso passare", "non si puo passare"
    ]):
        eventi.append(_evento(
            "accesso_non_disponibile",
            "alta",
            "l'osservazione suggerisce che un accesso o passaggio potrebbe non essere disponibile"
        ))

    if _contiene(testo, [
        "passaggio ostruito", "percorso ostruito",
        "passaggio bloccato", "percorso bloccato",
        "davanti al passaggio", "davanti al percorso",
        "davanti alla porta",
        "sul passaggio", "sul percorso",
        "in mezzo al percorso", "in mezzo al passaggio",
        "ostacolo", "ingombro", "ingombrante"
    ]):
        eventi.append(_evento(
            "percorso_potenzialmente_ostruito",
            "alta",
            "l'osservazione suggerisce un possibile ostacolo sul percorso"
        ))

    if (
        _contiene(testo, ["vicino", "accanto", "davanti", "sul", "in mezzo"])
        and
        _contiene(testo, [
            "accesso", "passaggio", "percorso",
            "entrata", "uscita", "corridoio",
            "porta", "varco"
        ])
    ):
        eventi.append(_evento(
            "oggetto_in_zona_rilevante",
            "media",
            "un elemento osservato si trova vicino a una zona utile per movimento o esplorazione"
        ))

    if _contiene(testo, [
        "rotto", "rotta", "danneggiato", "danneggiata",
        "crepa", "crepato", "rovinato", "rovinata",
        "anomalo", "anomala", "strano", "strana"
    ]):
        eventi.append(_evento(
            "elemento_ambientale_anomalo",
            "media",
            "l'osservazione suggerisce un elemento danneggiato o anomalo"
        ))

    if _contiene(testo, [
        "fuori posto", "caduto", "caduta",
        "a terra", "spostato", "spostata"
    ]):
        eventi.append(_evento(
            "elemento_fuori_posto",
            "media",
            "un elemento sembra fuori dalla posizione normale e potrebbe richiedere attenzione"
        ))

    if _contiene(testo, [
        "zona sconosciuta", "area sconosciuta",
        "zona nuova", "area nuova",
        "mai vista", "non riconosco"
    ]):
        eventi.append(_evento(
            "zona_da_esplorare",
            "bassa",
            "l'ambiente contiene una zona nuova o non riconosciuta"
        ))

    if (
        _contiene(testo, [
            "contenitore", "scatola", "cartone", "cestino",
            "secchio", "area", "punto", "zona"
        ])
        and
        _contiene(testo, [
            "testo leggibile", "scritta", "indica",
            "istruzioni", "conferisci", "inserisci",
            "metti", "qui", "materiali", "fogli",
            "documenti", "oggetti"
        ])
    ):
        eventi.append({
            "nome": "informazione_operativa",
            "categoria": "sconosciuta",
            "descrizione": "contenitore o area con istruzioni leggibili potenzialmente utili",
            "valore": True
        })

    # Rimuove duplicati mantenendo ordine.
    visti = set()
    puliti = []

    for ev in eventi:
        nome = ev.get("nome")
        if nome not in visti:
            puliti.append(ev)
            visti.add(nome)

    return puliti
