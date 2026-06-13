# -*- coding: utf-8 -*-
from __future__ import unicode_literals

"""
Memoria leggera di goal e intenti per NAO.

Non sostituisce condizioni, ipotesi o world model: interpreta gli eventi
rispetto a cio' che il robot stava cercando di fare.
"""

import re
import time
import unicodedata

try:
    basestring
except NameError:
    basestring = str


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


def _contiene(testo, parole):
    for parola in parole:
        if parola in testo:
            return True
    return False


def _eventi_attivi(firma):
    if not isinstance(firma, dict):
        return []

    eventi = firma.get("eventi_attivi", {})
    if isinstance(eventi, dict):
        return [
            str(nome).lower()
            for nome, valore in eventi.items()
            if valore not in [False, None, "", [], {}]
        ]

    if isinstance(eventi, list):
        return [str(nome).lower() for nome in eventi]

    return []


def _goal_da_runtime(stato_runtime):
    if not isinstance(stato_runtime, dict):
        return {}

    sorgenti = [
        "goal_corrente",
        "obiettivo_corrente",
        "intento_corrente",
        "task_corrente",
        "piano_corrente"
    ]

    for chiave in sorgenti:
        valore = stato_runtime.get(chiave)

        if isinstance(valore, dict):
            goal = dict(valore)
            goal.setdefault("origine", chiave)
            return goal

        if isinstance(valore, basestring) and valore.strip():
            return {
                "descrizione": valore.strip(),
                "origine": chiave,
                "stato": "attivo"
            }

    destinazione = stato_runtime.get("destinazione") or stato_runtime.get("target")
    if isinstance(destinazione, basestring) and destinazione.strip():
        return {
            "descrizione": "raggiungere {}".format(destinazione.strip()),
            "target": destinazione.strip(),
            "tipo": "navigazione",
            "origine": "destinazione_runtime",
            "stato": "attivo"
        }

    return {}


def _descrizione_goal(goal):
    if not isinstance(goal, dict):
        return ""

    for chiave in ["descrizione", "obiettivo", "goal", "intent", "nome"]:
        valore = goal.get(chiave)
        if isinstance(valore, basestring) and valore.strip():
            return valore.strip()

    return ""


def _tipo_goal(goal):
    tipo = str(goal.get("tipo", "")).lower()
    descrizione = _normalizza(_descrizione_goal(goal))

    if tipo:
        return tipo

    if _contiene(descrizione, [
        "raggiung", "andare", "vai", "entrare", "uscire",
        "porta", "stanza", "laboratorio", "corridoio",
        "passaggio", "percorso"
    ]):
        return "navigazione"

    if _contiene(descrizione, [
        "leggere", "leggi", "capire", "interpreta",
        "monitor", "schermo", "testo", "errore",
        "informazione", "istruzioni"
    ]):
        return "informazione"

    if _contiene(descrizione, [
        "cercare", "cerca", "trovare", "trova",
        "controllare", "verificare"
    ]):
        return "ricerca"

    return "generico"


def _target_goal(goal):
    target = goal.get("target") or goal.get("destinazione")
    if isinstance(target, basestring) and target.strip():
        return _normalizza(target)

    descrizione = _normalizza(_descrizione_goal(goal))
    candidati = [
        "porta",
        "stanza",
        "laboratorio",
        "corridoio",
        "accesso",
        "monitor",
        "schermo",
        "display",
        "tavolo",
        "persona"
    ]

    trovati = []
    for parola in candidati:
        if parola in descrizione and parola not in trovati:
            trovati.append(parola)

    return " ".join(trovati)


def _credenza_world_model(world_model):
    if not isinstance(world_model, dict):
        return {}

    credenza = world_model.get("credenza", {})
    if isinstance(credenza, dict):
        return credenza

    return {}


def valuta_goal_intent(mondo, firma=None, stato_runtime=None, world_model=None):
    """
    Valuta la scena rispetto al goal attivo.

    Ritorna una struttura descrittiva: il chiamante decide se trasformarla
    in decisione immediata.
    """

    if stato_runtime is None:
        stato_runtime = {}

    goal = _goal_da_runtime(stato_runtime)
    descrizione = _descrizione_goal(goal)

    if not goal or not descrizione:
        return {
            "goal_attivo": False,
            "rilevanza_evento": "nessun_goal",
            "motivo": "nessun goal attivo nel runtime"
        }

    stato_goal = str(goal.get("stato", "attivo")).lower()
    if stato_goal in ["completato", "concluso", "annullato", "sospeso"]:
        return {
            "goal_attivo": False,
            "goal": goal,
            "rilevanza_evento": "goal_non_attivo",
            "motivo": "goal non attivo"
        }

    testo = _normalizza(mondo)
    eventi = set(_eventi_attivi(firma or {}))
    eventi_testo = " ".join(eventi)
    tipo_goal = _tipo_goal(goal)
    target_goal = _target_goal(goal)
    credenza = _credenza_world_model(world_model)
    stato_normale = str(credenza.get("stato_normale", ""))
    stato_corrente = str(credenza.get("stato_corrente", ""))
    anomalia = bool(
        isinstance(world_model, dict)
        and world_model.get("anomalia")
    )

    base = " ".join([
        testo,
        eventi_testo,
        target_goal,
        stato_corrente,
        stato_normale
    ])

    accesso_bloccato = (
        "accesso_non_disponibile" in eventi
        or "accesso_o_percorso_limitato" in eventi
        or _contiene(base, [
            "porta chiusa",
            "chiusa",
            "chiuso",
            "bloccato",
            "bloccata",
            "non disponibile",
            "non accessibile",
            "ostruito",
            "ostruita"
        ])
    )

    informazione_utile = (
        "informazione_operativa" in eventi
        or "contenuto_informativo_rilevante" in eventi
        or _contiene(base, [
            "testo leggibile",
            "errore",
            "istruzioni",
            "messaggio"
        ])
    )

    ostacolo = (
        "ostacolo_frontale" in eventi
        or "ostacolo_sinistra" in eventi
        or "ostacolo_destra" in eventi
        or "oggetto_in_zona_rilevante" in eventi
    )

    if tipo_goal in ["navigazione", "accesso"] and accesso_bloccato:
        return _esito_goal(
            goal,
            tipo_goal,
            "ostacola_goal",
            "rivedi_piano",
            "alta",
            (
                "l'accesso o il percorso necessario al goal sembra limitato"
            ),
            world_model,
            firma
        )

    if tipo_goal in ["navigazione", "accesso"] and ostacolo:
        return _esito_goal(
            goal,
            tipo_goal,
            "ostacola_goal",
            "osserva_con_prudenza",
            "alta",
            "un elemento spaziale puo' interferire con il movimento",
            world_model,
            firma
        )

    if tipo_goal in ["informazione", "ricerca"] and informazione_utile:
        return _esito_goal(
            goal,
            tipo_goal,
            "supporta_goal",
            "approfondisci_goal",
            "media",
            "la scena contiene informazione utile per il goal",
            world_model,
            firma
        )

    if anomalia and tipo_goal in ["navigazione", "accesso", "ricerca"]:
        return _esito_goal(
            goal,
            tipo_goal,
            "potrebbe_impattare_goal",
            "osserva_con_prudenza",
            "media",
            "il world model segnala una variazione rilevante",
            world_model,
            firma
        )

    return _esito_goal(
        goal,
        tipo_goal,
        "irrilevante_o_debole",
        "continua",
        "bassa",
        "nessun impatto chiaro sul goal corrente",
        world_model,
        firma
    )


def _esito_goal(
    goal,
    tipo_goal,
    rilevanza,
    azione,
    priorita,
    motivo,
    world_model,
    firma
):
    esito = {
        "goal_attivo": True,
        "goal": goal,
        "obiettivo": _descrizione_goal(goal),
        "tipo_goal": tipo_goal,
        "rilevanza_evento": rilevanza,
        "azione_agentica": azione,
        "priorita": priorita,
        "motivo": motivo,
        "aggiornato_il": _adesso()
    }

    if isinstance(world_model, dict):
        esito["world_model"] = {
            "anomalia": world_model.get("anomalia", False),
            "familiare": world_model.get("familiare", False)
        }

        credenza = _credenza_world_model(world_model)
        if credenza:
            esito["world_model"].update({
                "entita": credenza.get("entita", ""),
                "stato_corrente": credenza.get("stato_corrente", ""),
                "stato_normale": credenza.get("stato_normale", ""),
                "fiducia": credenza.get("fiducia", 0.0)
            })

    if isinstance(firma, dict):
        esito["eventi_attivi"] = _eventi_attivi(firma)

    return esito


def costruisci_decisione_goal_intent(esito):
    if not isinstance(esito, dict):
        return None

    if not esito.get("goal_attivo"):
        return None

    azione = esito.get("azione_agentica")
    rilevanza = esito.get("rilevanza_evento")

    if azione == "continua" or rilevanza == "irrilevante_o_debole":
        return None

    obiettivo = esito.get("obiettivo", "")
    motivo = esito.get("motivo", "")

    if azione == "rivedi_piano":
        revisione = _costruisci_revisione_piano(esito)
        return {
            "stato_interno": "deliberativo",
            "obiettivo": "rivedere il piano rispetto al goal attivo",
            "azioni": [
                {"tipo": "occhi", "colore": "yellow"},
                {"tipo": "fermati"},
                {"tipo": "guarda", "x": 0.0, "y": -0.25},
                {
                    "tipo": "parla",
                    "testo": "Questo ostacola il mio obiettivo. Devo valutare un piano alternativo."
                }
            ],
            "memoria": [
                _voce_memoria_goal(esito),
                revisione
            ]
        }

    if azione == "approfondisci_goal":
        target = _target_goal(esito.get("goal", {})) or "contenuto osservato"
        return {
            "stato_interno": "attento",
            "obiettivo": "approfondire informazione utile al goal",
            "azioni": [
                {"tipo": "occhi", "colore": "blue"},
                {"tipo": "guarda", "x": 0.0, "y": -0.25},
                {
                    "tipo": "parla",
                    "testo": "Questa informazione puo' aiutare il mio obiettivo. La osservo meglio."
                }
            ],
            "memoria": [
                _voce_memoria_goal(esito),
                {
                    "tipo": "osservazione_mirata",
                    "target": target,
                    "motivo": motivo,
                    "azione_cognitiva": "interpreta_e_memorizza",
                    "cosa_cercare": [
                        "testo leggibile",
                        "errore",
                        "istruzioni"
                    ]
                }
            ]
        }

    if azione == "osserva_con_prudenza":
        target = _target_goal(esito.get("goal", {})) or "situazione osservata"
        return {
            "stato_interno": "prudente",
            "obiettivo": "verificare un possibile impatto sul goal",
            "azioni": [
                {"tipo": "occhi", "colore": "yellow"},
                {"tipo": "guarda", "x": 0.0, "y": -0.25},
                {
                    "tipo": "parla",
                    "testo": "Potrebbe influire sul mio obiettivo. Lo verifico prima di procedere."
                }
            ],
            "memoria": [
                _voce_memoria_goal(esito),
                {
                    "tipo": "osservazione_mirata",
                    "target": target,
                    "motivo": motivo,
                    "azione_cognitiva": "osserva_con_prudenza",
                    "cosa_cercare": [
                        "ostruzione",
                        "percorso libero",
                        "cambiamento rispetto al normale"
                    ]
                }
            ]
        }

    return None


def registra_revisione_piano_corrente(stato_runtime, decisione):
    """
    Copia nel runtime la revisione piano prodotta da una decisione goal-aware.
    """

    if stato_runtime is None or not isinstance(decisione, dict):
        return decisione

    memoria = decisione.get("memoria", [])
    revisione = None

    if isinstance(memoria, list):
        for voce in memoria:
            if isinstance(voce, dict) and voce.get("tipo") == "revisione_piano":
                revisione = voce
                break

    if not isinstance(revisione, dict):
        return decisione

    piano = revisione.get("piano_da_rivedere", {})
    ostacolo = revisione.get("ostacolo_al_goal", {})
    azione = revisione.get("azione_successiva_suggerita", {})

    if isinstance(piano, dict):
        stato_runtime["piano_da_rivedere"] = dict(piano)

    if isinstance(ostacolo, dict):
        stato_runtime["ostacolo_al_goal"] = dict(ostacolo)

    if isinstance(azione, dict):
        stato_runtime["azione_successiva_suggerita"] = dict(azione)

    stato_runtime["revisione_piano_corrente"] = dict(revisione)

    subgoal = revisione.get("subgoal_alternativi", [])
    if isinstance(subgoal, list):
        stato_runtime["subgoal_goal_corrente"] = [
            dict(voce)
            for voce in subgoal
            if isinstance(voce, dict)
        ]

    _aggiorna_goal_status(
        stato_runtime,
        "attivo",
        "piano alternativo inizializzato"
    )

    storia = stato_runtime.get("revisioni_piano_recenti", [])
    if not isinstance(storia, list):
        storia = []

    storia.append(dict(revisione))
    stato_runtime["revisioni_piano_recenti"] = storia[-5:]

    return decisione


def costruisci_decisione_azione_successiva(stato_runtime):
    """
    Trasforma una azione_successiva_suggerita in un piano concreto.
    """

    if not isinstance(stato_runtime, dict):
        return None

    decisione_status = costruisci_decisione_goal_status(stato_runtime)
    if decisione_status is not None:
        return decisione_status

    subgoal = _prossimo_subgoal_pendente(stato_runtime)
    if isinstance(subgoal, dict):
        stato_runtime["azione_successiva_suggerita"] = (
            _azione_da_subgoal(subgoal)
        )

    azione = stato_runtime.get("azione_successiva_suggerita", {})
    if not isinstance(azione, dict):
        return None

    stato_azione = str(azione.get("stato", "pendente")).lower()
    if stato_azione in ["in_corso", "completata", "scaduta", "annullata"]:
        return None

    piano = stato_runtime.get("piano_da_rivedere", {})
    if not isinstance(piano, dict):
        piano = {}

    ostacolo = stato_runtime.get("ostacolo_al_goal", {})
    if not isinstance(ostacolo, dict):
        ostacolo = {}

    target = (
        azione.get("target")
        or ostacolo.get("target")
        or piano.get("target")
        or "percorso alternativo"
    )

    cosa_cercare = azione.get("cosa_cercare", [])
    if not isinstance(cosa_cercare, list) or not cosa_cercare:
        cosa_cercare = [
            "percorso alternativo",
            "accesso disponibile",
            "ostacolo temporaneo",
            "possibilita' di attendere"
        ]

    motivo = (
        azione.get("descrizione")
        or azione.get("motivo")
        or "verificare una alternativa al piano bloccato"
    )

    azione["stato"] = "in_corso"
    azione["avviata_il"] = _adesso()
    azione["target"] = target
    stato_runtime["azione_successiva_suggerita"] = azione

    subgoal_id = azione.get("subgoal_id")
    if subgoal_id:
        _aggiorna_subgoal(
            stato_runtime,
            subgoal_id,
            "in_corso",
            "osservazione avviata"
        )

    return {
        "stato_interno": "deliberativo",
        "obiettivo": "cercare un passo alternativo per il goal",
        "azioni": [
            {"tipo": "occhi", "colore": "yellow"},
            {"tipo": "guarda", "x": 0.0, "y": -0.25},
            {
                "tipo": "parla",
                "testo": "Cerco un'alternativa prima di rinunciare al mio obiettivo."
            }
        ],
        "memoria": [
            {
                "tipo": "azione_successiva_goal",
                "piano_da_rivedere": piano,
                "ostacolo_al_goal": ostacolo,
                "azione_successiva_suggerita": azione
            },
            {
                "tipo": "osservazione_mirata",
                "target": target,
                "motivo": motivo,
                "azione_cognitiva": azione.get(
                    "azione_cognitiva",
                    "osserva_con_prudenza"
                ),
                "cosa_cercare": cosa_cercare
            }
        ]
    }


def costruisci_decisione_goal_status(stato_runtime):
    if not isinstance(stato_runtime, dict):
        return None

    goal_status = stato_runtime.get("goal_status", {})
    if not isinstance(goal_status, dict):
        return None

    stato = str(goal_status.get("stato", "")).lower()
    if stato not in ["in_attesa", "fallito", "bloccato_temporaneamente"]:
        return None

    if goal_status.get("decisione_comunicata"):
        return None

    goal_status["decisione_comunicata"] = True
    stato_runtime["goal_status"] = goal_status

    testo = "Non riesco a completare questo obiettivo ora. Lo metto in attesa e riprovero' piu' tardi."
    colore = "yellow"

    if stato == "fallito":
        testo = "Non ho trovato un modo per completare questo obiettivo. Registro il fallimento."
        colore = "red"
    elif stato == "bloccato_temporaneamente":
        testo = "Il mio obiettivo e' temporaneamente bloccato. Aspetto nuove evidenze."

    return {
        "stato_interno": "deliberativo",
        "obiettivo": "chiudere temporaneamente un goal non risolto",
        "azioni": [
            {"tipo": "occhi", "colore": colore},
            {
                "tipo": "parla",
                "testo": testo
            }
        ],
        "memoria": [
            {
                "tipo": "goal_status",
                "stato": goal_status.get("stato", ""),
                "motivo": goal_status.get("motivo", ""),
                "retry_after": goal_status.get("retry_after", None),
                "ultimo_motivo_fallimento": goal_status.get(
                    "ultimo_motivo_fallimento",
                    ""
                ),
                "goal_history": stato_runtime.get("goal_history", [])
            }
        ]
    }


def aggiorna_azione_successiva_da_osservazione(esito, stato_runtime=None):
    """
    Chiude o aggiorna l'azione successiva quando arriva l'esito percettivo.
    """

    if stato_runtime is None or not isinstance(esito, dict):
        return None

    azione = stato_runtime.get("azione_successiva_suggerita", {})
    if not isinstance(azione, dict):
        return None

    if str(azione.get("stato", "")).lower() != "in_corso":
        return None

    tentativo = int(esito.get("tentativo", 1))
    trovato = bool(esito.get("trovato"))

    if trovato:
        azione["stato"] = "completata"
        azione["risultato"] = "alternativa_o_evidenza_trovata"
        stato_subgoal = "completato"
    elif tentativo >= 3:
        azione["stato"] = "scaduta"
        azione["risultato"] = "nessuna_alternativa_confermata"
        stato_subgoal = "fallito"
    else:
        azione["stato"] = "in_corso"
        azione["risultato"] = "ancora_da_verificare"
        stato_subgoal = "in_corso"

    azione["ultimo_esito"] = {
        "trovato": trovato,
        "tentativo": tentativo,
        "target": esito.get("target", ""),
        "segnali_trovati": esito.get("segnali_trovati", []),
        "segnali_mancanti": esito.get("segnali_mancanti", [])
    }
    azione["aggiornata_il"] = _adesso()

    stato_runtime["azione_successiva_suggerita"] = azione

    subgoal_id = azione.get("subgoal_id")
    if subgoal_id:
        _aggiorna_subgoal(
            stato_runtime,
            subgoal_id,
            stato_subgoal,
            azione.get("risultato", "")
        )
        valuta_stato_goal_corrente(stato_runtime)

    if stato_subgoal in ["completato", "fallito"]:
        stato_runtime.pop("azione_successiva_suggerita", None)

    revisione = stato_runtime.get("revisione_piano_corrente", {})
    if isinstance(revisione, dict):
        revisione["azione_successiva_suggerita"] = dict(azione)
        stato_runtime["revisione_piano_corrente"] = revisione

    return azione


def valuta_stato_goal_corrente(stato_runtime):
    """
    Decide se il goal e' attivo, completato, in attesa o fallito.
    """

    if not isinstance(stato_runtime, dict):
        return None

    subgoal = stato_runtime.get("subgoal_goal_corrente", [])
    if not isinstance(subgoal, list) or not subgoal:
        return stato_runtime.get("goal_status")

    stati = []
    for voce in subgoal:
        if isinstance(voce, dict):
            stati.append(str(voce.get("stato", "pendente")).lower())

    if "completato" in stati:
        return _aggiorna_goal_status(
            stato_runtime,
            "completato",
            "un subgoal alternativo ha prodotto evidenza utile"
        )

    if "in_corso" in stati:
        return _aggiorna_goal_status(
            stato_runtime,
            "attivo",
            "subgoal alternativo in corso"
        )

    if "pendente" in stati:
        return _aggiorna_goal_status(
            stato_runtime,
            "attivo",
            "subgoal alternativi ancora disponibili"
        )

    if stati and all(stato == "fallito" for stato in stati):
        ultimo = _ultimo_subgoal(subgoal)
        motivo = (
            ultimo.get("risultato")
            or "tutti i subgoal alternativi sono falliti"
        )

        return _aggiorna_goal_status(
            stato_runtime,
            "in_attesa",
            motivo,
            retry_after=300,
            ultimo_motivo_fallimento=motivo
        )

    return _aggiorna_goal_status(
        stato_runtime,
        "bloccato_temporaneamente",
        "goal bloccato ma stato dei subgoal non conclusivo"
    )


def _ultimo_subgoal(subgoal):
    ultimo = {}

    for voce in subgoal:
        if isinstance(voce, dict):
            ultimo = voce

    return ultimo


def _aggiorna_goal_status(
    stato_runtime,
    stato,
    motivo,
    retry_after=None,
    ultimo_motivo_fallimento=None
):
    goal_status = {
        "stato": stato,
        "motivo": motivo,
        "aggiornato_il": _adesso()
    }

    piano = stato_runtime.get("piano_da_rivedere", {})
    if isinstance(piano, dict):
        goal_status["obiettivo"] = piano.get("obiettivo", "")
        goal_status["target"] = piano.get("target", "")
        piano["stato_goal"] = stato
        stato_runtime["piano_da_rivedere"] = piano

    if retry_after is not None:
        try:
            retry_after = int(retry_after)
        except Exception:
            retry_after = 300

        goal_status["retry_after"] = retry_after
        goal_status["retry_after_timestamp"] = int(time.time()) + retry_after

    if ultimo_motivo_fallimento:
        goal_status["ultimo_motivo_fallimento"] = ultimo_motivo_fallimento
        stato_runtime["ultimo_motivo_fallimento"] = (
            ultimo_motivo_fallimento
        )

    stato_runtime["goal_status"] = goal_status

    storia = stato_runtime.get("goal_history", [])
    if not isinstance(storia, list):
        storia = []

    if (
        not storia
        or storia[-1].get("stato") != stato
        or storia[-1].get("motivo") != motivo
    ):
        storia.append(dict(goal_status))

    stato_runtime["goal_history"] = storia[-10:]

    revisione = stato_runtime.get("revisione_piano_corrente", {})
    if isinstance(revisione, dict):
        revisione["goal_status"] = dict(goal_status)
        stato_runtime["revisione_piano_corrente"] = revisione

    return goal_status


def _prossimo_subgoal_pendente(stato_runtime):
    subgoal = stato_runtime.get("subgoal_goal_corrente", [])
    if not isinstance(subgoal, list):
        return None

    for voce in subgoal:
        if not isinstance(voce, dict):
            continue

        stato = str(voce.get("stato", "pendente")).lower()
        if stato == "pendente":
            return voce

    return None


def _azione_da_subgoal(subgoal):
    return {
        "tipo": "subgoal_goal",
        "subgoal_id": subgoal.get("id", ""),
        "nome": subgoal.get("nome", ""),
        "target": subgoal.get("target", ""),
        "azione_cognitiva": subgoal.get(
            "azione_cognitiva",
            "osserva_con_prudenza"
        ),
        "descrizione": subgoal.get("descrizione", ""),
        "cosa_cercare": subgoal.get("cosa_cercare", []),
        "stato": "pendente"
    }


def _aggiorna_subgoal(stato_runtime, subgoal_id, stato, risultato):
    subgoal = stato_runtime.get("subgoal_goal_corrente", [])
    if not isinstance(subgoal, list):
        return

    aggiornati = []
    for voce in subgoal:
        if not isinstance(voce, dict):
            continue

        voce = dict(voce)
        if voce.get("id") == subgoal_id:
            voce["stato"] = stato
            voce["risultato"] = risultato
            voce["aggiornato_il"] = _adesso()

        aggiornati.append(voce)

    stato_runtime["subgoal_goal_corrente"] = aggiornati

    revisione = stato_runtime.get("revisione_piano_corrente", {})
    if isinstance(revisione, dict):
        revisione["subgoal_alternativi"] = aggiornati
        stato_runtime["revisione_piano_corrente"] = revisione


def _costruisci_revisione_piano(esito):
    goal = esito.get("goal", {})
    world_model = esito.get("world_model", {})
    target = _target_goal(goal)

    if not target and isinstance(world_model, dict):
        target = world_model.get("entita", "")

    if not target:
        target = "goal corrente"

    ostacolo = esito.get("motivo", "evento rilevante per il goal")

    if isinstance(world_model, dict):
        stato_corrente = world_model.get("stato_corrente", "")
        stato_normale = world_model.get("stato_normale", "")

        if stato_corrente or stato_normale:
            ostacolo = (
                "{}: stato corrente '{}', stato normale '{}'"
                .format(target, stato_corrente, stato_normale)
            )

    return {
        "tipo": "revisione_piano",
        "obiettivo": esito.get("obiettivo", ""),
        "goal": goal,
        "target": target,
        "motivo": esito.get("motivo", ""),
        "azione": "rivedi_piano",
        "piano_da_rivedere": {
            "obiettivo": esito.get("obiettivo", ""),
            "tipo_goal": esito.get("tipo_goal", ""),
            "target": target,
            "stato": "bloccato_o_incerto",
            "motivo": esito.get("motivo", "")
        },
        "ostacolo_al_goal": {
            "target": target,
            "descrizione": ostacolo,
            "eventi_attivi": esito.get("eventi_attivi", []),
            "world_model": world_model
        },
        "azione_successiva_suggerita": {
            "tipo": "osservazione_o_alternativa",
            "subgoal_id": "verifica_ostacolo",
            "azione_cognitiva": "osserva_con_prudenza",
            "descrizione": (
                "verificare l'ostacolo e cercare un percorso o piano alternativo"
            ),
            "cosa_cercare": [
                "percorso alternativo",
                "accesso disponibile",
                "ostacolo temporaneo",
                "possibilita' di attendere"
            ]
        },
        "subgoal_alternativi": _subgoal_alternativi_goal(
            esito,
            target,
            world_model
        ),
        "creata_il": _adesso()
    }


def _subgoal_alternativi_goal(esito, target, world_model):
    return [
        {
            "id": "verifica_ostacolo",
            "nome": "verificare porta o accesso",
            "target": target,
            "stato": "pendente",
            "priorita": 1,
            "azione_cognitiva": "osserva_con_prudenza",
            "descrizione": "verificare se l'accesso e' davvero bloccato",
            "cosa_cercare": [
                "stato dell'accesso",
                "accesso disponibile",
                "ostruzione",
                "porta temporaneamente chiusa"
            ]
        },
        {
            "id": "cerca_accesso_alternativo",
            "nome": "cercare accesso alternativo",
            "target": "percorso alternativo",
            "stato": "pendente",
            "priorita": 2,
            "azione_cognitiva": "osserva_con_prudenza",
            "descrizione": "cercare un altro accesso o passaggio disponibile",
            "cosa_cercare": [
                "percorso alternativo",
                "accesso disponibile",
                "passaggio libero",
                "altra porta"
            ]
        },
        {
            "id": "attendi_temporaneo",
            "nome": "attendere se il blocco e' temporaneo",
            "target": target,
            "stato": "pendente",
            "priorita": 3,
            "azione_cognitiva": "osserva_meglio",
            "descrizione": "capire se l'ostacolo e' temporaneo",
            "cosa_cercare": [
                "ostacolo temporaneo",
                "persona che sta usando l'accesso",
                "porta in movimento",
                "possibilita' di attendere"
            ]
        },
        {
            "id": "chiedi_aiuto_umano",
            "nome": "chiedere aiuto umano",
            "target": "persona vicina",
            "stato": "pendente",
            "priorita": 4,
            "azione_cognitiva": "richiedi_supporto",
            "descrizione": "chiedere aiuto se nessuna alternativa e' confermata",
            "cosa_cercare": [
                "persona vicina",
                "volto riconosciuto",
                "voce umana",
                "possibilita' di chiedere aiuto"
            ]
        }
    ]


def _voce_memoria_goal(esito):
    return {
        "tipo": "goal_intent",
        "obiettivo": esito.get("obiettivo", ""),
        "tipo_goal": esito.get("tipo_goal", ""),
        "rilevanza_evento": esito.get("rilevanza_evento", ""),
        "azione_agentica": esito.get("azione_agentica", ""),
        "priorita": esito.get("priorita", ""),
        "motivo": esito.get("motivo", ""),
        "world_model": esito.get("world_model", {}),
        "eventi_attivi": esito.get("eventi_attivi", [])
    }
