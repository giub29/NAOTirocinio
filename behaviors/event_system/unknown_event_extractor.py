# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import re
import unicodedata
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


def estrai_eventi_sconosciuti(testo):
    """
    Estrae eventi unknown da situazioni comportamentalmente utili.

    NON genera condizioni da semplici oggetti o colori.
    Genera eventi solo se il testo suggerisce:
    - accessibilità modificata
    - ostacolo o ingombro
    - danno/anomalia
    - relazione spaziale che può influenzare movimento/esplorazione
    """

    testo = _normalizza(testo)

    if not testo:
        return []

    if _solo_descrizione_generica(testo):
        return []
    
    # Ragionamento cognitivo generale:
    # decide se la scena è solo descrittiva,
    # curiosa ma non generativa,
    # oppure utile per una condizione autonoma.
    if ragiona_situazione_sconosciuta is not None:
        ragionamento = ragiona_situazione_sconosciuta(testo)

        if not ragionamento.get("genera_condizione", False):
            return []

        evento = ragionamento.get("evento")

        if evento:
            return [
                _evento(
                    evento,
                    "alta" if ragionamento.get("tipo") == "spaziale_safety" else "media",
                    ragionamento.get("ipotesi", "situazione sconosciuta significativa")
                )
            ]

    eventi = []

    # 1. Accessibilità: qualcosa non sembra attraversabile/usabile.
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

    # 2. Passaggio/percorso ostruito.
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

    # 3. Relazione spaziale rilevante:
    # qualcosa vicino/ad/accanto a zona di movimento/accesso.
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

    # 4. Danno o anomalia nell'ambiente.
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

    # 5. Oggetto fuori posto/caduto.
    if _contiene(testo, [
        "fuori posto", "caduto", "caduta",
        "a terra", "spostato", "spostata"
    ]):
        eventi.append(_evento(
            "elemento_fuori_posto",
            "media",
            "un elemento sembra fuori dalla posizione normale e potrebbe richiedere attenzione"
        ))

    # 6. Zona nuova/esplorabile.
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

    # 7. Contenitore con istruzioni visibili.
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
            "nome": "contenitore_con_istruzioni_visibili",
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