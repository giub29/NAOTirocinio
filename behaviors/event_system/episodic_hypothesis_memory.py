# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import re
import time
import unicodedata

try:
    from behaviors.event_system.unknown_situation_reasoner import (
        ragiona_situazione_sconosciuta
    )
except Exception:
    ragiona_situazione_sconosciuta = None


MEMORIA_IPOTESI = {}
TTL_IPOTESI = 120


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


def _token_contesto(testo):
    testo = _normalizza(testo)
    parole_vuote = [
        "report", "vedo", "sento", "rilevo", "una", "uno", "un",
        "la", "il", "lo", "le", "gli", "nel", "nella", "sul",
        "sulla", "con", "che", "qui", "sono", "sto", "ancora",
        "stesso", "stessa", "senza", "testo", "leggibile",
        "visibile", "spento", "spenta", "acceso", "accesa",
        "contenuto", "informazione", "errore", "fermo",
        "camminando"
    ]

    token = []

    for parola in testo.split():
        if len(parola) < 4:
            continue

        if parola in parole_vuote:
            continue

        if parola not in token:
            token.append(parola)

    return token[:6]


def _eventi_attivi(firma):
    eventi = firma.get("eventi_attivi", {})

    if not isinstance(eventi, dict):
        return []

    return [
        str(nome).lower()
        for nome, valore in eventi.items()
        if valore not in [False, None, "", [], {}]
    ]


def _classifica_ipotesi(mondo, firma):
    eventi = set(_eventi_attivi(firma))

    ragionamento = {}
    if ragiona_situazione_sconosciuta is not None:
        try:
            ragionamento = ragiona_situazione_sconosciuta(mondo)
        except Exception:
            ragionamento = {}

    tipo = str(ragionamento.get("tipo", "")).lower()
    evento_ragionato = str(ragionamento.get("evento", "")).lower()

    if (
        "elemento_ambientale_anomalo" in eventi
        or evento_ragionato == "elemento_ambientale_anomalo"
        or tipo == "anomalia"
    ):
        return {
            "ipotesi": "elemento_ambientale_anomalo",
            "descrizione": "un elemento dell'ambiente sembra anomalo o danneggiato",
            "fiducia_iniziale": 0.75,
            "incremento_conferma": 0.20,
            "azione_temporanea": "osserva_con_prudenza",
            "conferme_minime": 1,
            "generabile": True,
            "rilevanza": "alta"
        }

    if (
        "accesso_non_disponibile" in eventi
        or "accesso_o_percorso_limitato" in eventi
        or evento_ragionato in [
            "accesso_non_disponibile",
            "accesso_o_percorso_limitato"
        ]
    ):
        return {
            "ipotesi": "accesso_non_disponibile",
            "descrizione": "forse questo accesso non e' disponibile",
            "fiducia_iniziale": 0.35,
            "incremento_conferma": 0.25,
            "azione_temporanea": "osserva_con_prudenza",
            "conferme_minime": 3,
            "generabile": True,
            "rilevanza": "media"
        }

    if (
        "informazione_operativa" in eventi
        or "contenuto_informativo_rilevante" in eventi
        or evento_ragionato in [
            "informazione_operativa",
            "contenuto_informativo_rilevante"
        ]
    ):
        return {
            "ipotesi": "informazione_operativa",
            "descrizione": "il contenuto osservato potrebbe essere utile",
            "fiducia_iniziale": 0.55,
            "incremento_conferma": 0.25,
            "azione_temporanea": "interpreta_e_memorizza",
            "conferme_minime": 2,
            "generabile": True,
            "rilevanza": "media"
        }

    if tipo in [
        "informazione_visiva_incerta",
        "supporto_informativo_potenziale",
        "ambiguita_visiva"
    ]:
        return {
            "ipotesi": "contenuto_informativo_incerto",
            "descrizione": "potrebbe esserci informazione utile non leggibile",
            "fiducia_iniziale": 0.30,
            "incremento_conferma": 0.10,
            "azione_temporanea": "osserva_meglio",
            "conferme_minime": 999,
            "generabile": False,
            "rilevanza": "bassa"
        }

    return None


def _chiave_ipotesi(mondo, ipotesi):
    token = _token_contesto(mondo)

    if not token:
        token = ["contesto_generico"]

    return "{}::{}".format(
        ipotesi.get("ipotesi", "sconosciuta"),
        "_".join(token[:4])
    )


def _pulisci_scadute(adesso):
    for chiave in list(MEMORIA_IPOTESI.keys()):
        ultima = MEMORIA_IPOTESI[chiave].get("ultima_osservazione", 0)

        if adesso - ultima > TTL_IPOTESI:
            del MEMORIA_IPOTESI[chiave]


def _registra_smentite(ipotesi_corrente, adesso, mondo):
    nome = ipotesi_corrente.get("ipotesi")

    opposti = {
        "accesso_non_disponibile": ["accesso_disponibile"],
        "contenuto_informativo_incerto": [
            "informazione_operativa",
            "contenuto_informativo_rilevante"
        ]
    }

    for chiave, record in MEMORIA_IPOTESI.items():
        nome_record = record.get("ipotesi")

        if nome_record == nome:
            continue

        if record.get("risolta_da_osservazione_mirata"):
            continue

        if nome in opposti.get(nome_record, []):
            record["smentite"] = int(record.get("smentite", 0)) + 1
            record["fiducia"] = max(0.0, float(record.get("fiducia", 0.0)) - 0.30)
            record["ultima_osservazione"] = adesso

            esempi_smentite = record.get("esempi_smentite", [])
            if mondo and mondo not in esempi_smentite:
                esempi_smentite.append(mondo)
            record["esempi_smentite"] = esempi_smentite[-3:]


def valuta_ipotesi_temporanee(mondo, firma, stato_runtime=None):
    """
    Aggiorna una memoria episodica non permanente di ipotesi cognitive.

    Ritorna una decisione leggera:
    - genera_condizione False: osserva ancora o ignora;
    - genera_condizione True: l'ipotesi e' abbastanza confermata.
    """

    if stato_runtime is None:
        stato_runtime = {}

    adesso = time.time()
    _pulisci_scadute(adesso)

    ipotesi = _classifica_ipotesi(mondo, firma)

    if ipotesi is None:
        return {
            "ha_ipotesi": False,
            "genera_condizione": False,
            "motivo": "nessuna ipotesi temporanea utile"
        }

    _registra_smentite(ipotesi, adesso, mondo)

    chiave = _chiave_ipotesi(mondo, ipotesi)
    record = MEMORIA_IPOTESI.get(chiave)

    if record is None:
        record = {
            "ipotesi": ipotesi.get("ipotesi"),
            "descrizione": ipotesi.get("descrizione"),
            "fiducia": ipotesi.get("fiducia_iniziale", 0.30),
            "conferme": 0,
            "smentite": 0,
            "prima_osservazione": adesso,
            "ultima_osservazione": adesso,
            "azione_temporanea": ipotesi.get("azione_temporanea"),
            "rilevanza": ipotesi.get("rilevanza", "media"),
            "diventa_condizione_se": {
                "conferme_minime": ipotesi.get("conferme_minime", 2)
            },
            "esempi": [],
            "esempi_smentite": []
        }

    record["conferme"] = int(record.get("conferme", 0)) + 1
    record["ultima_osservazione"] = adesso
    record["fiducia"] = min(
        1.0,
        float(record.get("fiducia", 0.0)) + ipotesi.get("incremento_conferma", 0.20)
    )

    esempi = record.get("esempi", [])
    if mondo and mondo not in esempi:
        esempi.append(mondo)
    record["esempi"] = esempi[-3:]

    MEMORIA_IPOTESI[chiave] = record
    stato_runtime["ipotesi_temporanea"] = record

    conferme_minime = int(
        record.get("diventa_condizione_se", {}).get("conferme_minime", 2)
    )

    if not ipotesi.get("generabile", False):
        if record["conferme"] >= 2:
            return {
                "ha_ipotesi": True,
                "genera_condizione": False,
                "ignora_osservazione": True,
                "motivo": "ipotesi rimasta incerta dopo osservazioni ripetute",
                "ipotesi": record
            }

        return {
            "ha_ipotesi": True,
            "genera_condizione": False,
            "motivo": "ipotesi informativa ancora incerta",
            "azione_temporanea": record.get("azione_temporanea"),
            "ipotesi": record
        }

    if record["conferme"] >= conferme_minime:
        return {
            "ha_ipotesi": True,
            "genera_condizione": True,
            "motivo": "ipotesi confermata piu volte",
            "ipotesi": record
        }

    return {
        "ha_ipotesi": True,
        "genera_condizione": False,
        "motivo": "ipotesi ancora debole",
        "azione_temporanea": record.get("azione_temporanea"),
        "ipotesi": record
    }


def costruisci_decisione_ipotesi(esito):
    if not isinstance(esito, dict):
        return None

    ipotesi = esito.get("ipotesi", {})
    azione = esito.get("azione_temporanea") or ipotesi.get("azione_temporanea")

    if esito.get("genera_condizione", False):
        return None

    if not azione:
        return None

    colore = "yellow"
    frase = "Ho formulato un'ipotesi, ma la osservo ancora prima di renderla stabile."

    if azione == "osserva_con_prudenza":
        colore = "yellow"
        frase = "Ho un'ipotesi prudente sulla situazione. La verifico prima di memorizzarla."
    elif azione == "interpreta_e_memorizza":
        colore = "blue"
        frase = "Ho notato un'informazione potenzialmente utile. La tengo in memoria temporanea."
    elif azione == "osserva_meglio":
        colore = "yellow"
        frase = "Non ho abbastanza evidenza. Osservo meglio prima di creare una condizione."

    return {
        "stato_interno": "riflessivo",
        "obiettivo": "verificare una ipotesi temporanea",
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
                "tipo": "ipotesi_temporanea",
                "ipotesi": ipotesi.get("ipotesi"),
                "fiducia": ipotesi.get("fiducia"),
                "conferme": ipotesi.get("conferme"),
                "smentite": ipotesi.get("smentite"),
                "motivo": esito.get("motivo")
            }
        ]
    }


def _firma_esito_osservazione(esito):
    return "{}::{}::{}".format(
        esito.get("aggiornata_il", ""),
        esito.get("target", ""),
        esito.get("tentativo", "")
    )


def _trova_record_runtime(stato_runtime):
    if not isinstance(stato_runtime, dict):
        return None, None

    ipotesi_runtime = stato_runtime.get("ipotesi_temporanea", {})
    if not isinstance(ipotesi_runtime, dict):
        return None, None

    for chiave, record in MEMORIA_IPOTESI.items():
        if record is ipotesi_runtime:
            return chiave, record

    nome = ipotesi_runtime.get("ipotesi")
    prima = ipotesi_runtime.get("prima_osservazione")

    for chiave, record in MEMORIA_IPOTESI.items():
        if (
            record.get("ipotesi") == nome
            and record.get("prima_osservazione") == prima
        ):
            return chiave, record

    return None, ipotesi_runtime


def aggiorna_ipotesi_da_osservazione_mirata(esito, stato_runtime=None):
    """
    Usa l'esito di una osservazione mirata per confermare o indebolire
    l'ipotesi temporanea corrente.

    - segnali trovati: aumenta fiducia e conferme;
    - niente segnali dopo piu' tentativi: registra smentita e abbassa fiducia.
    """

    if stato_runtime is None:
        stato_runtime = {}

    if not isinstance(esito, dict):
        return None

    if esito.get("tipo") != "esito_osservazione_mirata":
        return None

    applicati = stato_runtime.get("_esiti_osservazione_mirata_applicati", [])
    if not isinstance(applicati, list):
        applicati = []

    firma_esito = _firma_esito_osservazione(esito)
    if firma_esito in applicati:
        return stato_runtime.get("ipotesi_temporanea")

    chiave, record = _trova_record_runtime(stato_runtime)
    if not isinstance(record, dict):
        return None

    adesso = time.time()
    record["ultima_osservazione"] = adesso

    trovato = bool(esito.get("trovato"))
    tentativo = int(esito.get("tentativo", 1))
    mondo = esito.get("mondo", "")
    segnali_trovati = esito.get("segnali_trovati", [])
    segnali_mancanti = esito.get("segnali_mancanti", [])

    if not isinstance(segnali_trovati, list):
        segnali_trovati = []

    if not isinstance(segnali_mancanti, list):
        segnali_mancanti = []

    if trovato:
        incremento = 0.18
        if esito.get("cambiamento_confermato"):
            incremento = 0.25

        record["conferme"] = int(record.get("conferme", 0)) + 1
        record["fiducia"] = min(
            1.0,
            float(record.get("fiducia", 0.0)) + incremento
        )

        esempi = record.get("esempi", [])
        if mondo and mondo not in esempi:
            esempi.append(mondo)
        record["esempi"] = esempi[-3:]
        record["risolta_da_osservazione_mirata"] = True
        record["ultimo_esito_osservazione"] = "confermata"

    elif tentativo >= 2:
        decremento = 0.30
        if tentativo >= 3:
            decremento = 0.45

        record["smentite"] = int(record.get("smentite", 0)) + 1
        record["fiducia"] = max(
            0.0,
            float(record.get("fiducia", 0.0)) - decremento
        )

        esempi_smentite = record.get("esempi_smentite", [])
        if mondo and mondo not in esempi_smentite:
            esempi_smentite.append(mondo)
        record["esempi_smentite"] = esempi_smentite[-3:]
        record["ultimo_esito_osservazione"] = "smentita"

    tracce = record.get("osservazioni_mirate", [])
    if not isinstance(tracce, list):
        tracce = []

    tracce.append({
        "tempo": esito.get("aggiornata_il", ""),
        "target": esito.get("target", ""),
        "trovato": trovato,
        "tentativo": tentativo,
        "segnali_trovati": segnali_trovati,
        "segnali_mancanti": segnali_mancanti,
        "stato": esito.get("stato", "")
    })
    record["osservazioni_mirate"] = tracce[-5:]

    if chiave:
        MEMORIA_IPOTESI[chiave] = record

    stato_runtime["ipotesi_temporanea"] = record
    stato_runtime.pop("_esito_ipotesi_temporanea", None)

    applicati.append(firma_esito)
    stato_runtime["_esiti_osservazione_mirata_applicati"] = applicati[-10:]

    return record


def snapshot_ipotesi():
    return dict(MEMORIA_IPOTESI)


def reset_ipotesi_temporanee():
    MEMORIA_IPOTESI.clear()
