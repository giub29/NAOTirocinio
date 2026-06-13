# -*- coding: utf-8 -*-
from __future__ import unicode_literals

"""
Pianificatore di osservazione mirata per NAO.

Trasforma una azione cognitiva debole in un piano percettivo concreto:
cosa guardare, perche', e quali segnali cercare nella prossima percezione.
Non genera condizioni e non decide al posto del supervisore.
"""

import re
import time
import unicodedata

try:
    basestring
except NameError:
    basestring = str


AZIONI_PERCETTIVE = [
    "osserva_meglio",
    "osserva_con_prudenza",
    "interpreta_e_memorizza",
    "approfondisci_osservazione",
    "prudenza",
    "memoria"
]


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


def _testo_breve(testo, limite=180):
    if isinstance(testo, basestring):
        testo = testo or ""
    else:
        testo = str(testo or "")

    testo = " ".join(testo.split())

    if len(testo) <= limite:
        return testo

    return testo[:limite].rstrip() + "..."


def registra_osservazione_mirata_corrente(stato_runtime, decisione):
    """
    Salva nel runtime il piano di osservazione mirata prodotto da una decisione.
    """

    if stato_runtime is None or not isinstance(decisione, dict):
        return decisione

    piano = None
    memoria = decisione.get("memoria", [])

    if isinstance(memoria, list):
        for voce in memoria:
            if (
                isinstance(voce, dict)
                and voce.get("tipo") == "osservazione_mirata"
            ):
                piano = dict(voce)
                break

    if piano is None:
        return decisione

    piano_precedente = stato_runtime.get("osservazione_mirata_corrente", {})
    if not isinstance(piano_precedente, dict):
        piano_precedente = {}

    stesso_target = (
        piano_precedente.get("target")
        and piano_precedente.get("target") == piano.get("target")
    )

    piano["attiva_il"] = piano_precedente.get(
        "attiva_il",
        _adesso()
    )
    piano["tentativi"] = (
        int(piano_precedente.get("tentativi", 0))
        if stesso_target else 0
    )
    piano["stato"] = "attiva"
    stato_runtime["osservazione_mirata_corrente"] = piano

    storia = stato_runtime.get("osservazioni_mirate_recenti", [])
    if not isinstance(storia, list):
        storia = []

    storia.append(piano)
    stato_runtime["osservazioni_mirate_recenti"] = storia[-5:]

    return decisione


def _credenza_da_world_model(world_model):
    if not isinstance(world_model, dict):
        return {}

    credenza = world_model.get("credenza", {})
    if isinstance(credenza, dict):
        return credenza

    if world_model.get("entita") or world_model.get("stato_corrente"):
        return world_model

    return {}


def _eventi_da_firma(firma):
    if not isinstance(firma, dict):
        return []

    eventi_attivi = firma.get("eventi_attivi", {})

    if isinstance(eventi_attivi, dict):
        return [
            str(nome).lower()
            for nome, valore in eventi_attivi.items()
            if valore not in [False, None, "", [], {}]
        ]

    if isinstance(eventi_attivi, list):
        return [str(nome).lower() for nome in eventi_attivi]

    eventi = firma.get("eventi", {})
    if isinstance(eventi, dict):
        return [
            str(nome).lower()
            for nome, valore in eventi.items()
            if valore not in [False, None, "", [], {}]
        ]

    return []


def _contiene(testo, parole):
    for parola in parole:
        if parola in testo:
            return True
    return False


def _nega_segnale(testo, parole):
    negazioni = [
        "non",
        "senza",
        "nessun",
        "nessuna",
        "manca",
        "assente"
    ]

    for parola in parole:
        if parola not in testo:
            continue

        for negazione in negazioni:
            pattern = negazione + " " + parola
            if pattern in testo:
                return True

    return False


def _token_utili(testo):
    parole_vuote = [
        "report", "vedo", "sento", "rilevo", "sono", "fermo",
        "sto", "camminando", "una", "uno", "un", "la", "il",
        "lo", "le", "gli", "nel", "nella", "sul", "sulla",
        "con", "senza", "che", "qui", "stesso", "stessa",
        "del", "della", "dei", "delle", "cosa", "qualcosa",
        "stato", "elemento", "situazione"
    ]

    token = []

    for parola in _normalizza(testo).split():
        if len(parola) < 4:
            continue
        if parola in parole_vuote:
            continue
        if parola not in token:
            token.append(parola)

    return token


def _categoria_funzione(testo, azione_cognitiva, ragionamento, firma):
    eventi = " ".join(_eventi_da_firma(firma))
    tipo = ""

    if isinstance(ragionamento, dict):
        tipo = str(ragionamento.get("tipo", "")).lower()

    base = " ".join([testo, eventi, tipo, str(azione_cognitiva or "")])

    if _contiene(base, [
        "informazione", "informativo", "testuale", "testo",
        "scritta", "leggibile", "errore", "istruzioni",
        "monitor", "schermo", "display", "cartello", "documento"
    ]):
        return "informazione"

    if _contiene(base, [
        "accesso", "passaggio", "percorso", "porta",
        "ingresso", "uscita", "corridoio", "non disponibile",
        "limitato", "blocc", "chius"
    ]):
        return "accesso"

    if _contiene(base, [
        "anomalia", "anomalo", "danneggiato", "rotto",
        "fuori posto", "prudenza", "pericolo"
    ]):
        return "anomalia"

    if _contiene(base, [
        "zona", "ostacolo", "oggetto", "elemento",
        "vicino", "davanti"
    ]):
        return "spazio"

    return "generica"


def _target_da_testo(testo, credenza, categoria):
    entita = credenza.get("entita", "")
    if entita:
        return str(entita).replace("_", " ")

    candidati = [
        ("monitor", ["monitor", "schermo", "display", "terminale"]),
        ("cartello", ["cartello", "scritta", "segnale"]),
        ("documento", ["documento", "foglio", "lavagna"]),
        ("accesso", ["porta", "accesso", "passaggio", "corridoio", "ingresso", "uscita"]),
        ("elemento", ["oggetto", "elemento", "struttura", "dispositivo"]),
        ("zona", ["zona", "area", "percorso"])
    ]

    for target, parole in candidati:
        if _contiene(testo, parole):
            return target

    parole_vuote = [
        "report", "vedo", "sento", "rilevo", "sono", "fermo",
        "sto", "camminando", "una", "uno", "un", "la", "il",
        "lo", "le", "gli", "nel", "nella", "sul", "sulla",
        "con", "senza", "che", "qui", "stesso", "stessa",
        "chiuso", "chiusa", "aperto", "aperta", "spento",
        "spenta", "acceso", "accesa", "leggibile", "visibile",
        "testo", "errore", "informazione", "contenuto",
        "non", "del", "della", "dei", "delle"
    ]

    token = []
    for parola in testo.split():
        if len(parola) < 4:
            continue
        if parola in parole_vuote:
            continue
        if parola not in token:
            token.append(parola)

    if token:
        return " ".join(token[:2])

    if categoria == "informazione":
        return "contenuto osservato"
    if categoria == "accesso":
        return "accesso osservato"
    if categoria == "anomalia":
        return "elemento osservato"

    return "situazione osservata"


def _cosa_cercare(categoria, azione_cognitiva, credenza):
    stato_normale = str(credenza.get("stato_normale", ""))
    stato_corrente = str(credenza.get("stato_corrente", ""))

    if categoria == "informazione":
        segnali = [
            "testo leggibile",
            "errore",
            "istruzioni",
            "vincoli"
        ]
    elif categoria == "accesso":
        segnali = [
            "stato dell'accesso",
            "ostruzione",
            "percorso libero",
            "variazione rispetto al normale"
        ]
    elif categoria == "anomalia":
        segnali = [
            "danno visibile",
            "posizione anomala",
            "rischio",
            "cambiamento rispetto al normale"
        ]
    elif categoria == "spazio":
        segnali = [
            "posizione dell'elemento",
            "distanza",
            "percorso libero",
            "possibile ostacolo"
        ]
    else:
        segnali = [
            "dettagli utili",
            "stato dell'elemento",
            "cambiamento",
            "informazione nuova"
        ]

    if stato_normale and stato_corrente and stato_normale != stato_corrente:
        segnali.append("conferma del cambiamento")

    if azione_cognitiva == "interpreta_e_memorizza":
        segnali.append("informazione da ricordare")

    risultato = []
    for segnale in segnali:
        if segnale not in risultato:
            risultato.append(segnale)

    return risultato[:6]


def _profilo_azione(azione_cognitiva, categoria, anomalia):
    if azione_cognitiva in ["interpreta_e_memorizza", "memoria"]:
        return (
            "attento",
            "blue",
            "osservare e interpretare un contenuto utile",
            "Provo a leggere meglio il contenuto."
        )

    if anomalia or azione_cognitiva in ["osserva_con_prudenza", "prudenza"]:
        return (
            "prudente",
            "yellow",
            "verificare con prudenza una variazione osservata",
            "Osservo con prudenza prima di decidere."
        )

    if categoria == "informazione":
        return (
            "attento",
            "blue",
            "chiarire un contenuto informativo incerto",
            "Provo a leggere meglio il contenuto."
        )

    return (
        "curioso",
        "yellow",
        "raccogliere dettagli mancanti dalla scena",
        "Osservo meglio questa parte dell'ambiente."
    )


def costruisci_piano_osservazione(
    mondo=None,
    azione_cognitiva=None,
    motivo=None,
    ipotesi=None,
    world_model=None,
    ragionamento=None,
    firma=None
):
    """
    Crea un piano di active perception serializzabile.
    """

    if isinstance(ipotesi, dict):
        azione_cognitiva = (
            azione_cognitiva or
            ipotesi.get("azione_temporanea")
        )
        motivo = (
            motivo or
            ipotesi.get("descrizione") or
            ipotesi.get("ipotesi")
        )

    if isinstance(ragionamento, dict):
        azione_cognitiva = (
            azione_cognitiva or
            ragionamento.get("azione_cognitiva")
        )
        motivo = (
            motivo or
            ragionamento.get("ipotesi") or
            ragionamento.get("tipo")
        )

    if azione_cognitiva not in AZIONI_PERCETTIVE:
        return None

    credenza = _credenza_da_world_model(world_model)
    testo = _normalizza(mondo)
    anomalia = False

    if isinstance(world_model, dict):
        anomalia = bool(world_model.get("anomalia"))
    if credenza.get("anomalia"):
        anomalia = True

    categoria = _categoria_funzione(
        testo,
        azione_cognitiva,
        ragionamento,
        firma
    )
    target = _target_da_testo(testo, credenza, categoria)
    stato_interno, colore, obiettivo, frase = _profilo_azione(
        azione_cognitiva,
        categoria,
        anomalia
    )

    stato_normale = credenza.get("stato_normale", "")
    stato_corrente = credenza.get("stato_corrente", "")

    if anomalia and stato_normale and stato_corrente:
        motivo = (
            motivo or
            "stato corrente diverso dallo stato abituale"
        )

    piano = {
        "tipo": "osservazione_mirata",
        "target": target,
        "motivo": _testo_breve(
            motivo or "informazione mancante per decidere"
        ),
        "azione_cognitiva": azione_cognitiva,
        "categoria": categoria,
        "cosa_cercare": _cosa_cercare(
            categoria,
            azione_cognitiva,
            credenza
        ),
        "azioni": [
            {
                "tipo": "guarda",
                "x": 0.0,
                "y": -0.25
            },
            {
                "tipo": "parla",
                "testo": frase
            }
        ]
    }

    if credenza:
        piano["world_model"] = {
            "entita": credenza.get("entita", ""),
            "stato_corrente": stato_corrente,
            "stato_normale": stato_normale,
            "fiducia": credenza.get("fiducia", 0.0),
            "anomalia": anomalia
        }

    piano["_decisione"] = {
        "stato_interno": stato_interno,
        "colore": colore,
        "obiettivo": obiettivo
    }

    return piano


def costruisci_decisione_osservazione_mirata(
    mondo=None,
    azione_cognitiva=None,
    motivo=None,
    ipotesi=None,
    world_model=None,
    ragionamento=None,
    firma=None
):
    piano = costruisci_piano_osservazione(
        mondo=mondo,
        azione_cognitiva=azione_cognitiva,
        motivo=motivo,
        ipotesi=ipotesi,
        world_model=world_model,
        ragionamento=ragionamento,
        firma=firma
    )

    if not piano:
        return None

    decisione_info = piano.pop("_decisione", {})
    azioni = [
        {
            "tipo": "occhi",
            "colore": decisione_info.get("colore", "yellow")
        }
    ]
    azioni.extend(piano.get("azioni", []))

    return {
        "stato_interno": decisione_info.get("stato_interno", "riflessivo"),
        "obiettivo": decisione_info.get(
            "obiettivo",
            "osservare in modo mirato prima di decidere"
        ),
        "azioni": azioni,
        "memoria": [
            piano
        ]
    }


def _indicatori_per_segnale(segnale):
    segnale_norm = _normalizza(segnale)

    if "testo leggibile" in segnale_norm:
        return [
            "testo leggibile",
            "testo visibile",
            "scritta leggibile",
            "scritta visibile",
            "contenuto leggibile",
            "messaggio visibile"
        ]

    if "errore" in segnale_norm:
        return [
            "errore",
            "warning",
            "allarme",
            "avviso",
            "messaggio di errore"
        ]

    if "istruzioni" in segnale_norm:
        return [
            "istruzione",
            "istruzioni",
            "procedura",
            "seguire",
            "premere",
            "inserire",
            "conferire"
        ]

    if "vincol" in segnale_norm:
        return [
            "vietato",
            "obbligo",
            "limite",
            "non entrare",
            "non toccare",
            "solo personale"
        ]

    if "accesso" in segnale_norm or "percorso" in segnale_norm:
        return [
            "accesso",
            "passaggio",
            "percorso",
            "porta",
            "aperto",
            "aperta",
            "chiuso",
            "chiusa",
            "libero",
            "bloccato",
            "non accessibile"
        ]

    if "ostruzione" in segnale_norm:
        return [
            "ostru",
            "blocc",
            "ingombro",
            "impedisce",
            "non posso passare",
            "davanti al passaggio"
        ]

    if "libero" in segnale_norm:
        return [
            "libero",
            "libera",
            "accessibile",
            "aperto",
            "aperta",
            "posso passare"
        ]

    if "danno" in segnale_norm:
        return [
            "rotto",
            "rotta",
            "danneggiato",
            "danneggiata",
            "crepa",
            "rovinato"
        ]

    if "anom" in segnale_norm:
        return [
            "anomalo",
            "anomala",
            "fuori posto",
            "strano",
            "caduto",
            "spostato"
        ]

    if "rischio" in segnale_norm:
        return [
            "pericolo",
            "rischio",
            "caduta",
            "ostacolo",
            "bloccato"
        ]

    if "cambiamento" in segnale_norm or "variazione" in segnale_norm:
        return [
            "ora",
            "adesso",
            "diverso",
            "cambiato",
            "non e piu",
            "rispetto a prima",
            "stesso"
        ]

    return _token_utili(segnale_norm)


def _segnale_trovato(segnale, testo):
    indicatori = _indicatori_per_segnale(segnale)

    if not indicatori:
        return False

    if _nega_segnale(testo, indicatori):
        return False

    return _contiene(testo, indicatori)


def _target_presente(target, testo):
    token_target = _token_utili(target)

    if not token_target:
        return False

    for token in token_target:
        if token in testo:
            return True

    return False


def valuta_risposta_osservazione_mirata(
    mondo,
    piano,
    firma=None,
    world_model=None
):
    """
    Confronta una nuova percezione con il piano attivo.

    Ritorna un esito temporaneo: non genera condizioni, ma dice se NAO
    ha trovato almeno parte di cio' che aveva deciso di cercare.
    """

    if not isinstance(piano, dict):
        return None

    if piano.get("tipo") != "osservazione_mirata":
        return None

    testo = _normalizza(mondo)
    cosa_cercare = piano.get("cosa_cercare", [])
    if not isinstance(cosa_cercare, list):
        cosa_cercare = []

    segnali_trovati = []
    segnali_mancanti = []

    for segnale in cosa_cercare:
        if _segnale_trovato(segnale, testo):
            segnali_trovati.append(segnale)
        else:
            segnali_mancanti.append(segnale)

    credenza = _credenza_da_world_model(world_model)
    if not credenza and isinstance(piano.get("world_model"), dict):
        credenza = piano.get("world_model")

    cambiamento_confermato = False
    stato_normale = credenza.get("stato_normale", "")
    stato_corrente = credenza.get("stato_corrente", "")

    if stato_normale and stato_corrente and stato_normale != stato_corrente:
        cambiamento_confermato = True
        if "conferma del cambiamento" not in segnali_trovati:
            segnali_trovati.append("conferma del cambiamento")
        if "conferma del cambiamento" in segnali_mancanti:
            segnali_mancanti.remove("conferma del cambiamento")

    target = piano.get("target", "")
    target_presente = _target_presente(target, testo)

    trovato = bool(segnali_trovati)
    if target_presente and not trovato:
        stato = "target_ritrovato"
    elif trovato and segnali_mancanti:
        stato = "parziale"
    elif trovato:
        stato = "trovato"
    else:
        stato = "non_trovato"

    esito = {
        "tipo": "esito_osservazione_mirata",
        "aggiornata_il": _adesso(),
        "target": target,
        "target_presente": target_presente,
        "trovato": trovato,
        "stato": stato,
        "segnali_trovati": segnali_trovati,
        "segnali_mancanti": segnali_mancanti,
        "cambiamento_confermato": cambiamento_confermato,
        "motivo": piano.get("motivo", ""),
        "mondo": _testo_breve(mondo, 260)
    }

    if isinstance(firma, dict):
        esito["eventi_attivi"] = _eventi_da_firma(firma)

    if credenza:
        esito["world_model"] = {
            "entita": credenza.get("entita", ""),
            "stato_corrente": stato_corrente,
            "stato_normale": stato_normale,
            "fiducia": credenza.get("fiducia", 0.0),
            "anomalia": credenza.get("anomalia", False)
        }

    return esito
