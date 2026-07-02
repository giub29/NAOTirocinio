# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
import json
import time
import re

try:
    basestring
except NameError:
    basestring = str


BASE_DIR = "/data/home/nao/NAOTirocinio"
DATA_DIR = "/data/home/nao/.nao_knowledge_memory"
MEMORY_PATH = os.path.join(DATA_DIR, "knowledge_memory.json")
CAMPI_SEMANTICI = [
    "affordance",
    "funzione_probabile",
    "utilita_contestuale",
    "conseguenze_possibili"
]
EVENTI_SEMANTICI = [
    "contenuto_informativo_rilevante",
    "informazione_operativa",
    "supporto_informativo_potenziale",
    "dettaglio_funzionale_osservabile"
]
SOGLIA_CONOSCENZA_STABILE = 0.70


def _testo(valore):
    try:
        if isinstance(valore, basestring):
            return valore.lower().strip()
        return str(valore or "").lower().strip()
    except Exception:
        return ""


def _normalizza(testo):
    testo = _testo(testo)
    testo = re.sub(r"[^a-z0-9àèéìòù\s_]", " ", testo)
    testo = re.sub(r"\s+", " ", testo).strip()
    return testo


def _carica_memoria():
    if not os.path.exists(DATA_DIR):
        try:
            os.makedirs(DATA_DIR)
        except Exception:
            pass

    if not os.path.exists(MEMORY_PATH):
        return {"ipotesi": []}

    try:
        with open(MEMORY_PATH, "r") as f:
            dati = json.load(f)
        if not isinstance(dati, dict):
            return {"ipotesi": []}
        if "ipotesi" not in dati or not isinstance(dati["ipotesi"], list):
            dati["ipotesi"] = []
        return dati
    except Exception:
        return {"ipotesi": []}


def _salva_memoria(dati):
    if not os.path.exists(DATA_DIR):
        try:
            os.makedirs(DATA_DIR)
        except Exception:
            pass

    try:
        with open(MEMORY_PATH, "w") as f:
            json.dump(dati, f, indent=2, sort_keys=True)
        return True
    except Exception:
        return False


def _firma(concetto, evidenze):
    parole = [_normalizza(concetto)]

    if isinstance(evidenze, list):
        for e in evidenze:
            t = _normalizza(e)
            if t and t not in parole:
                parole.append(t)

    return "|".join(parole[:8])


def _lista_norm(valore):
    if not isinstance(valore, list):
        return []

    risultato = []
    for elemento in valore:
        testo = _normalizza(elemento)
        if testo and testo not in risultato:
            risultato.append(testo)
    return risultato


def _unisci_lista(lista_base, lista_nuova):
    risultato = []
    if isinstance(lista_base, list):
        for elemento in lista_base:
            if elemento not in risultato:
                risultato.append(elemento)

    if isinstance(lista_nuova, list):
        for elemento in lista_nuova:
            if elemento not in risultato:
                risultato.append(elemento)

    return risultato


def _sovrapposizione(lista_a, lista_b):
    norm_a = _lista_norm(lista_a)
    norm_b = _lista_norm(lista_b)

    return [
        elemento for elemento in norm_a
        if elemento in norm_b
    ]


def _campi_semantici_simili(voce, ipotesi):
    punteggio = 0

    for campo in ["funzione_probabile", "utilita_contestuale"]:
        if (
            _normalizza(voce.get(campo, ""))
            and _normalizza(voce.get(campo, "")) == _normalizza(
                ipotesi.get(campo, "")
            )
        ):
            punteggio += 1

    for campo in ["affordance", "conseguenze_possibili"]:
        if _sovrapposizione(voce.get(campo, []), ipotesi.get(campo, [])):
            punteggio += 1

    return punteggio


def _ipotesi_simile(voce, ipotesi):
    if _testo(voce.get("concetto")) != _testo(ipotesi.get("concetto")):
        return False

    if _sovrapposizione(voce.get("evidenze", []), ipotesi.get("evidenze", [])):
        return True

    return _campi_semantici_simili(voce, ipotesi) >= 2


def _conflitto_reale(voce, ipotesi):
    if _testo(voce.get("concetto")) != _testo(ipotesi.get("concetto")):
        return False

    vecchie = _lista_norm(voce.get("evidenze", []))
    nuove = _lista_norm(ipotesi.get("evidenze", []))

    if not vecchie or not nuove:
        return False

    return (
        not _sovrapposizione(vecchie, nuove)
        and _campi_semantici_simili(voce, ipotesi) == 0
    )


def _aggiorna_stabilita(voce):
    try:
        fiducia = float(voce.get("fiducia", 0.0))
    except Exception:
        fiducia = 0.0

    conferme = int(voce.get("conferme", 0) or 0)
    smentite = int(voce.get("smentite", 0) or 0)

    voce["conoscenza_stabile"] = (
        fiducia >= SOGLIA_CONOSCENZA_STABILE
        and conferme >= 2
        and smentite == 0
    )

    return voce["conoscenza_stabile"]


def _costruisci_voce_salvata(ipotesi, mondo=None):
    concetto = _testo(ipotesi.get("concetto"))
    evidenze = ipotesi.get("evidenze", [])
    if not isinstance(evidenze, list):
        evidenze = []

    voce = {
        "firma": _firma(concetto, evidenze),
        "concetto": concetto,
        "ipotesi": ipotesi.get("ipotesi", ""),
        "evidenze": evidenze,
        "fiducia": float(ipotesi.get("fiducia", 0.3)),
        "conferme": 0,
        "smentite": 0,
        "osservazioni": 1,
        "origine": ipotesi.get("origine", "osservazione"),
        "mondo_esempio": mondo or "",
        "conoscenza_stabile": bool(ipotesi.get("conoscenza_stabile", False)),
        "creata": time.time(),
        "ultimo_aggiornamento": time.time()
    }

    for campo in CAMPI_SEMANTICI:
        if campo in ipotesi:
            voce[campo] = ipotesi.get(campo)

    _aggiorna_stabilita(voce)
    return voce


def estrai_evidenze_da_testo(testo):
    testo = _normalizza(testo)

    evidenze = []
    parole_utili = [
        "aperto", "chiuso", "orario", "venerdi", "venerdì",
        "weekly", "bar", "caffe", "caffè", "laboratorio",
        "accesso", "uscita", "entrata", "vietato", "attenzione",
        "istruzioni", "premere", "usare", "errore", "warning"
    ]

    for parola in parole_utili:
        if parola in testo and parola not in evidenze:
            evidenze.append(parola)

    return evidenze


SCHEMI_IPOTESI_GENERALISTE = [
    {
        "concetto": "fonte_informativa",
        "segnali": [
            "testo", "leggibile", "ocr", "informazione", "avviso",
            "messaggio", "scritto", "parole", "contenuto", "comunica"
        ],
        "ipotesi": (
            "la scena potrebbe offrire informazioni utili per "
            "comprendere il contesto"
        ),
        "affordance": [
            "leggere il contenuto",
            "memorizzare il significato",
            "usare l'informazione nel ragionamento"
        ],
        "funzione_probabile": "trasmettere informazioni contestuali",
        "utilita_contestuale": "aumenta la comprensione della situazione",
        "conseguenze_possibili": [
            "migliore interpretazione del luogo",
            "decisioni piu' coerenti con il contesto"
        ]
    },
    {
        "concetto": "riferimento_temporale",
        "segnali": [
            "orario", "ora", "aperto", "chiuso", "oggi", "domani",
            "lunedi", "martedi", "mercoledi", "giovedi", "venerdi",
            "sabato", "domenica", "scadenza", "appuntamento"
        ],
        "ipotesi": (
            "la scena potrebbe contenere un riferimento temporale "
            "rilevante"
        ),
        "affordance": [
            "stimare disponibilita' nel tempo",
            "collegare l'azione al momento corretto"
        ],
        "funzione_probabile": "organizzare accesso o comportamento nel tempo",
        "utilita_contestuale": "aiuta a decidere quando agire o attendere",
        "conseguenze_possibili": [
            "evitare azioni fuori tempo",
            "riconoscere finestre di disponibilita'"
        ]
    },
    {
        "concetto": "supporto_informativo",
        "segnali": [
            "supporto", "visibile", "simbolo", "segnale", "indicazione",
            "etichetta", "istruzioni", "leggibile", "scritto"
        ],
        "ipotesi": (
            "potrebbe esserci un supporto dedicato a rendere "
            "informazioni osservabili"
        ),
        "affordance": [
            "osservare meglio",
            "cercare contenuto leggibile",
            "associare forma e funzione"
        ],
        "funzione_probabile": "rendere disponibili informazioni nell'ambiente",
        "utilita_contestuale": "orienta ulteriori osservazioni mirate",
        "conseguenze_possibili": [
            "scoprire istruzioni o vincoli",
            "ridurre incertezza sul contesto"
        ]
    },
    {
        "concetto": "contesto_sociale_o_organizzativo",
        "segnali": [
            "persone", "utente", "pubblico", "personale", "staff",
            "riunione", "gruppo", "prenotazione", "turno", "ufficio",
            "accoglienza"
        ],
        "ipotesi": (
            "la scena potrebbe appartenere a un contesto sociale "
            "o organizzativo"
        ),
        "affordance": [
            "adattare tono e distanza",
            "riconoscere ruoli possibili",
            "evitare interruzioni inappropriate"
        ],
        "funzione_probabile": "coordinare persone, ruoli o servizi",
        "utilita_contestuale": "aiuta a scegliere un comportamento sociale adatto",
        "conseguenze_possibili": [
            "interazione piu' prudente",
            "migliore rispetto del contesto"
        ]
    },
    {
        "concetto": "indicazione_operativa",
        "segnali": [
            "premere", "usare", "seguire", "andare", "entrare",
            "uscire", "attendere", "chiamare", "registrarsi",
            "conferisci", "inserire", "ritirare"
        ],
        "ipotesi": (
            "la scena potrebbe suggerire una procedura o un'azione "
            "da compiere"
        ),
        "affordance": [
            "seguire una procedura",
            "chiedere conferma prima di agire",
            "usare l'indicazione per pianificare"
        ],
        "funzione_probabile": "guidare un comportamento operativo",
        "utilita_contestuale": "trasforma osservazioni in possibili azioni",
        "conseguenze_possibili": [
            "azione piu' mirata",
            "minore ambiguita' decisionale"
        ]
    },
    {
        "concetto": "vincolo_o_regola",
        "segnali": [
            "vietato", "obbligatorio", "riservato", "solo", "non",
            "divieto", "permesso", "accesso", "limite", "regola",
            "autorizzato"
        ],
        "ipotesi": (
            "la scena potrebbe esprimere un vincolo o una regola "
            "di comportamento"
        ),
        "affordance": [
            "evitare azioni non consentite",
            "chiedere autorizzazione",
            "rispettare il vincolo"
        ],
        "funzione_probabile": "limitare o regolare comportamenti possibili",
        "utilita_contestuale": "riduce il rischio di azioni inappropriate",
        "conseguenze_possibili": [
            "maggiore sicurezza comportamentale",
            "necessita' di conferma prima dell'azione"
        ]
    },
    {
        "concetto": "opportunita_di_orientamento",
        "segnali": [
            "direzione", "percorso", "freccia", "uscita", "entrata",
            "ingresso", "piano", "zona", "area", "qui", "verso"
        ],
        "ipotesi": (
            "la scena potrebbe aiutare l'orientamento nello spazio"
        ),
        "affordance": [
            "aggiornare la mappa mentale",
            "scegliere una direzione",
            "disambiguare un percorso"
        ],
        "funzione_probabile": "fornire riferimenti spaziali",
        "utilita_contestuale": "migliora navigazione e localizzazione",
        "conseguenze_possibili": [
            "spostamento piu' informato",
            "minore disorientamento"
        ]
    },
    {
        "concetto": "possibile_rischio",
        "segnali": [
            "attenzione", "pericolo", "warning", "errore", "emergenza",
            "rischio", "bagnato", "caduta", "ostacolo", "allarme",
            "fragile"
        ],
        "ipotesi": (
            "la scena potrebbe segnalare un rischio o una condizione "
            "che richiede prudenza"
        ),
        "affordance": [
            "rallentare",
            "mantenere distanza",
            "richiedere verifica prima di procedere"
        ],
        "funzione_probabile": "avvertire di una possibile criticita'",
        "utilita_contestuale": "aumenta prudenza e sicurezza",
        "conseguenze_possibili": [
            "evitare manovre rischiose",
            "priorita' a osservazione o richiesta di aiuto"
        ]
    },
    {
        "concetto": "contesto_commerciale_o_servizio",
        "segnali": [
            "servizio", "prezzo", "pagamento", "prenotazione",
            "offerta", "vendita", "acquisto", "disponibile",
            "cliente", "apertura", "chiusura"
        ],
        "ipotesi": (
            "la scena potrebbe appartenere a un contesto di servizio "
            "o scambio"
        ),
        "affordance": [
            "riconoscere disponibilita' di un servizio",
            "chiedere informazioni",
            "rispettare procedure di accesso"
        ],
        "funzione_probabile": "gestire disponibilita', accesso o scambio",
        "utilita_contestuale": "aiuta a interpretare scopo e modalita' del luogo",
        "conseguenze_possibili": [
            "interazione orientata al servizio",
            "attenzione a costi, tempi o disponibilita'"
        ]
    }
]


def _segnali_presenti(testo, segnali):
    presenti = []
    for segnale in segnali:
        segnale_norm = _normalizza(segnale)
        if segnale_norm and segnale_norm in testo and segnale_norm not in presenti:
            presenti.append(segnale_norm)
    return presenti


def _fiducia_da_evidenze(evidenze, evento):
    base = 0.30
    if evento in ["contenuto_informativo_rilevante", "informazione_operativa"]:
        base = 0.35
    elif evento in [
        "supporto_informativo_potenziale",
        "dettaglio_funzionale_osservabile"
    ]:
        base = 0.28

    incremento = min(0.20, 0.04 * len(evidenze))
    return min(0.65, base + incremento)


def costruisci_ipotesi_multiple_da_evento(evento, mondo):
    evento = _testo(evento)
    testo = _normalizza(mondo)
    ipotesi = []

    if not testo and not evento:
        return ipotesi

    if evento not in EVENTI_SEMANTICI:
        return ipotesi

    for schema in SCHEMI_IPOTESI_GENERALISTE:
        evidenze = _segnali_presenti(testo, schema.get("segnali", []))

        if not evidenze:
            continue

        ipotesi.append({
            "concetto": schema.get("concetto", ""),
            "ipotesi": schema.get("ipotesi", ""),
            "evidenze": evidenze,
            "affordance": list(schema.get("affordance", [])),
            "funzione_probabile": schema.get("funzione_probabile", ""),
            "utilita_contestuale": schema.get("utilita_contestuale", ""),
            "conseguenze_possibili": list(
                schema.get("conseguenze_possibili", [])
            ),
            "fiducia": _fiducia_da_evidenze(evidenze, evento),
            "origine": evento
        })

    if not ipotesi and evento == "supporto_informativo_potenziale":
        ipotesi.append({
            "concetto": "supporto_informativo",
            "ipotesi": (
                "potrebbe esistere un supporto informativo, ma il "
                "contenuto non e' ancora abbastanza chiaro"
            ),
            "evidenze": estrai_evidenze_da_testo(testo),
            "affordance": [
                "osservare meglio",
                "cercare contenuto leggibile"
            ],
            "funzione_probabile": "rendere disponibili informazioni",
            "utilita_contestuale": "guida ulteriori osservazioni",
            "conseguenze_possibili": [
                "possibile scoperta di informazioni utili"
            ],
            "fiducia": 0.25,
            "origine": evento
        })

    return ipotesi


def costruisci_ipotesi_da_evento(evento, mondo):
    evento = _testo(evento)
    testo = _normalizza(mondo)
    evidenze = estrai_evidenze_da_testo(testo)

    if evento in ["contenuto_informativo_rilevante", "informazione_operativa"]:
        return {
            "concetto": "fonte_informativa",
            "ipotesi": (
                "la scena potrebbe contenere informazioni utili "
                "per comprendere il contesto"
            ),
            "evidenze": evidenze,
            "fiducia": 0.35 if evidenze else 0.25,
            "origine": evento
        }

    if evento == "supporto_informativo_potenziale":
        return {
            "concetto": "supporto_informativo_potenziale",
            "ipotesi": (
                "e' presente un possibile supporto informativo, "
                "ma il contenuto non e' ancora disponibile"
            ),
            "evidenze": evidenze,
            "fiducia": 0.25,
            "origine": evento
        }

    if evento == "dettaglio_funzionale_osservabile":
        return {
            "concetto": "dettaglio_funzionale",
            "ipotesi": (
                "la scena contiene un dettaglio potenzialmente utile "
                "per orientamento o decisioni future"
            ),
            "evidenze": evidenze,
            "fiducia": 0.30,
            "origine": evento
        }

    return None


def salva_ipotesi_semantica(ipotesi, mondo=None):
    if not isinstance(ipotesi, dict):
        return None

    concetto = _testo(ipotesi.get("concetto"))
    if not concetto:
        return None

    evidenze = ipotesi.get("evidenze", [])
    if not isinstance(evidenze, list):
        evidenze = []

    dati = _carica_memoria()
    firma = _firma(concetto, evidenze)

    for voce in dati["ipotesi"]:
        if voce.get("firma") == firma:
            voce["ultimo_aggiornamento"] = time.time()
            voce["osservazioni"] = int(voce.get("osservazioni", 1)) + 1
            voce["fiducia"] = min(
                1.0,
                float(voce.get("fiducia", 0.3)) + 0.05
            )

            for e in evidenze:
                if e not in voce.get("evidenze", []):
                    voce.setdefault("evidenze", []).append(e)

            for campo in CAMPI_SEMANTICI:
                if campo in ipotesi:
                    voce[campo] = ipotesi.get(campo)

            _aggiorna_stabilita(voce)
            _salva_memoria(dati)
            return voce

    nuova = _costruisci_voce_salvata(ipotesi, mondo)
    dati["ipotesi"].append(nuova)
    dati["ipotesi"] = dati["ipotesi"][-100:]
    _salva_memoria(dati)
    return nuova


def trova_ipotesi_simili(concetto=None, evidenze=None, limite=5):
    dati = _carica_memoria()
    risultati = []

    concetto_norm = _testo(concetto)
    evidenze_norm = []
    if isinstance(evidenze, list):
        evidenze_norm = [_normalizza(e) for e in evidenze]

    for voce in dati.get("ipotesi", []):
        punteggio = 0

        if concetto_norm and concetto_norm == _testo(voce.get("concetto")):
            punteggio += 3

        voce_evidenze = [
            _normalizza(e)
            for e in voce.get("evidenze", [])
        ]

        for e in evidenze_norm:
            if e in voce_evidenze:
                punteggio += 1

        if punteggio > 0:
            copia = dict(voce)
            copia["punteggio_similarita"] = punteggio
            risultati.append(copia)

    risultati.sort(
        key=lambda v: (
            v.get("punteggio_similarita", 0),
            v.get("fiducia", 0)
        ),
        reverse=True
    )

    return risultati[:limite]


def aggiorna_fiducia_ipotesi(firma, confermata=True, motivo=""):
    dati = _carica_memoria()

    for voce in dati.get("ipotesi", []):
        if voce.get("firma") != firma:
            continue

        if confermata:
            voce["conferme"] = int(voce.get("conferme", 0)) + 1
            voce["fiducia"] = min(
                1.0,
                float(voce.get("fiducia", 0.3)) + 0.15
            )
        else:
            voce["smentite"] = int(voce.get("smentite", 0)) + 1
            voce["fiducia"] = max(
                0.0,
                float(voce.get("fiducia", 0.3)) - 0.20
            )

        voce["ultimo_motivo_aggiornamento"] = motivo
        voce["ultimo_aggiornamento"] = time.time()
        _aggiorna_stabilita(voce)
        _salva_memoria(dati)
        return voce

    return None


def _eventi_per_aggiornamento(evento):
    evento_norm = _testo(evento)
    if evento_norm in EVENTI_SEMANTICI:
        return [evento_norm]
    return list(EVENTI_SEMANTICI)


def _deduplica_ipotesi(ipotesi):
    viste = {}
    risultato = []

    if not isinstance(ipotesi, list):
        return risultato

    for voce in ipotesi:
        if not isinstance(voce, dict):
            continue

        chiave = (
            _testo(voce.get("concetto")),
            "|".join(_lista_norm(voce.get("evidenze", [])))
        )
        if chiave in viste:
            continue
        viste[chiave] = True
        risultato.append(voce)

    return risultato


def _punteggio_rilevanza(voce, ipotesi_correnti):
    punteggio = 0

    if not isinstance(voce, dict):
        return punteggio

    for ipotesi in ipotesi_correnti:
        if not isinstance(ipotesi, dict):
            continue

        if _testo(voce.get("concetto")) != _testo(ipotesi.get("concetto")):
            continue

        punteggio += 3
        punteggio += len(
            _sovrapposizione(
                voce.get("evidenze", []),
                ipotesi.get("evidenze", [])
            )
        )
        punteggio += _campi_semantici_simili(voce, ipotesi)

    return punteggio


def _costruisci_ipotesi_per_osservazione(mondo, evento=None):
    ipotesi = []
    for evento_corrente in _eventi_per_aggiornamento(evento):
        ipotesi.extend(
            costruisci_ipotesi_multiple_da_evento(
                evento_corrente,
                mondo
            )
        )
    return _deduplica_ipotesi(ipotesi)


def recupera_conoscenze_stabili_rilevanti(mondo, evento=None, limite=5):
    dati = _carica_memoria()
    ipotesi_correnti = _costruisci_ipotesi_per_osservazione(mondo, evento)
    risultati = []

    for voce in dati.get("ipotesi", []):
        if not isinstance(voce, dict):
            continue
        if not voce.get("conoscenza_stabile", False):
            continue

        punteggio = _punteggio_rilevanza(voce, ipotesi_correnti)
        if punteggio <= 0:
            continue

        copia = dict(voce)
        copia["punteggio_rilevanza"] = punteggio
        risultati.append(copia)

    risultati.sort(
        key=lambda v: (
            v.get("punteggio_rilevanza", 0),
            v.get("fiducia", 0),
            v.get("conferme", 0)
        ),
        reverse=True
    )

    return risultati[:limite]


def _rafforza_voce(voce, nuova_ipotesi, mondo):
    voce["ultimo_aggiornamento"] = time.time()
    voce["osservazioni"] = int(voce.get("osservazioni", 1) or 1) + 1
    voce["conferme"] = int(voce.get("conferme", 0) or 0) + 1
    voce["fiducia"] = min(
        1.0,
        float(voce.get("fiducia", 0.3)) + 0.12
    )
    voce["evidenze"] = _unisci_lista(
        voce.get("evidenze", []),
        nuova_ipotesi.get("evidenze", [])
    )
    voce["mondo_ultimo_esempio"] = mondo or ""

    for campo in CAMPI_SEMANTICI:
        if campo in ["affordance", "conseguenze_possibili"]:
            voce[campo] = _unisci_lista(
                voce.get(campo, []),
                nuova_ipotesi.get(campo, [])
            )
        elif nuova_ipotesi.get(campo):
            voce[campo] = nuova_ipotesi.get(campo)

    _aggiorna_stabilita(voce)
    return voce


def _indebolisci_voce(voce, motivo):
    voce["ultimo_aggiornamento"] = time.time()
    voce["smentite"] = int(voce.get("smentite", 0) or 0) + 1
    voce["fiducia"] = max(
        0.0,
        float(voce.get("fiducia", 0.3)) - 0.08
    )
    voce["ultimo_motivo_aggiornamento"] = motivo
    _aggiorna_stabilita(voce)
    return voce


def aggiorna_ipotesi_da_osservazione(mondo, evento=None):
    dati = _carica_memoria()
    ipotesi_salvate = dati.get("ipotesi", [])
    if not isinstance(ipotesi_salvate, list):
        ipotesi_salvate = []
        dati["ipotesi"] = ipotesi_salvate

    nuove_ipotesi = _costruisci_ipotesi_per_osservazione(mondo, evento)

    esito = {
        "nuove_ipotesi": len(nuove_ipotesi),
        "confermate": 0,
        "smentite": 0,
        "inserite": 0,
        "stabili": 0,
        "aggiornate": []
    }

    confermate_firme = {}

    for nuova in nuove_ipotesi:
        corrispondenza = None
        for voce in ipotesi_salvate:
            if _ipotesi_simile(voce, nuova):
                corrispondenza = voce
                break

        if corrispondenza is not None:
            _rafforza_voce(corrispondenza, nuova, mondo)
            esito["confermate"] += 1
            firma = corrispondenza.get("firma")
            if firma:
                confermate_firme[firma] = True
            esito["aggiornate"].append({
                "firma": firma,
                "concetto": corrispondenza.get("concetto"),
                "fiducia": corrispondenza.get("fiducia"),
                "conoscenza_stabile": corrispondenza.get(
                    "conoscenza_stabile",
                    False
                )
            })
            continue

        inserita = _costruisci_voce_salvata(nuova, mondo)
        ipotesi_salvate.append(inserita)
        esito["inserite"] += 1
        firma = inserita.get("firma")
        if firma:
            confermate_firme[firma] = True
        esito["aggiornate"].append({
            "firma": firma,
            "concetto": inserita.get("concetto"),
            "fiducia": inserita.get("fiducia"),
            "conoscenza_stabile": inserita.get(
                "conoscenza_stabile",
                False
            )
        })

    concetti_nuovi = {}
    for nuova in nuove_ipotesi:
        concetto = _testo(nuova.get("concetto"))
        if concetto:
            concetti_nuovi[concetto] = True

    for voce in ipotesi_salvate:
        firma = voce.get("firma")
        if firma in confermate_firme:
            continue
        if _testo(voce.get("concetto")) not in concetti_nuovi:
            continue

        conflitto = False
        for nuova in nuove_ipotesi:
            if _conflitto_reale(voce, nuova):
                conflitto = True
                break

        if conflitto:
            _indebolisci_voce(voce, "osservazione simile non conferma l'ipotesi")
            esito["smentite"] += 1
            esito["aggiornate"].append({
                "firma": firma,
                "concetto": voce.get("concetto"),
                "fiducia": voce.get("fiducia"),
                "conoscenza_stabile": voce.get(
                    "conoscenza_stabile",
                    False
                )
            })

    for voce in dati.get("ipotesi", []):
        if _aggiorna_stabilita(voce):
            esito["stabili"] += 1

    dati["ipotesi"] = dati.get("ipotesi", [])[-100:]
    _salva_memoria(dati)
    return esito


def ipotesi_pronta_per_condizione(voce):
    if not isinstance(voce, dict):
        return False

    try:
        fiducia = float(voce.get("fiducia", 0.0))
    except Exception:
        fiducia = 0.0

    conferme = int(voce.get("conferme", 0) or 0)
    smentite = int(voce.get("smentite", 0) or 0)

    return (
        fiducia >= 0.70
        and conferme >= 2
        and smentite == 0
    )


def elenco_conoscenze():
    return _carica_memoria().get("ipotesi", [])
