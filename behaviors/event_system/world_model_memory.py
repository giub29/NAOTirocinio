# -*- coding: utf-8 -*-
from __future__ import unicode_literals

"""
World model persistente per NAO.

Trasforma osservazioni ripetute in credenze stabili sul contesto:
non decide al posto delle condizioni, ma mantiene uno stato del mondo
riutilizzabile da supervisore, generatore e memoria cognitiva.
"""

import os
import re
import json
import time
import codecs
import unicodedata
import logging

try:
    basestring
except NameError:
    basestring = str

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(__file__)
WORLD_MODEL_PATH = os.path.join(BASE_DIR, "world_model_memory.json")
LIMITE_EVIDENZE = 8


def _adesso():
    return time.strftime("%Y-%m-%d %H:%M:%S")


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


def _testo_breve(testo, limite=240):
    if isinstance(testo, basestring):
        testo = testo or ""
    else:
        testo = str(testo or "")

    testo = " ".join(testo.split())

    if len(testo) <= limite:
        return testo

    return testo[:limite].rstrip() + "..."


def _leggi_world_model():
    if not os.path.exists(WORLD_MODEL_PATH):
        return {
            "versione": 1,
            "aggiornata_il": "",
            "credenze": {}
        }

    try:
        with codecs.open(WORLD_MODEL_PATH, "r", "utf-8") as f:
            dati = json.load(f)
    except Exception as e:
        logger.warning(u"[WORLD_MODEL] Errore lettura memoria: {}".format(e))
        dati = {}

    if not isinstance(dati, dict):
        dati = {}

    if "credenze" not in dati or not isinstance(dati.get("credenze"), dict):
        dati["credenze"] = {}

    dati.setdefault("versione", 1)
    dati.setdefault("aggiornata_il", "")

    return dati


def _scrivi_world_model(dati):
    try:
        cartella = os.path.dirname(WORLD_MODEL_PATH)
        if not os.path.exists(cartella):
            os.makedirs(cartella)

        dati["aggiornata_il"] = _adesso()

        with codecs.open(WORLD_MODEL_PATH, "w", "utf-8") as f:
            json.dump(
                dati,
                f,
                ensure_ascii=False,
                indent=2,
                sort_keys=True
            )

        return True

    except Exception as e:
        logger.warning(u"[WORLD_MODEL] Errore scrittura memoria: {}".format(e))
        return False


def _eventi_attivi(firma):
    eventi = firma.get("eventi_attivi", {})
    if not isinstance(eventi, dict):
        return []

    return [
        str(nome).lower()
        for nome, valore in eventi.items()
        if valore not in [False, None, "", [], {}]
    ]


def _categoria_da_eventi(eventi, stato_semantico, testo=None):
    testo = testo or ""
    eventi_testo = " ".join(eventi)

    if any(x in testo for x in [
        "monitor", "schermo", "display", "computer",
        "terminale", "tablet", "telefono"
    ]):
        return "dispositivo"

    if "accesso" in eventi_testo or "percorso" in eventi_testo:
        return "accesso"

    if "informazione" in eventi_testo or "testuale" in eventi_testo:
        return "informazione"

    if "anomalo" in eventi_testo or "fuori_posto" in eventi_testo:
        return "anomalia"

    if "ostacolo" in eventi_testo or "zona" in eventi_testo:
        return "spazio"

    if stato_semantico in [
        "spento",
        "acceso",
        "attivo",
        "inattivo"
    ]:
        return "dispositivo"

    return "ambiente"


def _stato_da_osservazione(testo, eventi):
    eventi_set = set(eventi)

    if (
        "accesso_non_disponibile" in eventi_set
        or "accesso_o_percorso_limitato" in eventi_set
    ):
        return "non_disponibile"

    if "accesso_disponibile" in eventi_set:
        return "disponibile"

    if (
        "elemento_ambientale_anomalo" in eventi_set
        or "elemento_fuori_posto" in eventi_set
    ):
        return "anomalo"

    if "informazione_operativa" in eventi_set:
        return "informazione_operativa"

    if "contenuto_informativo_rilevante" in eventi_set:
        return "informazione_rilevante"

    if "contenuto_testuale_da_approfondire" in eventi_set:
        return "informazione_incerta"

    categorie_testuali = [
        ("non_disponibile", [
            "chius", "blocc", "ostru", "impedit",
            "non accessibile", "non posso passare"
        ]),
        ("disponibile", [
            "apert", "libero", "accessibile", "posso passare"
        ]),
        ("spento", [
            "spento", "schermo nero", "non attivo", "inattivo"
        ]),
        ("acceso", [
            "acceso", "attivo", "illuminato", "funzionante"
        ]),
        ("anomalo", [
            "rotto", "rotta", "danneggiato", "danneggiata",
            "anomalo", "anomala", "fuori posto", "caduto"
        ]),
        ("presente", [
            "presente", "comparso", "vedo", "rilevo", "vicino"
        ])
    ]

    for stato, indicatori in categorie_testuali:
        if any(indicatore in testo for indicatore in indicatori):
            return stato

    if eventi:
        return "osservato"

    return "descrizione_generica"


def _token_entita(testo, eventi, categoria):
    parole_vuote = [
        "report", "vedo", "sento", "rilevo", "sono", "fermo",
        "sto", "camminando", "una", "uno", "un", "la", "il",
        "lo", "le", "gli", "nel", "nella", "sul", "sulla",
        "con", "che", "qui", "ancora", "oggi", "spesso",
        "normalmente", "di", "a", "da", "in", "per", "del",
        "della", "dei", "delle", "qualcosa", "elemento",
        "non", "senza", "stesso", "stessa"
    ]

    parole_stato = [
        "chiusa", "chiuso", "aperta", "aperto", "bloccata",
        "bloccato", "ostruita", "ostruito", "spento", "spenta",
        "acceso", "accesa", "rotto", "rotta", "danneggiato",
        "danneggiata", "anomalo", "anomala", "presente",
        "comparso", "comparsa", "vicino", "davanti",
        "accessibile", "inaccessibile", "libero", "libera",
        "disponibile", "indisponibile", "testo", "leggibile",
        "visibile", "errore", "messaggio", "contenuto",
        "informazione", "informazioni"
    ]

    token = []

    for parola in testo.split():
        parola = parola.strip().lower()

        if len(parola) < 4:
            continue

        if parola in parole_vuote or parola in parole_stato:
            continue

        if parola not in token:
            token.append(parola)

    if token:
        return token[:4]

    token_eventi = []
    for evento in eventi:
        for pezzo in evento.replace("_", " ").split():
            if len(pezzo) >= 4 and pezzo not in token_eventi:
                token_eventi.append(pezzo)

    if token_eventi:
        return token_eventi[:4]

    return [categoria or "contesto"]


def _chiave_entita(categoria, token):
    return "{}::{}".format(
        categoria or "ambiente",
        "_".join(token[:4])
    )


def _stato_normale(conteggi, stato_normale_precedente):
    if not isinstance(conteggi, dict) or not conteggi:
        return stato_normale_precedente or ""

    stati = sorted(
        conteggi.items(),
        key=lambda item: item[1],
        reverse=True
    )

    stato_piu_frequente, conteggio = stati[0]

    if conteggio >= 2:
        return stato_piu_frequente

    return stato_normale_precedente or stato_piu_frequente


def _calcola_fiducia(conteggi, stato_corrente):
    totale = 0
    for valore in conteggi.values():
        try:
            totale += int(valore)
        except Exception:
            pass

    if totale <= 0:
        return 0.0

    corrente = int(conteggi.get(stato_corrente, 0))
    fiducia = float(corrente) / float(totale)

    if totale >= 4:
        fiducia = min(1.0, fiducia + 0.10)

    return round(fiducia, 3)


def _anomalia(record):
    stato_normale = record.get("stato_normale", "")
    stato_corrente = record.get("stato_corrente", "")

    if not stato_normale or not stato_corrente:
        return False

    if stato_normale == stato_corrente:
        return False

    if int(record.get("osservazioni_totali", 0)) < 3:
        return False

    conteggi = record.get("conteggi_stati", {})
    normale = int(conteggi.get(stato_normale, 0))
    corrente = int(conteggi.get(stato_corrente, 0))

    return normale >= 2 and corrente <= normale


def _ricalcola_record(record):
    conteggi = record.get("conteggi_stati", {})
    if not isinstance(conteggi, dict):
        conteggi = {}

    totale = 0
    for valore in conteggi.values():
        try:
            totale += int(valore)
        except Exception:
            pass

    record["osservazioni_totali"] = max(0, totale)

    stato_corrente = record.get("stato_corrente", "")
    if stato_corrente and int(conteggi.get(stato_corrente, 0)) <= 0:
        stati = sorted(
            conteggi.items(),
            key=lambda item: item[1],
            reverse=True
        )
        if stati and int(stati[0][1]) > 0:
            record["stato_corrente"] = stati[0][0]

    record["stato_normale"] = _stato_normale(
        conteggi,
        record.get("stato_normale", "")
    )
    record["fiducia"] = _calcola_fiducia(
        conteggi,
        record.get("stato_corrente", "")
    )
    record["anomalia"] = _anomalia(record)

    return record


def _costruisci_osservazione(mondo, firma):
    if firma is None:
        firma = {}

    testo = _normalizza(mondo)
    eventi = _eventi_attivi(firma)
    stato = _stato_da_osservazione(testo, eventi)
    categoria = _categoria_da_eventi(eventi, stato, testo)
    token = _token_entita(testo, eventi, categoria)
    chiave = _chiave_entita(categoria, token)

    return {
        "chiave": chiave,
        "entita": "_".join(token[:4]),
        "categoria": categoria,
        "stato": stato,
        "eventi": eventi,
        "testo": testo
    }


def aggiorna_world_model(mondo, firma=None, stato_runtime=None):
    """
    Aggiorna il belief state persistente e ritorna la credenza corrente.
    """

    if stato_runtime is None:
        stato_runtime = {}

    osservazione = _costruisci_osservazione(mondo, firma or {})

    if osservazione.get("stato") == "descrizione_generica":
        return {
            "aggiornato": False,
            "motivo": "osservazione troppo generica per il world model"
        }

    dati = _leggi_world_model()
    credenze = dati.get("credenze", {})
    chiave = osservazione.get("chiave")
    adesso = _adesso()

    record = credenze.get(chiave)
    if not isinstance(record, dict):
        record = {
            "entita": osservazione.get("entita"),
            "chiave": chiave,
            "categoria": osservazione.get("categoria"),
            "stato_corrente": "",
            "stato_normale": "",
            "fiducia": 0.0,
            "anomalia": False,
            "osservazioni_totali": 0,
            "conteggi_stati": {},
            "eventi_associati": [],
            "prima_osservazione": adesso,
            "ultima_osservazione": adesso,
            "evidenze_recenti": []
        }

    stato = osservazione.get("stato")
    conteggi = record.get("conteggi_stati", {})
    if not isinstance(conteggi, dict):
        conteggi = {}

    conteggi[stato] = int(conteggi.get(stato, 0)) + 1
    record["conteggi_stati"] = conteggi
    record["osservazioni_totali"] = int(record.get("osservazioni_totali", 0)) + 1
    record["stato_corrente"] = stato
    record["stato_normale"] = _stato_normale(
        conteggi,
        record.get("stato_normale", "")
    )
    record["fiducia"] = _calcola_fiducia(conteggi, stato)
    record["ultima_osservazione"] = adesso

    eventi_associati = record.get("eventi_associati", [])
    if not isinstance(eventi_associati, list):
        eventi_associati = []

    for evento in osservazione.get("eventi", []):
        if evento not in eventi_associati:
            eventi_associati.append(evento)
    record["eventi_associati"] = eventi_associati[-12:]

    evidenze = record.get("evidenze_recenti", [])
    if not isinstance(evidenze, list):
        evidenze = []

    evidenze.append({
        "tempo": adesso,
        "stato": stato,
        "mondo": _testo_breve(mondo)
    })
    record["evidenze_recenti"] = evidenze[-LIMITE_EVIDENZE:]
    record["anomalia"] = _anomalia(record)

    credenze[chiave] = record
    dati["credenze"] = credenze
    _scrivi_world_model(dati)

    esito = {
        "aggiornato": True,
        "chiave": chiave,
        "credenza": record,
        "anomalia": record.get("anomalia", False),
        "familiare": int(record.get("osservazioni_totali", 0)) >= 3,
        "novita": int(record.get("osservazioni_totali", 0)) == 1,
        "motivo": "credenza aggiornata dal mondo osservato"
    }

    stato_runtime["world_model"] = esito
    stato_runtime["belief_state"] = record

    return esito


def costruisci_decisione_world_model(esito):
    if not isinstance(esito, dict) or not esito.get("aggiornato"):
        return None

    credenza = esito.get("credenza", {})
    if not isinstance(credenza, dict):
        return None

    if esito.get("anomalia"):
        frase = (
            "Questa situazione non corrisponde a quello che ricordo "
            "come stato abituale. La considero con prudenza."
        )
        colore = "yellow"
        obiettivo = "valutare una variazione rispetto al modello del mondo"
    elif esito.get("familiare"):
        frase = (
            "Riconosco questa situazione come ricorrente. "
            "La tengo nel mio modello del mondo senza trattarla come novita'."
        )
        colore = "blue"
        obiettivo = "riconoscere uno stato abituale del mondo"
    else:
        return None

    return {
        "stato_interno": "riflessivo",
        "obiettivo": obiettivo,
        "azioni": [
            {
                "tipo": "occhi",
                "colore": colore
            },
            {
                "tipo": "parla",
                "testo": frase
            }
        ],
        "memoria": [
            {
                "tipo": "world_model",
                "entita": credenza.get("entita", ""),
                "stato_corrente": credenza.get("stato_corrente", ""),
                "stato_normale": credenza.get("stato_normale", ""),
                "fiducia": credenza.get("fiducia", 0.0),
                "anomalia": credenza.get("anomalia", False),
                "osservazioni_totali": credenza.get("osservazioni_totali", 0)
            }
        ]
    }


def recupera_credenze_rilevanti(mondo, firma=None, limite=5):
    osservazione = _costruisci_osservazione(mondo, firma or {})
    dati = _leggi_world_model()
    credenze = dati.get("credenze", {})
    token = set(osservazione.get("entita", "").split("_"))
    risultati = []

    for chiave, record in credenze.items():
        if not isinstance(record, dict):
            continue

        punteggio = 0

        if record.get("categoria") == osservazione.get("categoria"):
            punteggio += 3

        token_record = set(str(record.get("entita", "")).split("_"))
        overlap = token.intersection(token_record)

        if overlap:
            punteggio += len(overlap) * 2

        if punteggio <= 0:
            continue

        voce = dict(record)
        voce["punteggio_rilevanza"] = punteggio
        risultati.append(voce)

    risultati = sorted(
        risultati,
        key=lambda voce: voce.get("punteggio_rilevanza", 0),
        reverse=True
    )

    return risultati[:limite]


def _trova_chiave_record_da_esito(dati, esito, stato_runtime=None):
    credenze = dati.get("credenze", {})
    if not isinstance(credenze, dict):
        return None, None

    if stato_runtime is None:
        stato_runtime = {}

    esito_world = stato_runtime.get("world_model", {})
    if isinstance(esito_world, dict):
        chiave = esito_world.get("chiave")
        if chiave in credenze:
            return chiave, credenze.get(chiave)

    belief_state = stato_runtime.get("belief_state", {})
    if isinstance(belief_state, dict):
        chiave = belief_state.get("chiave")
        if chiave in credenze:
            return chiave, credenze.get(chiave)

    world_esito = esito.get("world_model", {})
    entita = ""
    if isinstance(world_esito, dict):
        entita = world_esito.get("entita", "")

    if not entita:
        entita = esito.get("target", "")

    entita_norm = str(entita).replace(" ", "_").lower()

    for chiave, record in credenze.items():
        if not isinstance(record, dict):
            continue

        record_entita = str(record.get("entita", "")).lower()
        if record_entita and (
            record_entita == entita_norm
            or record_entita in entita_norm
            or entita_norm in record_entita
        ):
            return chiave, record

    return None, None


def aggiorna_world_model_da_osservazione_mirata(
    esito,
    stato_runtime=None
):
    """
    Usa il feedback dell'active perception per correggere o confermare
    una credenza del world model.

    Se la ricerca trova segnali, la credenza/anomalia viene rinforzata.
    Se dopo piu' tentativi non trova segnali, si evita di consolidare come
    vera una variazione non confermata.
    """

    if stato_runtime is None:
        stato_runtime = {}

    if not isinstance(esito, dict):
        return None

    if esito.get("tipo") != "esito_osservazione_mirata":
        return None

    applicati = stato_runtime.get("_esiti_world_model_applicati", [])
    if not isinstance(applicati, list):
        applicati = []

    firma_esito = "{}::{}::{}".format(
        esito.get("aggiornata_il", ""),
        esito.get("target", ""),
        esito.get("tentativo", "")
    )

    if firma_esito in applicati:
        return stato_runtime.get("world_model")

    dati = _leggi_world_model()
    chiave, record = _trova_chiave_record_da_esito(
        dati,
        esito,
        stato_runtime=stato_runtime
    )

    if not chiave or not isinstance(record, dict):
        return None

    adesso = _adesso()
    trovato = bool(esito.get("trovato"))
    tentativo = int(esito.get("tentativo", 1))
    segnali_trovati = esito.get("segnali_trovati", [])
    segnali_mancanti = esito.get("segnali_mancanti", [])

    if not isinstance(segnali_trovati, list):
        segnali_trovati = []

    if not isinstance(segnali_mancanti, list):
        segnali_mancanti = []

    fiducia_delta = 0.0
    feedback = record.get("feedback_osservazione_mirata", [])
    if not isinstance(feedback, list):
        feedback = []

    feedback.append({
        "tempo": adesso,
        "target": esito.get("target", ""),
        "trovato": trovato,
        "tentativo": tentativo,
        "stato": esito.get("stato", ""),
        "segnali_trovati": segnali_trovati,
        "segnali_mancanti": segnali_mancanti
    })
    record["feedback_osservazione_mirata"] = feedback[-LIMITE_EVIDENZE:]

    if trovato:
        record["conferme_osservazione_mirata"] = int(
            record.get("conferme_osservazione_mirata", 0)
        ) + 1
        record["ultima_conferma_mirata"] = adesso

        if esito.get("cambiamento_confermato"):
            record["anomalia_confermata"] = True

        fiducia_delta = 0.08

    elif tentativo >= 2:
        record["smentite_osservazione_mirata"] = int(
            record.get("smentite_osservazione_mirata", 0)
        ) + 1
        record["ultima_smentita_mirata"] = adesso

        stato_corrente = record.get("stato_corrente", "")
        stato_normale = record.get("stato_normale", "")
        conteggi = record.get("conteggi_stati", {})
        if not isinstance(conteggi, dict):
            conteggi = {}

        variazione_non_confermata = (
            stato_corrente
            and stato_normale
            and stato_corrente != stato_normale
        )

        if record.get("anomalia") or variazione_non_confermata:
            conteggi[stato_corrente] = max(
                0,
                int(conteggi.get(stato_corrente, 0)) - 1
            )
            record["conteggi_stati"] = conteggi
            record["anomalia_confermata"] = False
            record["nota_feedback"] = (
                "variazione ridimensionata per osservazione mirata non confermata"
            )

        fiducia_delta = -0.10

    record["ultima_osservazione_mirata"] = adesso
    record = _ricalcola_record(record)

    if fiducia_delta:
        record["fiducia"] = round(
            min(
                1.0,
                max(0.0, float(record.get("fiducia", 0.0)) + fiducia_delta)
            ),
            3
        )

    if (
        record.get("anomalia_confermata")
        and record.get("stato_corrente")
        and record.get("stato_normale")
        and record.get("stato_corrente") != record.get("stato_normale")
    ):
        record["anomalia"] = True

    dati["credenze"][chiave] = record
    _scrivi_world_model(dati)

    esito_world = {
        "aggiornato": True,
        "chiave": chiave,
        "credenza": record,
        "anomalia": record.get("anomalia", False),
        "familiare": int(record.get("osservazioni_totali", 0)) >= 3,
        "novita": int(record.get("osservazioni_totali", 0)) == 1,
        "motivo": "credenza aggiornata da osservazione mirata"
    }

    stato_runtime["world_model"] = esito_world
    stato_runtime["belief_state"] = record

    applicati.append(firma_esito)
    stato_runtime["_esiti_world_model_applicati"] = applicati[-10:]

    return esito_world


def snapshot_world_model():
    return _leggi_world_model()


def reset_world_model():
    _scrivi_world_model({
        "versione": 1,
        "aggiornata_il": _adesso(),
        "credenze": {}
    })
