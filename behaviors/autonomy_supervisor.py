# -*- coding: utf-8 -*-
"""
Autonomy Supervisor

Modulo centrale per la gestione autonoma delle condizioni.

Responsabilità:
- valutare automaticamente le condizioni già generate;
- decidere se una situazione nuova merita una nuova condizione;
- generare autonomamente nuove condizioni tramite LLM;
- rivalutare subito le condizioni dopo la generazione;
- proteggere soul.py da errori del generator o del condition_manager;
- dare priorità agli eventi composti prima delle condizioni semplici.

Questo modulo è il punto di passaggio tra:
percezione → firma evento → condizione esistente/generazione → decisione.
"""

import logging
import traceback
import time
import os
import inspect
import re

try:
    from behaviors.event_system.unknown_event_extractor import (
        estrai_eventi_sconosciuti
    )
except Exception:
    estrai_eventi_sconosciuti = None

try:
    from behaviors.event_system.structured_event import (
        costruisci_evento_strutturato as costruisci_evento_strutturato_layer
    )
except Exception:
    costruisci_evento_strutturato_layer = None

try:
    from behaviors.event_system.structured_event_policy import (
        decidi_da_evento_strutturato
    )
except Exception:
    decidi_da_evento_strutturato = None

try:
    from behaviors.event_system.structured_hypothesis_evaluator import (
        valuta_ipotesi_da_evento_strutturato
    )
except Exception:
    valuta_ipotesi_da_evento_strutturato = None

try:
    from behaviors.event_system.event_registry import arricchisci_eventi_registro
except Exception:
    arricchisci_eventi_registro = None

try:
    from behaviors.event_system.autonomous_curiosity_manager import (
        costruisci_decisione_curiosa
    )
except Exception:
    costruisci_decisione_curiosa = None

try:
    from behaviors.agentic_system.agentic_orchestrator import (
        esegui_ciclo_agentico
    )
except Exception:
    esegui_ciclo_agentico = None

try:
    from behaviors.condition_system.condition_memory import (
        trova_condizioni_simili,
        registra_feedback_osservazione_mirata
    )
except Exception:
    trova_condizioni_simili = None
    registra_feedback_osservazione_mirata = None

try:
    from behaviors.event_system.episodic_hypothesis_memory import (
        valuta_ipotesi_temporanee,
        costruisci_decisione_ipotesi,
        aggiorna_ipotesi_da_osservazione_mirata
    )
except Exception:
    valuta_ipotesi_temporanee = None
    costruisci_decisione_ipotesi = None
    aggiorna_ipotesi_da_osservazione_mirata = None

try:
    from behaviors.event_system.world_model_memory import (
        aggiorna_world_model,
        costruisci_decisione_world_model,
        aggiorna_world_model_da_osservazione_mirata
    )
except Exception:
    aggiorna_world_model = None
    costruisci_decisione_world_model = None
    aggiorna_world_model_da_osservazione_mirata = None

try:
    from behaviors.event_system.active_perception_planner import (
        costruisci_decisione_osservazione_mirata,
        valuta_risposta_osservazione_mirata,
        registra_osservazione_mirata_corrente
    )
except Exception:
    costruisci_decisione_osservazione_mirata = None
    valuta_risposta_osservazione_mirata = None
    registra_osservazione_mirata_corrente = (
        lambda stato_runtime, decisione: decisione
    )

try:
    from behaviors.agentic_system.goal_intent_memory import (
        valuta_goal_intent,
        costruisci_decisione_goal_intent,
        registra_revisione_piano_corrente,
        costruisci_decisione_azione_successiva,
        aggiorna_azione_successiva_da_osservazione
    )
except Exception:
    valuta_goal_intent = None
    costruisci_decisione_goal_intent = None
    registra_revisione_piano_corrente = (
        lambda stato_runtime, decisione: decisione
    )
    costruisci_decisione_azione_successiva = None
    aggiorna_azione_successiva_da_osservazione = None

try:
    from behaviors.event_system.knowledge_memory import (
        costruisci_ipotesi_multiple_da_evento,
        costruisci_ipotesi_da_evento,
        aggiorna_ipotesi_da_osservazione,
        recupera_conoscenze_stabili_rilevanti,
        salva_ipotesi_semantica
    )
except Exception:
    costruisci_ipotesi_multiple_da_evento = None
    costruisci_ipotesi_da_evento = None
    aggiorna_ipotesi_da_osservazione = None
    recupera_conoscenze_stabili_rilevanti = None
    salva_ipotesi_semantica = None

from behaviors.event_system.unknown_generation_simulator import simula_condizione_sconosciuta

logger = logging.getLogger(__name__)
try:
    basestring
except NameError:
    basestring = str

BASE_DIR = os.path.dirname(__file__)
CONDIZIONI_GENERATE_DIR = os.path.join(
    BASE_DIR,
    "condition_system",
    "generated_conditions"
)
ULTIMA_GENERAZIONE = 0
INTERVALLO_MINIMO_GENERAZIONE = 20
ULTIMO_MONDO_GENERATO = None
EVENTI_HELPER_NON_GENERATIVI = [
    "interazione_utente"
]
FALLBACK_VISIVI_NON_GENERATIVI = [
    "non distinguo elementi rilevanti senza analisi visiva llm",
    "scena acquisita dalla camera, ma non distinguo elementi rilevanti",
    "non distinguo elementi rilevanti",
    "senza analisi visiva llm"
]
EVENTI_SUPPORTO_INFORMATIVO_NON_GENERATIVI = [
    "supporto_informativo_potenziale",
    "supporto_informativo_non_disponibile"
]
CONDIZIONI_INFORMATIVE_GENERALI = [
    "condizione_contenuto_informativo_rilevante",
    "condizione_informazione_operativa"
]
EVENTI_NOVITA_SPECIFICHE_GENERATIVE = [
    "vincolo_comportamentale",
    "accesso_non_disponibile",
    "accesso_disponibile",
    "accesso_o_percorso_limitato",
    "oggetto_in_zona_rilevante",
    "oggetto_funzione_sconosciuta",
    "elemento_ambientale_anomalo",
    "elemento_fuori_posto",
    "ostacolo_destra",
    "ostacolo_sinistra",
    "ostacolo_frontale"
]
COOLDOWN_SCENA_COMPRESA = 300
COOLDOWN_CURIOSITA_RIPETUTA = 180
TESTO_INFORMAZIONE_OPERATIVA_COMPRESA = (
    "Ho trovato alcune informazioni utili per comprendere meglio questo luogo."
)
TERMINI_TROPPO_SPECIFICI_EVENTO_GENERALE = [
    "cosa ci",
    "dentro questo",
    "oggetto specifico",
    "elemento specifico",
    "supporto specifico"
]
TERMINI_TESTO_OPERATIVO_SPECIFICO = [
    "vietato",
    "obbligatorio",
    "riservato",
    "accesso",
    "uscita",
    "entrata",
    "entrare",
    "non entrare",
    "pericolo",
    "attenzione",
    "rischio",
    "orario",
    "orari",
    "aperto",
    "chiuso",
    "dalle",
    "alle",
    "procedura",
    "istruzione",
    "istruzioni",
    "seguire",
    "premere",
    "usare",
    "utilizzare",
    "emergenza"
]


def _diag_pipeline(label, valore):
    return None


def _testo_sicuro(valore):
    if isinstance(valore, basestring):
        return valore

    try:
        return str(valore or "")
    except Exception:
        return ""


def _maschera_dati_sensibili(valore):
    try:
        if isinstance(valore, dict):
            risultato = {}
            for chiave, contenuto in valore.items():
                chiave_testo = str(chiave).lower()
                if (
                    "api_key" in chiave_testo
                    or "openai" in chiave_testo
                    or "chiave_privata" in chiave_testo
                ):
                    risultato[chiave] = "***MASKED***"
                else:
                    risultato[chiave] = _maschera_dati_sensibili(contenuto)
            return risultato

        if isinstance(valore, list):
            return [_maschera_dati_sensibili(v) for v in valore]

        if isinstance(valore, tuple):
            return tuple(_maschera_dati_sensibili(v) for v in valore)

        if isinstance(valore, basestring):
            return re.sub(
                r"sk-[A-Za-z0-9_\-]{8,}",
                "sk-***MASKED***",
                valore
            )
    except Exception:
        return "***MASKED***"

    return valore


def filtra_eventi_helper(eventi):
    if not isinstance(eventi, list):
        return []

    return [
        e for e in eventi
        if str(e).lower().strip() not in EVENTI_HELPER_NON_GENERATIVI
    ]


def _testo_contiene_fallback_visivo_generico(mondo):
    testo = _testo_sicuro(mondo).lower()
    return any(
        indicatore in testo
        for indicatore in FALLBACK_VISIVI_NON_GENERATIVI
    )


def _evento_strutturato_neutro_non_generativo(evento_strutturato):
    if not isinstance(evento_strutturato, dict):
        return False

    categoria = str(
        evento_strutturato.get("categoria", "") or ""
    ).lower()
    genera = evento_strutturato.get("genera_condizione", False)
    eventi_core = evento_strutturato.get("eventi_core", [])

    if not isinstance(eventi_core, list):
        eventi_core = []

    return (
        categoria == "neutra"
        and genera is False
        and len(filtra_eventi_helper(eventi_core)) == 0
    )


def situazione_fallback_visivo_neutra(mondo, evento_strutturato):
    return (
        _testo_contiene_fallback_visivo_generico(mondo)
        and _evento_strutturato_neutro_non_generativo(evento_strutturato)
    )


def evento_informazione_operativa(stato_runtime):
    if not isinstance(stato_runtime, dict):
        return False

    evento = stato_runtime.get("evento_strutturato", {})
    if not isinstance(evento, dict):
        evento = {}

    eventi_core = evento.get("eventi_core", [])
    if not isinstance(eventi_core, list):
        eventi_core = []

    eventi = stato_runtime.get("eventi", {})
    if not isinstance(eventi, dict):
        eventi = {}

    ragionamento = evento.get("ragionamento_unknown", {})
    if not isinstance(ragionamento, dict):
        ragionamento = {}

    return (
        "informazione_operativa" in eventi_core
        or "contenuto_informativo_rilevante" in eventi_core
        or eventi.get("informazione_operativa") not in [
            False, None, "", [], {}
        ]
        or eventi.get("contenuto_informativo_rilevante") not in [
            False, None, "", [], {}
        ]
        or ragionamento.get("evento") in [
            "informazione_operativa",
            "contenuto_informativo_rilevante"
        ]
    )


def _evento_attivo(dati, nome):
    if not isinstance(dati, dict):
        return False

    return dati.get(nome) not in [False, None, "", [], {}]


def _sanitizza_eventi_supporto_informativo(eventi):
    if not isinstance(eventi, dict):
        return eventi

    eventi_forti = [
        "informazione_operativa",
        "contenuto_informativo_rilevante",
        "vincolo_comportamentale",
        "accesso_non_disponibile",
        "accesso_disponibile",
        "accesso_o_percorso_limitato",
        "oggetto_in_zona_rilevante",
        "oggetto_funzione_sconosciuta",
        "elemento_ambientale_anomalo",
        "elemento_fuori_posto",
        "dettaglio_funzionale_osservabile"
    ]

    if any(_evento_attivo(eventi, nome) for nome in eventi_forti):
        eventi.pop("supporto_informativo_potenziale", None)
        eventi.pop("supporto_informativo_non_disponibile", None)
        return eventi

    if _evento_attivo(eventi, "supporto_informativo_non_disponibile"):
        eventi.pop("supporto_informativo_potenziale", None)

    return eventi


def _evento_strutturato_supporto_non_generativo(evento_strutturato):
    if not isinstance(evento_strutturato, dict):
        return False

    categoria = str(
        evento_strutturato.get("categoria", "") or ""
    ).lower()
    stato = str(evento_strutturato.get("stato", "") or "").lower()
    tipo = str(evento_strutturato.get("tipo", "") or "").lower()
    eventi_core = evento_strutturato.get("eventi_core", [])

    if not isinstance(eventi_core, list):
        eventi_core = []

    eventi_core = [
        str(e).lower().strip()
        for e in eventi_core
        if e not in [None, False, "", [], {}]
    ]

    return (
        categoria == "supporto_informativo"
        or stato in ["potenziale", "non_disponibile"]
        or tipo in [
            "supporto_informativo_potenziale",
            "supporto_informativo_non_disponibile"
        ]
        or "supporto_informativo_potenziale" in eventi_core
        or "supporto_informativo_non_disponibile" in eventi_core
    )


def evento_strutturato_non_deve_generare(evento_strutturato):
    if not isinstance(evento_strutturato, dict):
        return False

    genera = evento_strutturato.get("genera_condizione", False)
    azione = str(
        evento_strutturato.get("azione_cognitiva", "") or ""
    ).lower()

    if genera is False and azione == "ignora":
        return True

    return _evento_strutturato_supporto_non_generativo(evento_strutturato)


def evento_strutturato_da_chiudere_senza_decisione(evento_strutturato):
    if not isinstance(evento_strutturato, dict):
        return False

    genera = evento_strutturato.get("genera_condizione", False)
    azione = str(
        evento_strutturato.get("azione_cognitiva", "") or ""
    ).lower()
    categoria = str(
        evento_strutturato.get("categoria", "") or ""
    ).lower()
    stato = str(evento_strutturato.get("stato", "") or "").lower()
    tipo = str(evento_strutturato.get("tipo", "") or "").lower()

    return (
        (genera is False and azione == "ignora")
        or (
            categoria == "supporto_informativo"
            and (
                stato == "non_disponibile"
                or tipo == "supporto_informativo_non_disponibile"
            )
        )
    )


def chiudi_generazione_non_permessa(stato_runtime, motivo):
    if not isinstance(stato_runtime, dict):
        return

    stato_runtime.pop("forza_generazione_da_ipotesi_strutturata", None)
    stato_runtime.pop("motivo_generazione_ipotesi_strutturata", None)
    stato_runtime["decisione_non_generativa"] = motivo


def _normalizza_firma_testo(testo):
    testo = _testo_sicuro(testo).lower()
    testo = testo.replace("report:", " ")
    testo = testo.replace("vedo:", " ")
    testo = re.sub(r"[^a-z0-9\s_]", " ", testo)
    testo = re.sub(r"\s+", " ", testo).strip()
    parole = []
    stop = [
        "sono", "fermo", "vedo", "ancora", "una", "uno", "con",
        "che", "per", "del", "della", "dei", "delle", "qui"
    ]
    for parola in testo.split():
        if len(parola) < 4:
            continue
        if parola in stop:
            continue
        if parola not in parole:
            parole.append(parola)
    return "_".join(parole[:8])


def firma_scena_generale(mondo, stato_runtime=None, firma=None):
    parti = ["scena"]

    evento_strutturato = {}
    if isinstance(stato_runtime, dict):
        evento_strutturato = stato_runtime.get("evento_strutturato", {})
    if not isinstance(evento_strutturato, dict):
        evento_strutturato = {}

    if isinstance(firma, dict):
        evento_firma = firma.get("evento_strutturato", {})
        if isinstance(evento_firma, dict) and evento_firma:
            evento_strutturato = evento_firma

    for chiave in ["categoria", "tipo", "stato"]:
        valore = str(evento_strutturato.get(chiave, "") or "").lower()
        if valore:
            parti.append(chiave + "=" + valore)

    eventi_core = evento_strutturato.get("eventi_core", [])
    if not isinstance(eventi_core, list):
        eventi_core = []

    eventi_core = filtra_eventi_helper([
        str(e).lower().strip()
        for e in eventi_core
        if str(e).strip()
    ])
    if eventi_core:
        parti.append("core=" + ",".join(sorted(eventi_core)))

    parti.append("testo=" + _normalizza_firma_testo(mondo))
    return "|".join(parti)


def osservazioni_mirate_per_scena(stato_runtime, mondo, firma=None):
    if not isinstance(stato_runtime, dict):
        return 0

    memoria = stato_runtime.get("osservazioni_mirate_scene", {})
    if not isinstance(memoria, dict):
        return 0

    scena = firma_scena_generale(mondo, stato_runtime, firma=firma)
    voce = memoria.get(scena, {})
    if not isinstance(voce, dict):
        return 0

    try:
        return int(voce.get("conteggio", 0) or 0)
    except Exception:
        return 0


def evento_rilevante_per_generazione_dopo_osservazione(
    stato_runtime,
    firma=None
):
    evento_strutturato = {}
    if isinstance(stato_runtime, dict):
        evento_strutturato = stato_runtime.get("evento_strutturato", {})
    if not isinstance(evento_strutturato, dict):
        evento_strutturato = {}

    if isinstance(firma, dict):
        evento_firma = firma.get("evento_strutturato", {})
        if isinstance(evento_firma, dict) and evento_firma:
            evento_strutturato = evento_firma

    if evento_strutturato_non_deve_generare(evento_strutturato):
        return False

    if evento_strutturato.get("genera_condizione") is True:
        return True

    categoria = str(evento_strutturato.get("categoria", "") or "").lower()
    if categoria in ["", "neutra", "ambiguita", "supporto_informativo"]:
        return False

    eventi_core = evento_strutturato.get("eventi_core", [])
    if not isinstance(eventi_core, list):
        eventi_core = []
    eventi_core = filtra_eventi_helper([
        e for e in eventi_core
        if e not in [None, False, "", [], {}]
    ])
    if len(eventi_core) == 0:
        return False

    try:
        rilevanza = float(evento_strutturato.get("rilevanza", 0) or 0)
    except Exception:
        rilevanza = 0

    return rilevanza >= 0.6


def registra_osservazione_mirata_per_scena(
    stato_runtime,
    decisione,
    mondo,
    firma=None
):
    if not isinstance(stato_runtime, dict):
        return decisione

    scena = firma_scena_generale(mondo, stato_runtime, firma=firma)
    memoria = stato_runtime.get("osservazioni_mirate_scene", {})
    if not isinstance(memoria, dict):
        memoria = {}

    voce = memoria.get(scena, {})
    if not isinstance(voce, dict):
        voce = {}

    conteggio = int(voce.get("conteggio", 0) or 0)
    if conteggio >= 1:
        stato_runtime["decisione_non_generativa"] = (
            "osservazione_mirata_gia_eseguita"
        )
        stato_runtime["forza_generazione_dopo_osservazione_mirata"] = True
        stato_runtime["motivo_generazione_dopo_osservazione_mirata"] = (
            "osservazione mirata gia' eseguita per la scena"
        )
        return None

    voce["conteggio"] = conteggio + 1
    voce["tempo"] = time.time()
    memoria[scena] = voce

    if len(memoria) > 20:
        try:
            elementi = sorted(
                memoria.items(),
                key=lambda item: item[1].get("tempo", 0)
            )
            memoria = dict(elementi[-20:])
        except Exception:
            pass

    stato_runtime["osservazioni_mirate_scene"] = memoria
    stato_runtime["ultima_scena_osservazione_mirata"] = scena
    return registra_osservazione_mirata_corrente(stato_runtime, decisione)


def firma_scena_operativa(mondo, stato_runtime):
    parti = ["informazione_operativa"]

    for sorgente in [
        stato_runtime.get("belief_state", {}),
        stato_runtime.get("world_model", {})
    ]:
        if not isinstance(sorgente, dict):
            continue

        chiave = sorgente.get("chiave")
        if not chiave and isinstance(sorgente.get("credenza"), dict):
            chiave = sorgente.get("credenza", {}).get("chiave")

        if chiave:
            parti.append(str(chiave).lower())
            return "|".join(parti)

    parti.append(_normalizza_firma_testo(mondo))
    return "|".join(parti)


def registra_scena_operativa_compresa(stato_runtime, mondo):
    if not isinstance(stato_runtime, dict):
        return None

    firma = firma_scena_operativa(mondo, stato_runtime)
    memoria = stato_runtime.get("scene_operative_comprese", {})
    if not isinstance(memoria, dict):
        memoria = {}

    memoria[firma] = {
        "tempo": time.time(),
        "evento": "informazione_operativa"
    }
    stato_runtime["scene_operative_comprese"] = memoria
    stato_runtime["ultima_scena_operativa_compresa"] = firma
    return firma


def _testi_parlati_decisione(decisione):
    if not isinstance(decisione, dict):
        return []

    testi = []
    azioni = decisione.get("azioni", [])
    if isinstance(azioni, list):
        for azione in azioni:
            if not isinstance(azione, dict):
                continue
            if azione.get("tipo") == "parla":
                testo = _testo_sicuro(azione.get("testo", "")).strip()
                if testo:
                    testi.append(testo)

    return testi


def decisione_sembra_curiosa(decisione):
    if not isinstance(decisione, dict):
        return False

    testi = " ".join(_testi_parlati_decisione(decisione)).lower()
    indicatori_testo = [
        "osservo meglio",
        "lo osservo meglio",
        "lo osservo con prudenza",
        "ho notato qualcosa",
        "prima di decidere",
        "potrebbe essere utile"
    ]
    if any(indicatore in testi for indicatore in indicatori_testo):
        return True

    memoria = decisione.get("memoria", [])
    if isinstance(memoria, list):
        for voce in memoria:
            if not isinstance(voce, dict):
                continue
            azione = str(voce.get("azione", "") or "").lower()
            tipo = str(voce.get("tipo", "") or "").lower()
            if azione in ["osserva_meglio", "osserva_con_prudenza"]:
                return True
            if tipo in ["curiosita", "politica_agentica"]:
                return True

    return False


def firma_curiosita(mondo, stato_runtime, decisione, firma):
    parti = ["curiosita"]

    evento_strutturato = stato_runtime.get("evento_strutturato", {})
    if not isinstance(evento_strutturato, dict):
        evento_strutturato = {}

    categoria = str(evento_strutturato.get("categoria", "") or "").lower()
    evento = str(evento_strutturato.get("evento", "") or "").lower()
    parti.append("categoria=" + categoria)
    parti.append("evento=" + evento)

    eventi_core = evento_strutturato.get("eventi_core", [])
    if not isinstance(eventi_core, list):
        eventi_core = []
    eventi_core = [
        str(e).lower().strip()
        for e in eventi_core
        if str(e).strip()
    ]
    if eventi_core:
        parti.append("core=" + ",".join(sorted(eventi_core)))

    eventi_attivi = {}
    for sorgente in [
        firma.get("eventi", {}) if isinstance(firma, dict) else {},
        firma.get("eventi_attivi", {}) if isinstance(firma, dict) else {},
        stato_runtime.get("eventi", {}),
        stato_runtime.get("eventi_reali", {})
    ]:
        if not isinstance(sorgente, dict):
            continue
        for nome, valore in sorgente.items():
            if valore not in [False, None, "", [], {}]:
                eventi_attivi[str(nome).lower().strip()] = True

    if eventi_attivi:
        parti.append("attivi=" + ",".join(sorted(eventi_attivi.keys())))

    parti.append("scena=" + _normalizza_firma_testo(mondo))
    parti.append(
        "frase=" + _normalizza_firma_testo(
            " ".join(_testi_parlati_decisione(decisione))
        )
    )

    return "|".join(parti)


def filtra_curiosita_ripetuta(decisione, stato_runtime, mondo, firma, origine):
    if not isinstance(stato_runtime, dict):
        return decisione

    if not decisione_sembra_curiosa(decisione):
        return decisione

    firma_corrente = firma_curiosita(mondo, stato_runtime, decisione, firma)
    memoria = stato_runtime.get("curiosita_recenti", {})
    if not isinstance(memoria, dict):
        memoria = {}

    voce = memoria.get(firma_corrente)
    if isinstance(voce, dict):
        try:
            recente = (
                time.time() - float(voce.get("tempo", 0))
                < COOLDOWN_CURIOSITA_RIPETUTA
            )
        except Exception:
            recente = True

        if recente:
            stato_runtime["decisione_non_generativa"] = (
                "curiosita_ripetuta_in_cooldown"
            )
            stato_runtime["ultima_curiosita_saltata"] = firma_corrente
            logger.info(
                "[AUTONOMIA] Curiosita gia' espressa di recente: "
                "salto ripetizione ({})".format(origine)
            )
            return None

    memoria[firma_corrente] = {
        "tempo": time.time(),
        "origine": origine
    }

    if len(memoria) > 20:
        try:
            elementi = sorted(
                memoria.items(),
                key=lambda item: item[1].get("tempo", 0)
            )
            memoria = dict(elementi[-20:])
        except Exception:
            pass

    stato_runtime["curiosita_recenti"] = memoria
    stato_runtime["ultima_curiosita_espressa"] = firma_corrente
    return decisione


def scena_operativa_gia_compresa(stato_runtime, mondo):
    if not evento_informazione_operativa(stato_runtime):
        return False

    firma = firma_scena_operativa(mondo, stato_runtime)
    memoria = stato_runtime.get("scene_operative_comprese", {})
    if not isinstance(memoria, dict):
        return False

    voce = memoria.get(firma)
    if not isinstance(voce, dict):
        return False

    ultimo = voce.get("tempo", 0)
    try:
        recente = time.time() - float(ultimo) < COOLDOWN_SCENA_COMPRESA
    except Exception:
        recente = True

    return recente


def rafforza_decisione_informazione_operativa(decisione, stato_runtime, mondo):
    if not isinstance(decisione, dict):
        return decisione

    if not evento_informazione_operativa(stato_runtime):
        return decisione

    azioni = decisione.get("azioni", [])
    if not isinstance(azioni, list):
        return decisione

    sintesi = costruisci_sintesi_semantica_osservazione(
        mondo,
        stato_runtime
    )
    if not sintesi:
        sintesi = TESTO_INFORMAZIONE_OPERATIVA_COMPRESA

    sostituita = False
    motivo_bassa_generalita = ""
    for azione in azioni:
        if not isinstance(azione, dict):
            continue
        if azione.get("tipo") != "parla":
            continue

        testo = _testo_sicuro(azione.get("testo", "")).lower()
        if (
            any(
                termine in testo
                for termine in TERMINI_TROPPO_SPECIFICI_EVENTO_GENERALE
            )
            or "interessante" in testo
            or not testo
        ):
            motivo_bassa_generalita = (
                "frase troppo specifica per evento informazione_operativa"
            )
            azione["testo"] = sintesi
            sostituita = True
            break

    if not sostituita:
        azioni.append({
            "tipo": "parla",
            "testo": sintesi
        })

    if motivo_bassa_generalita and isinstance(stato_runtime, dict):
        nome_condizione = stato_runtime.get(
            "ultima_condizione_attiva",
            "condizione_informazione_operativa"
        )
        condizioni = stato_runtime.get("condizioni_bassa_generalita", [])
        if not isinstance(condizioni, list):
            condizioni = []

        condizioni.append({
            "condizione": nome_condizione,
            "evento": "informazione_operativa",
            "azione": "rigenera_quando_possibile",
            "motivo": motivo_bassa_generalita
        })
        stato_runtime["condizioni_bassa_generalita"] = condizioni[-10:]
        stato_runtime["condizione_da_rigenerare"] = nome_condizione
        stato_runtime["motivo_rigenerazione_condizione"] = (
            motivo_bassa_generalita
        )

    memoria = decisione.get("memoria", [])
    if not isinstance(memoria, list):
        memoria = []
    memoria.append({
        "tipo": "scena_operativa_compresa",
        "evento": "informazione_operativa",
        "firma": registra_scena_operativa_compresa(stato_runtime, mondo)
    })
    decisione["memoria"] = memoria

    return decisione


def integra_eventi_sconosciuti_in_evento_strutturato(
    evento_strutturato,
    eventi_sconosciuti
):
    if not isinstance(evento_strutturato, dict):
        evento_strutturato = {}

    if not isinstance(eventi_sconosciuti, list):
        eventi_sconosciuti = []

    tipo_attuale = str(evento_strutturato.get("tipo", "") or "").lower()
    if tipo_attuale in ["", "generico", "neutra"]:
        evento_strutturato["tipo"] = "unknown"

    categoria_attuale = str(
        evento_strutturato.get("categoria", "") or ""
    ).lower()
    if categoria_attuale in ["", "neutra"]:
        evento_strutturato["categoria"] = "sconosciuta"

    origine_attuale = str(
        evento_strutturato.get("origine", "") or ""
    ).lower()
    if origine_attuale in ["", "report"]:
        evento_strutturato["origine"] = "scoperta"

    eventi_core = evento_strutturato.get("eventi_core", [])
    if not isinstance(eventi_core, list):
        eventi_core = []

    eventi_uniti = []
    for evento in eventi_core + eventi_sconosciuti:
        if evento in [None, False, "", [], {}]:
            continue

        if evento not in eventi_uniti:
            eventi_uniti.append(evento)

    evento_strutturato["eventi_core"] = eventi_uniti
    evento_strutturato["evento_composto"] = len(eventi_uniti) >= 2

    return evento_strutturato


def evento_strutturato_va_ricostruito(evento_strutturato, mondo):
    if not isinstance(evento_strutturato, dict):
        return True

    if not evento_strutturato:
        return True

    testo_originale = evento_strutturato.get("testo_originale")
    if testo_originale and mondo and testo_originale != mondo:
        return True

    categoria = str(evento_strutturato.get("categoria", "") or "").lower()
    tipo = str(evento_strutturato.get("tipo", "") or "").lower()
    eventi_core = evento_strutturato.get("eventi_core", [])

    if not isinstance(eventi_core, list):
        eventi_core = []

    return (
        categoria in ["", "neutra"]
        and tipo in ["", "generico", "neutra"]
        and len(eventi_core) == 0
    )


def evento_strutturato_puo_generare_da_ipotesi(evento_strutturato):
    if not isinstance(evento_strutturato, dict):
        return False

    if _evento_strutturato_supporto_non_generativo(evento_strutturato):
        return False

    categoria = str(
        evento_strutturato.get("categoria", "") or ""
    ).lower()
    if categoria in ["", "neutra", "ambiguita"]:
        return False

    eventi_core = evento_strutturato.get("eventi_core", [])
    if not isinstance(eventi_core, list):
        return False

    eventi_core = filtra_eventi_helper([
        e for e in eventi_core
        if e not in [None, False, "", [], {}]
    ])
    if len(eventi_core) == 0:
        return False

    ragionamento = evento_strutturato.get("ragionamento_unknown", {})
    if (
        isinstance(ragionamento, dict)
        and "evento" in ragionamento
        and ragionamento.get("evento") in [None, False, "", [], {}]
    ):
        return False

    return True


def salva_ipotesi_temporanea_da_decisione(stato_runtime, decisione):
    if stato_runtime is None or not isinstance(decisione, dict):
        return None

    ipotesi = decisione.get("ipotesi_temporanea")
    if not isinstance(ipotesi, dict):
        return None

    stato_runtime["ipotesi_temporanea"] = ipotesi

    recenti = stato_runtime.get("ipotesi_temporanee_recenti", [])
    if not isinstance(recenti, list):
        recenti = []

    recenti.append(ipotesi)
    stato_runtime["ipotesi_temporanee_recenti"] = recenti[-5:]

    return ipotesi


def archivia_ipotesi_strutturata(stato_runtime, esito, motivo=None):
    if stato_runtime is None:
        return None

    ipotesi = stato_runtime.get("ipotesi_temporanea")
    if not isinstance(ipotesi, dict):
        stato_runtime.pop("forza_generazione_da_ipotesi_strutturata", None)
        stato_runtime.pop("motivo_generazione_ipotesi_strutturata", None)
        return None

    archiviata = dict(ipotesi)
    archiviata["esito_finale"] = esito
    archiviata["motivo_finale"] = motivo
    archiviata["chiusa"] = True

    archivio = stato_runtime.get("ipotesi_strutturate_archiviate", [])
    if not isinstance(archivio, list):
        archivio = []

    archivio.append(archiviata)
    stato_runtime["ipotesi_strutturate_archiviate"] = archivio[-10:]

    stato_runtime.pop("ipotesi_temporanea", None)
    stato_runtime.pop("forza_generazione_da_ipotesi_strutturata", None)
    stato_runtime.pop("motivo_generazione_ipotesi_strutturata", None)

    return archiviata


def valuta_ipotesi_strutturata_sicura(stato_runtime, evento_strutturato, mondo):
    if stato_runtime is None:
        return None

    ipotesi = stato_runtime.get("ipotesi_temporanea")
    if not isinstance(ipotesi, dict):
        return None

    if valuta_ipotesi_da_evento_strutturato is None:
        return None

    try:
        valutazione = valuta_ipotesi_da_evento_strutturato(
            ipotesi,
            evento_strutturato,
            nuovo_mondo=mondo
        )
    except Exception as e:
        logger.warning(
            "[AUTONOMIA] Errore valutando ipotesi strutturata: {}".format(e)
        )
        return None

    if not isinstance(valutazione, dict):
        return None

    stato_runtime["valutazione_ipotesi_strutturata"] = valutazione

    ipotesi_aggiornata = valutazione.get("ipotesi")
    if isinstance(ipotesi_aggiornata, dict):
        stato_runtime["ipotesi_temporanea"] = ipotesi_aggiornata

    if valutazione.get("stato") in ["smentita", "scaduta"]:
        archivia_ipotesi_strutturata(
            stato_runtime,
            valutazione.get("stato"),
            valutazione.get("motivo")
        )
        return valutazione

    evento_generativo = evento_strutturato_puo_generare_da_ipotesi(
        evento_strutturato
    )

    if (
        valutazione.get("stato") == "confermata"
        and valutazione.get("genera_condizione") is True
        and evento_generativo
    ):
        stato_runtime["forza_generazione_da_ipotesi_strutturata"] = True
        stato_runtime["motivo_generazione_ipotesi_strutturata"] = (
            valutazione.get(
                "motivo",
                "ipotesi strutturata confermata"
            )
        )
    else:
        stato_runtime.pop("forza_generazione_da_ipotesi_strutturata", None)
        stato_runtime.pop("motivo_generazione_ipotesi_strutturata", None)

    return valutazione


def aggiorna_world_model_sicuro(mondo, firma, stato_runtime):
    if stato_runtime is None:
        stato_runtime = {}

    if aggiorna_world_model is None:
        return {
            "aggiornato": False,
            "motivo": "world model non disponibile"
        }

    try:
        esito = aggiorna_world_model(
            mondo,
            firma,
            stato_runtime
        )
        stato_runtime["world_model"] = esito
        return esito
    except Exception as e:
        logger.warning("[AUTONOMIA] Errore world model: {}".format(e))
        return {
            "aggiornato": False,
            "motivo": "errore world model"
        }


def costruisci_osservazione_mirata_sicura(
    mondo,
    azione_cognitiva=None,
    motivo=None,
    ipotesi=None,
    world_model=None,
    ragionamento=None,
    firma=None
):
    if costruisci_decisione_osservazione_mirata is None:
        return None

    try:
        return costruisci_decisione_osservazione_mirata(
            mondo=mondo,
            azione_cognitiva=azione_cognitiva,
            motivo=motivo,
            ipotesi=ipotesi,
            world_model=world_model,
            ragionamento=ragionamento,
            firma=firma
        )
    except Exception as e:
        logger.warning(
            "[AUTONOMIA] Errore osservazione mirata: {}".format(e)
        )
        return None


def valuta_osservazione_mirata_corrente_sicura(
    mondo,
    firma,
    stato_runtime,
    world_model=None
):
    if stato_runtime is None:
        return None

    piano = stato_runtime.get("osservazione_mirata_corrente")
    if not isinstance(piano, dict):
        return None

    if valuta_risposta_osservazione_mirata is None:
        return None

    try:
        esito = valuta_risposta_osservazione_mirata(
            mondo,
            piano,
            firma=firma,
            world_model=world_model
        )
    except Exception as e:
        logger.warning(
            "[AUTONOMIA] Errore valutando risposta osservazione mirata: {}".format(e)
        )
        return None

    if not isinstance(esito, dict):
        return None

    tentativi = int(piano.get("tentativi", 0)) + 1
    piano["tentativi"] = tentativi

    esito["tentativo"] = tentativi
    stato_runtime["esito_osservazione_mirata"] = esito
    aggiorna_ipotesi_da_osservazione_mirata_sicura(
        esito,
        stato_runtime
    )
    aggiorna_ipotesi_strutturata_da_osservazione_sicura(
        esito,
        stato_runtime,
        evento_strutturato=firma.get("evento_strutturato", {}),
        mondo=mondo
    )
    aggiorna_world_model_da_osservazione_mirata_sicura(
        esito,
        stato_runtime
    )
    aggiorna_azione_successiva_sicura(
        esito,
        stato_runtime
    )
    condizioni_aggiornate = registra_feedback_condizioni_sicuro(
        esito,
        stato_runtime
    )
    if condizioni_aggiornate:
        stato_runtime["condizioni_feedback_osservazione_mirata"] = (
            condizioni_aggiornate
        )

    storia = stato_runtime.get("esiti_osservazioni_mirate", [])
    if not isinstance(storia, list):
        storia = []

    storia.append(esito)
    stato_runtime["esiti_osservazioni_mirate"] = storia[-5:]

    if esito.get("trovato") or tentativi >= 3:
        piano["stato"] = "completata" if esito.get("trovato") else "scaduta"
        stato_runtime.pop("osservazione_mirata_corrente", None)
    else:
        stato_runtime["osservazione_mirata_corrente"] = piano

    logger.info(
        "[AUTONOMIA] Esito osservazione mirata: {}".format(esito)
    )

    return esito


def _numero_sicuro(valore, default=0.0):
    try:
        return float(valore)
    except Exception:
        return default


def aggiorna_ipotesi_strutturata_da_osservazione_sicura(
    esito,
    stato_runtime,
    evento_strutturato=None,
    mondo=None
):
    if not isinstance(stato_runtime, dict):
        return None

    if not isinstance(esito, dict):
        return None

    ipotesi = stato_runtime.get("ipotesi_temporanea")
    if not isinstance(ipotesi, dict):
        return None

    if evento_strutturato is None:
        evento_strutturato = stato_runtime.get("evento_strutturato", {})
    if not isinstance(evento_strutturato, dict):
        evento_strutturato = {}

    categoria_ipotesi = str(ipotesi.get("categoria", "") or "").lower()
    stato_ipotesi = str(ipotesi.get("stato", "") or "").lower()
    categoria_evento = str(
        evento_strutturato.get("categoria", "") or ""
    ).lower()
    stato_evento = str(evento_strutturato.get("stato", "") or "").lower()

    eventi_ipotesi = ipotesi.get("eventi_core", [])
    eventi_evento = evento_strutturato.get("eventi_core", [])
    if not isinstance(eventi_ipotesi, list):
        eventi_ipotesi = []
    if not isinstance(eventi_evento, list):
        eventi_evento = []

    eventi_ipotesi = filtra_eventi_helper(eventi_ipotesi)
    eventi_evento = filtra_eventi_helper(eventi_evento)

    stesso_evento = (
        categoria_ipotesi
        and categoria_ipotesi == categoria_evento
        and (
            not stato_ipotesi
            or not stato_evento
            or stato_ipotesi == stato_evento
        )
    )
    if not stesso_evento and eventi_ipotesi and eventi_evento:
        stesso_evento = bool(
            set([str(e) for e in eventi_ipotesi]).intersection(
                set([str(e) for e in eventi_evento])
            )
        )

    if not stesso_evento:
        return ipotesi

    tentativo_esito = int(esito.get("tentativo", 0) or 0)
    tentativi = max(int(ipotesi.get("tentativi", 0) or 0), tentativo_esito)
    tentativi += 1 if tentativi == 0 else 0

    aggiornata = dict(ipotesi)
    aggiornata["tentativi"] = tentativi
    aggiornata["ultimo_mondo"] = mondo or esito.get("mondo", "")
    aggiornata["ultima_categoria"] = categoria_evento
    aggiornata["ultimo_stato"] = stato_evento

    rilevanza = _numero_sicuro(evento_strutturato.get("rilevanza", 0.0))
    confidenza = _numero_sicuro(evento_strutturato.get("confidenza", 0.0))
    rilevante = rilevanza >= 0.6 or confidenza >= 0.6
    trovato = bool(esito.get("trovato"))

    if tentativi >= 2 or (trovato and rilevante):
        aggiornata["confermata"] = True
    else:
        aggiornata["confermata"] = bool(aggiornata.get("confermata", False))

    stato_runtime["ipotesi_temporanea"] = aggiornata

    if (
        aggiornata.get("confermata")
        and rilevante
        and evento_strutturato_puo_generare_da_ipotesi(evento_strutturato)
    ):
        stato_runtime["forza_generazione_da_ipotesi_strutturata"] = True
        stato_runtime["motivo_generazione_ipotesi_strutturata"] = (
            "ipotesi confermata da osservazione mirata"
        )
        stato_runtime.pop("_esito_ipotesi_temporanea", None)

    return aggiornata


def aggiorna_ipotesi_da_osservazione_mirata_sicura(esito, stato_runtime):
    if aggiorna_ipotesi_da_osservazione_mirata is None:
        return None

    try:
        return aggiorna_ipotesi_da_osservazione_mirata(
            esito,
            stato_runtime
        )
    except Exception as e:
        logger.warning(
            "[AUTONOMIA] Errore aggiornando ipotesi da osservazione: {}".format(e)
        )
        return None


def aggiorna_world_model_da_osservazione_mirata_sicura(esito, stato_runtime):
    if aggiorna_world_model_da_osservazione_mirata is None:
        return None

    try:
        return aggiorna_world_model_da_osservazione_mirata(
            esito,
            stato_runtime
        )
    except Exception as e:
        logger.warning(
            "[AUTONOMIA] Errore aggiornando world model da osservazione: {}".format(e)
        )
        return None


def aggiorna_azione_successiva_sicura(esito, stato_runtime):
    if aggiorna_azione_successiva_da_osservazione is None:
        return None

    try:
        return aggiorna_azione_successiva_da_osservazione(
            esito,
            stato_runtime
        )
    except Exception as e:
        logger.warning(
            "[AUTONOMIA] Errore aggiornando azione successiva: {}".format(e)
        )
        return None


def registra_feedback_condizioni_sicuro(esito, stato_runtime):
    if registra_feedback_osservazione_mirata is None:
        return []

    try:
        return registra_feedback_osservazione_mirata(
            esito,
            stato_runtime=stato_runtime
        )
    except Exception as e:
        logger.warning(
            "[AUTONOMIA] Errore aggiornando memoria condizioni da osservazione: {}".format(e)
        )
        return []


def valuta_goal_intent_sicuro(mondo, firma, stato_runtime, world_model=None):
    if valuta_goal_intent is None:
        return {
            "goal_attivo": False,
            "motivo": "goal intent memory non disponibile"
        }

    try:
        esito = valuta_goal_intent(
            mondo,
            firma=firma,
            stato_runtime=stato_runtime,
            world_model=world_model
        )

        if isinstance(esito, dict):
            stato_runtime["goal_intent"] = esito

        return esito
    except Exception as e:
        logger.warning(
            "[AUTONOMIA] Errore goal/intent reasoning: {}".format(e)
        )
        return {
            "goal_attivo": False,
            "motivo": "errore goal intent"
        }


def costruisci_decisione_goal_sicura(esito_goal):
    if costruisci_decisione_goal_intent is None:
        return None

    try:
        return costruisci_decisione_goal_intent(esito_goal)
    except Exception as e:
        logger.warning(
            "[AUTONOMIA] Errore decisione goal/intent: {}".format(e)
        )
        return None


def costruisci_decisione_azione_successiva_sicura(stato_runtime):
    if costruisci_decisione_azione_successiva is None:
        return None

    try:
        return costruisci_decisione_azione_successiva(stato_runtime)
    except Exception as e:
        logger.warning(
            "[AUTONOMIA] Errore costruendo azione successiva: {}".format(e)
        )
        return None


def _generatore_supporta_storia_episodica(funzione_generatore):
    try:
        if hasattr(inspect, "getfullargspec"):
            specifica = inspect.getfullargspec(funzione_generatore)
            argomenti = specifica.args
            keywords = specifica.varkw
        else:
            specifica = inspect.getargspec(funzione_generatore)
            argomenti = specifica.args
            keywords = specifica.keywords

        if "storia_episodica" in argomenti:
            return True
        if keywords is not None:
            return True
        return False
    except Exception:
        return True


def chiama_genera_condizione_autonoma_sicura(
    funzione_generatore,
    mondo,
    dati_memoria,
    stato_robot,
    chiave_privata,
    storia_episodica=None
):
    if _generatore_supporta_storia_episodica(funzione_generatore):
        return funzione_generatore(
            mondo,
            dati_memoria,
            stato_robot,
            chiave_privata,
            storia_episodica=storia_episodica
        )

    logger.warning(
        "[AUTONOMIA] Generator senza parametro storia_episodica: uso chiamata legacy"
    )
    return funzione_generatore(
        mondo,
        dati_memoria,
        stato_robot,
        chiave_privata
    )

def _testo_visibile_da_mondo(mondo):
    testo = _testo_sicuro(mondo)

    marker = "TESTO_VISIBILE:"
    if marker not in testo:
        return ""

    parte = testo.split(marker, 1)[1]

    if "SONO FERMO" in parte:
        parte = parte.split("SONO FERMO", 1)[0]

    return parte.strip()


def _testo_leggibile_da_mondo(mondo):
    testo_visibile = _testo_visibile_da_mondo(mondo)
    if testo_visibile:
        return testo_visibile

    testo = _testo_sicuro(mondo)
    testo_lower = testo.lower()

    indicatori = [
        "testo leggibile:",
        "testo:",
        "ocr:"
    ]

    for indicatore in indicatori:
        indice = testo_lower.find(indicatore)
        if indice < 0:
            continue

        parte = testo[indice + len(indicatore):]

        for fine in [". sono fermo", " sono fermo", ". sono", " sono"]:
            indice_fine = parte.lower().find(fine)
            if indice_fine >= 0:
                parte = parte[:indice_fine]
                break

        parte = parte.strip(" .,:;")
        if parte:
            return parte

    return ""


def _estratto_breve_testo_leggibile(testo):
    testo = _testo_sicuro(testo)
    parole = [
        p.strip(".,:;!?()[]{}\"'")
        for p in re.split(r"\s+", testo)
        if len(p.strip(".,:;!?()[]{}\"'")) >= 3
    ]

    parole_utili = []
    for parola in parole:
        parola_lower = parola.lower()
        if parola_lower in [
            "report",
            "vedo",
            "testo",
            "leggibile",
            "visibile",
            "sono",
            "fermo",
            "ocr"
        ]:
            continue

        parole_utili.append(parola)

        if len(parole_utili) >= 5:
            break

    return " ".join(parole_utili)


def _parole_significative_testo_operativo(testo):
    testo = _testo_sicuro(testo)
    parole = [
        p.strip(".,:;!?()[]{}\"'").lower()
        for p in re.split(r"\s+", testo)
        if len(p.strip(".,:;!?()[]{}\"'")) >= 3
    ]

    escluse = [
        "testo", "visibile", "leggibile", "report", "vedo", "sono", "fermo",
        "qui", "con", "per", "una", "uno", "del", "della", "delle", "dei",
        "gli", "alle", "nel", "nella", "nell", "ambiente", "campus"
    ]

    risultato = []
    for parola in parole:
        if parola in escluse:
            continue
        if parola not in risultato:
            risultato.append(parola)

    return risultato


def _materiale_operativo_da_testo(testo):
    testo = _testo_sicuro(testo).lower()
    materiali = [
        "carta",
        "vetro",
        "plastica",
        "organico",
        "metallo",
        "alluminio"
    ]

    for materiale in materiali:
        if materiale in testo:
            return materiale

    return ""


def _verbo_operativo_da_testo(testo):
    testo = _testo_sicuro(testo).lower()
    indicatori = [
        ("conferisci", "conferire"),
        ("conferire", "conferire"),
        ("raccolta", "raccogliere"),
        ("differenzia", "differenziare"),
        ("differenziata", "differenziare"),
        ("vietato", "rispettare un divieto"),
        ("obbligatorio", "rispettare un obbligo"),
        ("uscita", "seguire un percorso"),
        ("entrata", "seguire un accesso"),
        ("usare", "usare"),
        ("usa", "usare"),
        ("premere", "premere"),
        ("seguire", "seguire")
    ]

    for chiave, verbo in indicatori:
        if chiave in testo:
            return verbo

    return ""


def _lista_elementi_operativi(testo, materiale):
    parole = _parole_significative_testo_operativo(testo)
    parole_da_escludere = [
        materiale,
        "conferisci",
        "conferire",
        "raccolta",
        "differenzia",
        "differenziata",
        "vietato",
        "obbligatorio",
        "uscita",
        "entrata",
        "usare",
        "usa",
        "premere",
        "seguire",
        "unisambiente"
    ]

    elementi = []
    i = 0
    while i < len(parole):
        parola = parole[i]
        if parola in parole_da_escludere:
            i += 1
            continue

        elemento = parola
        if (
            i + 1 < len(parole)
            and parole[i + 1] in ["usati", "usate"]
            and parola in ["quaderni", "fogli", "buste", "sacchetti"]
        ):
            elemento = parola + " " + parole[i + 1]
            i += 1

        if elemento not in elementi:
            elementi.append(elemento)

        if len(elementi) >= 4:
            break

        i += 1

    return elementi


def _unisci_lista_naturale(elementi):
    elementi = [e for e in elementi if e]
    if not elementi:
        return ""
    if len(elementi) == 1:
        return elementi[0]
    if len(elementi) == 2:
        return elementi[0] + " e " + elementi[1]
    return ", ".join(elementi[:-1]) + " e " + elementi[-1]


def _sintesi_operativa_da_testo(
    testo_leggibile,
    indizi,
    descrizione_indizi
):
    testo = _testo_sicuro(testo_leggibile)
    if not testo:
        return "", ""

    materiale = _materiale_operativo_da_testo(testo)
    verbo = _verbo_operativo_da_testo(testo)
    if not materiale and not verbo:
        return "", ""

    elementi = _lista_elementi_operativi(testo, materiale)
    elenco = _unisci_lista_naturale(elementi)

    if "contenitore" in indizi and materiale:
        frase_osservazione = (
            "Vedo un contenitore per la raccolta della {}."
            .format(materiale)
        )
    elif "contenitore" in indizi:
        frase_osservazione = "Vedo un contenitore con indicazioni operative."
    elif descrizione_indizi:
        frase_osservazione = (
            "Vedo {} con indicazioni operative."
            .format(descrizione_indizi)
        )
    else:
        frase_osservazione = (
            "Vedo un supporto con indicazioni operative."
        )

    if verbo == "conferire" and elenco:
        frase_azione = (
            "Le scritte indicano di conferire qui materiali come {}."
            .format(elenco)
        )
    elif verbo == "conferire" and materiale:
        frase_azione = (
            "Le scritte indicano di conferire qui materiale come {}."
            .format(materiale)
        )
    elif verbo and elenco:
        frase_azione = (
            "Le scritte suggeriscono di {} materiali o elementi come {}."
            .format(verbo, elenco)
        )
    elif verbo:
        frase_azione = (
            "Le scritte sembrano indicare cosa fare qui: {}."
            .format(verbo)
        )
    elif materiale:
        frase_azione = (
            "Le scritte specificano una categoria utile: {}."
            .format(materiale)
        )
    else:
        frase_azione = "Le scritte sembrano indicare cosa fare qui."

    frase_utilita = (
        frase_azione +
        " Lo considero utile per capire la funzione di questo punto "
        "dell'ambiente."
    )

    return frase_osservazione, frase_utilita


def _eventi_core_da_evento(evento_strutturato):
    if not isinstance(evento_strutturato, dict):
        return []

    eventi_core = evento_strutturato.get("eventi_core", [])
    if not isinstance(eventi_core, list):
        return []

    return [
        str(e).lower().strip()
        for e in eventi_core
        if e not in [None, False, "", [], {}]
    ]


def _prima_conoscenza_semantica_utile(stato_runtime):
    if not isinstance(stato_runtime, dict):
        return {}

    conoscenze = stato_runtime.get("conoscenze_semantiche_attive", [])
    if not isinstance(conoscenze, list):
        return {}

    for conoscenza in conoscenze:
        if isinstance(conoscenza, dict):
            return conoscenza

    return {}


def _indizi_osservati_da_mondo(mondo):
    testo = _testo_sicuro(mondo).lower()
    ind_lav = "lava" + "gna"
    ind_car = "car" + "tello"
    ind_mon = "moni" + "tor"
    ind_por = "por" + "ta"
    ind_oro = "orolo" + "gio"
    catalogo = [
        (ind_lav, [ind_lav]),
        ("bacheca", ["bacheca"]),
        (ind_car, [ind_car, "segnale"]),
        ("foglio", ["foglio", "documento", "pagina"]),
        (ind_mon, [ind_mon, "schermo", "display"]),
        ("contenitore", ["contenitore", "cestino", "scatola"]),
        (ind_por, [ind_por]),
        ("corridoio", ["corridoio"]),
        ("tavolo", ["tavolo", "scrivania"]),
        ("sedie", ["sedie", "sedia"]),
        (ind_oro, [ind_oro]),
        ("zaino", ["zaino", "borsa"]),
        ("parete", ["parete", "muro"]),
        ("crepa", ["crepa", "rottura", "rotto", "rotta", "danneggiato"]),
        ("scritte", ["scritte", "scritta", "testo", "parole"]),
        ("passaggio", ["passaggio", "zona di passaggio", "transito"]),
        ("uscita", ["uscita"]),
        ("oggetto", ["oggetto", "elemento"])
    ]
    indizi = []

    for nome, parole in catalogo:
        for parola in parole:
            if parola in testo:
                indizi.append(nome)
                break

    risultato = []
    for indizio in indizi:
        if indizio not in risultato:
            risultato.append(indizio)

    return risultato


def _articolo_indizio(indizio):
    ind_lav = "lava" + "gna"
    ind_por = "por" + "ta"
    if indizio in [ind_lav, "bacheca", ind_por, "parete", "crepa"]:
        return "una " + indizio
    if indizio in ["sedie", "scritte"]:
        return indizio
    return "un " + indizio


def _descrivi_indizi_osservati(indizi):
    principali = [
        i for i in indizi
        if i not in ["scritte", "passaggio", "crepa"]
    ]
    dettagli = []

    if "scritte" in indizi:
        dettagli.append("scritte parzialmente leggibili")
    if "crepa" in indizi:
        dettagli.append("un segno di rottura")
    if "passaggio" in indizi and "oggetto" in indizi:
        dettagli.append("una posizione vicina a una zona di passaggio")

    if not principali and dettagli:
        return " ".join(dettagli)

    if not principali:
        return ""

    descrizioni = [_articolo_indizio(i) for i in principali[:3]]
    testo = descrizioni[0]

    if len(descrizioni) == 2:
        testo += " e " + descrizioni[1]
    elif len(descrizioni) >= 3:
        testo += ", " + descrizioni[1] + " e " + descrizioni[2]

    if dettagli:
        testo += " con " + " e ".join(dettagli[:2])

    return testo


def _inferenza_contesto_da_indizi(indizi, categoria, eventi_core, mondo):
    testo = _testo_sicuro(mondo).lower()
    ind_lav = "lava" + "gna"
    ind_car = "car" + "tello"
    ind_mon = "moni" + "tor"
    ind_por = "por" + "ta"
    ind_oro = "orolo" + "gio"

    if (
        ind_lav in indizi
        and (
            "scritte" in indizi
            or ind_oro in indizi
            or "sedie" in indizi
        )
    ):
        return (
            "Potrebbe indicare che mi trovo in un'aula o in uno spazio "
            "usato per comunicare informazioni."
        )

    if any(i in indizi for i in [ind_car, "foglio", ind_mon, "bacheca"]):
        return (
            "Potrebbe contenere indicazioni, regole o informazioni utili "
            "sul contesto."
        )

    if any(i in indizi for i in [ind_por, "uscita", "corridoio"]):
        return (
            "Potrebbe indicare un accesso, un percorso o un limite al "
            "movimento."
        )

    if "oggetto" in indizi and "passaggio" in indizi:
        return "Potrebbe ostacolare il movimento."

    if any(i in indizi for i in ["crepa", "parete"]) and (
        "rotto" in testo
        or "rotta" in testo
        or "crepa" in testo
        or "danneggiato" in testo
    ):
        return (
            "Potrebbe essere un dettaglio anomalo da ricordare o controllare."
        )

    if categoria == "informazione" or "contenuto_informativo_rilevante" in eventi_core:
        return (
            "Potrebbe aiutarmi a comprendere meglio il luogo in cui mi trovo."
        )

    return ""


def costruisci_sintesi_semantica_osservazione(mondo, stato_runtime):
    if not isinstance(stato_runtime, dict):
        stato_runtime = {}

    evento = stato_runtime.get("evento_strutturato", {})
    if not isinstance(evento, dict):
        evento = {}

    ragionamento = evento.get("ragionamento_unknown", {})
    if not isinstance(ragionamento, dict):
        ragionamento = {}

    categoria = str(evento.get("categoria", "") or "").lower()
    stato = str(evento.get("stato", "") or "").lower()
    tipo = str(evento.get("tipo", "") or "").lower()
    azione = str(evento.get("azione_cognitiva", "") or "").lower()
    eventi_core = _eventi_core_da_evento(evento)
    testo_leggibile = _testo_leggibile_da_mondo(mondo)
    estratto_testo = _estratto_breve_testo_leggibile(testo_leggibile)
    conoscenza = _prima_conoscenza_semantica_utile(stato_runtime)
    indizi = _indizi_osservati_da_mondo(mondo)
    descrizione_indizi = _descrivi_indizi_osservati(indizi)
    inferenza_indizi = _inferenza_contesto_da_indizi(
        indizi,
        categoria,
        eventi_core,
        mondo
    )
    frase_operativa, utilita_operativa = _sintesi_operativa_da_testo(
        testo_leggibile,
        indizi,
        descrizione_indizi
    )

    funzione = ""
    utilita = ""
    if isinstance(conoscenza, dict):
        funzione = _testo_sicuro(conoscenza.get("funzione_probabile", ""))
        utilita = _testo_sicuro(conoscenza.get("utilita_contestuale", ""))

    frase_osservazione = ""
    frase_utilita = ""

    informativo = (
        categoria in ["informazione", "supporto_informativo"]
        or tipo in [
            "informazione_operativa",
            "contenuto_informativo_rilevante",
            "supporto_informativo_potenziale",
            "dettaglio_funzionale_osservabile"
        ]
        or "informazione_operativa" in eventi_core
        or "contenuto_informativo_rilevante" in eventi_core
        or "supporto_informativo_potenziale" in eventi_core
        or "dettaglio_funzionale_osservabile" in eventi_core
    )

    accesso = (
        categoria == "accesso"
        or tipo in [
            "accesso_non_disponibile",
            "accesso_disponibile",
            "accesso_o_percorso_limitato"
        ]
        or "accesso_non_disponibile" in eventi_core
        or "accesso_disponibile" in eventi_core
        or "accesso_o_percorso_limitato" in eventi_core
    )

    ostacolo = (
        categoria == "ostacolo_spazio"
        or tipo == "oggetto_in_zona_rilevante"
        or "oggetto_in_zona_rilevante" in eventi_core
        or "ostacolo_frontale" in eventi_core
        or "ostacolo_destra" in eventi_core
        or "ostacolo_sinistra" in eventi_core
    )

    anomalia = (
        categoria == "anomalia"
        or tipo in ["elemento_ambientale_anomalo", "elemento_fuori_posto"]
        or "elemento_ambientale_anomalo" in eventi_core
        or "elemento_fuori_posto" in eventi_core
    )

    vincolo = (
        "vincolo_comportamentale" in eventi_core
        or _testo_contiene_termine_operativo(mondo)
    )

    informazione_non_disponibile = (
        categoria == "supporto_informativo"
        and (
            stato == "non_disponibile"
            or azione == "ignora"
            or "supporto_informativo_non_disponibile" in eventi_core
        )
    )

    if informazione_non_disponibile:
        if descrizione_indizi:
            frase_osservazione = (
                "Vedo {}, ma non leggo elementi utili."
                .format(descrizione_indizi)
            )
        else:
            frase_osservazione = (
                "Ho osservato un possibile supporto informativo, ma non leggo "
                "elementi utili."
            )
        frase_utilita = "Non lo uso per decidere ora."

    elif informativo and frase_operativa and utilita_operativa:
        frase_osservazione = frase_operativa
        frase_utilita = utilita_operativa

    elif descrizione_indizi and inferenza_indizi:
        frase_osservazione = "Vedo {}.".format(descrizione_indizi)
        if informativo and estratto_testo:
            frase_osservazione = (
                "Vedo {}. Leggo alcune parole: {}."
                .format(descrizione_indizi, estratto_testo)
            )

        if ostacolo:
            frase_utilita = (
                inferenza_indizi +
                " Lo considero rilevante per muovermi con prudenza."
            )
        elif anomalia:
            frase_utilita = (
                inferenza_indizi +
                " Lo considero utile per ricordare lo stato dell'ambiente."
            )
        else:
            frase_utilita = (
                inferenza_indizi +
                " Lo considero utile per capire il contesto."
            )

    elif (
        categoria == "supporto_informativo"
        and (
            stato == "potenziale"
            or azione == "osserva_meglio"
            or "supporto_informativo_potenziale" in eventi_core
        )
    ):
        frase_osservazione = (
            "Ho osservato un possibile supporto informativo, ma il contenuto "
            "non e' ancora chiaro."
        )
        frase_utilita = "Serve osservarlo meglio prima di usarlo."

    elif informativo:
        if estratto_testo:
            frase_osservazione = (
                "Ho osservato un supporto informativo con alcune parole "
                "leggibili: {}.".format(estratto_testo)
            )
        elif testo_leggibile:
            frase_osservazione = (
                "Ho osservato un supporto informativo con testo leggibile."
            )
        else:
            frase_osservazione = (
                "Ho osservato un supporto informativo nell'ambiente."
            )

        if vincolo or azione in ["osserva_e_memorizza", "usa_informazione"]:
            frase_utilita = (
                "Le interpreto come indicazioni utili per orientarmi o agire."
            )
        elif utilita:
            frase_utilita = "Sembra utile per {}.".format(utilita)
        elif funzione:
            frase_utilita = "Probabilmente serve a {}.".format(funzione)
        else:
            frase_utilita = (
                "Sembra utile per capire meglio questo luogo."
            )

    elif accesso:
        if stato in ["non_disponibile", "chiuso", "bloccato"]:
            frase_osservazione = (
                "Ho osservato un accesso chiuso o non disponibile."
            )
            frase_utilita = (
                "Potrebbe limitare il passaggio e influenzare dove posso andare."
            )
        else:
            frase_osservazione = (
                "Ho osservato un accesso o un passaggio rilevante."
            )
            frase_utilita = (
                "Mi aiuta a valutare come muovermi nello spazio."
            )

    elif ostacolo:
        frase_osservazione = (
            "Ho osservato un elemento vicino a una zona di passaggio."
        )
        frase_utilita = (
            "Potrebbe essere importante per muovermi con prudenza."
        )

    elif anomalia:
        frase_osservazione = (
            "Ho osservato un dettaglio anomalo nell'ambiente."
        )
        frase_utilita = (
            "Potrebbe essere utile ricordarlo o osservarlo con attenzione."
        )

    elif vincolo:
        frase_osservazione = (
            "Ho osservato un possibile vincolo o una regola nel contesto."
        )
        frase_utilita = (
            "Potrebbe aiutarmi a scegliere un comportamento piu' adatto."
        )

    else:
        ipotesi = _testo_sicuro(ragionamento.get("ipotesi", ""))
        if ipotesi:
            frase_osservazione = "Ho osservato un elemento significativo."
            frase_utilita = "Lo interpreto cosi': {}.".format(ipotesi)

    if not frase_osservazione:
        return ""

    frase = (frase_osservazione + " " + frase_utilita).strip()

    if isinstance(stato_runtime, dict):
        stato_runtime["sintesi_semantica_osservazione"] = frase

    return frase


def testo_visibile_puo_generare_significato_specifico(mondo):
    testo = _testo_visibile_da_mondo(mondo).lower()

    if not testo:
        return False

    parole = [
        p.strip()
        for p in re.split(r"\s+", testo)
        if len(p.strip()) >= 3
    ]

    indicatori_specifici = [
        "vietato", "non entrare", "chiuso", "chiusa",
        "aperto", "aperta", "uscita", "entrata",
        "orario", "istruzioni", "premere", "usare",
        "attenzione", "pericolo", "obbligatorio",
        "riservato", "accesso", "laboratorio",
        "errore", "warning", "emergenza"
    ]

    if any(indicatore in testo for indicatore in indicatori_specifici):
        return True

    # Nuova regola generalista:
    # se c'e' testo visibile con piu' parole significative,
    # la condizione generale non deve chiudere subito.
    if len(parole) >= 3:
        return True

    return False

def evento_generale_informativo_con_testo_specifico(stato_runtime, mondo):
    if not isinstance(stato_runtime, dict):
        return False

    evento = stato_runtime.get("evento_strutturato", {})
    if not isinstance(evento, dict):
        evento = {}

    eventi_core = evento.get("eventi_core", [])
    if not isinstance(eventi_core, list):
        eventi_core = []

    return (
        "contenuto_informativo_rilevante" in eventi_core
        and testo_visibile_puo_generare_significato_specifico(mondo)
    )

def salva_conoscenza_semantica_da_evento(mondo, stato_runtime, firma=None):
    if (
        costruisci_ipotesi_multiple_da_evento is None
        and costruisci_ipotesi_da_evento is None
    ):
        return None

    if salva_ipotesi_semantica is None:
        return None

    if not isinstance(stato_runtime, dict):
        return None

    eventi = {}

    if isinstance(firma, dict):
        sorgenti = [
            firma.get("eventi_attivi", {}),
            firma.get("eventi", {})
        ]
    else:
        sorgenti = []

    sorgenti.extend([
        stato_runtime.get("eventi", {}),
        stato_runtime.get("eventi_reali", {})
    ])

    evento_strutturato = stato_runtime.get("evento_strutturato", {})
    if isinstance(evento_strutturato, dict):
        for ev in evento_strutturato.get("eventi_core", []):
            eventi[ev] = True

    for sorgente in sorgenti:
        if not isinstance(sorgente, dict):
            continue

        for nome, valore in sorgente.items():
            if valore not in [False, None, "", [], {}]:
                eventi[nome] = True

    eventi_utili = [
        "contenuto_informativo_rilevante",
        "informazione_operativa",
        "supporto_informativo_potenziale",
        "dettaglio_funzionale_osservabile"
    ]

    salvate = []
    gia_viste = {}

    for evento in eventi_utili:
        if not eventi.get(evento):
            continue

        if costruisci_ipotesi_multiple_da_evento is not None:
            ipotesi_evento = costruisci_ipotesi_multiple_da_evento(
                evento,
                mondo
            )
        else:
            ipotesi = costruisci_ipotesi_da_evento(evento, mondo)
            ipotesi_evento = [ipotesi] if isinstance(ipotesi, dict) else []

        if not isinstance(ipotesi_evento, list):
            continue

        for ipotesi in ipotesi_evento:
            if not isinstance(ipotesi, dict):
                continue

            chiave = (
                str(ipotesi.get("concetto", "")),
                "|".join([
                    str(e)
                    for e in ipotesi.get("evidenze", [])
                    if e not in [None, False, "", [], {}]
                ])
            )
            if chiave in gia_viste:
                continue
            gia_viste[chiave] = True

            voce = salva_ipotesi_semantica(ipotesi, mondo)
            if isinstance(voce, dict):
                salvate.append(voce)

    if salvate:
        stato_runtime["conoscenze_semantiche_salvate"] = salvate[-5:]
        stato_runtime["conoscenze_semantiche_attive"] = salvate[-5:]
        costruisci_sintesi_semantica_osservazione(mondo, stato_runtime)
        logger.info(
            "[AUTONOMIA][KNOWLEDGE] Ipotesi semantiche salvate: {}".format(
                [
                    (
                        v.get("concetto"),
                        v.get("fiducia"),
                        v.get("firma")
                    )
                    for v in salvate
                ]
            )
        )

        if aggiorna_ipotesi_da_osservazione is not None:
            try:
                evento_aggiornamento = None
                for evento in eventi_utili:
                    if eventi.get(evento):
                        evento_aggiornamento = evento
                        break

                esito = aggiorna_ipotesi_da_osservazione(
                    mondo,
                    evento=evento_aggiornamento
                )
                stato_runtime["aggiornamento_conoscenza_semantica"] = esito
            except Exception as e:
                stato_runtime["aggiornamento_conoscenza_semantica"] = {
                    "errore": str(e)
                }
                logger.warning(
                    "[AUTONOMIA][KNOWLEDGE] Aggiornamento semantico "
                    "saltato: {}".format(e)
                )

    return salvate


def recupera_conoscenze_semantiche_attive(mondo, stato_runtime, firma=None):
    if recupera_conoscenze_stabili_rilevanti is None:
        return []

    if not isinstance(stato_runtime, dict):
        return []

    eventi = {}
    sorgenti = []

    if isinstance(firma, dict):
        sorgenti.extend([
            firma.get("eventi_attivi", {}),
            firma.get("eventi", {})
        ])

    sorgenti.extend([
        stato_runtime.get("eventi", {}),
        stato_runtime.get("eventi_reali", {})
    ])

    evento_strutturato = stato_runtime.get("evento_strutturato", {})
    if isinstance(evento_strutturato, dict):
        for ev in evento_strutturato.get("eventi_core", []):
            eventi[ev] = True

    for sorgente in sorgenti:
        if not isinstance(sorgente, dict):
            continue

        for nome, valore in sorgente.items():
            if valore not in [False, None, "", [], {}]:
                eventi[nome] = True

    evento_ricerca = None
    for evento in [
        "contenuto_informativo_rilevante",
        "informazione_operativa",
        "supporto_informativo_potenziale",
        "dettaglio_funzionale_osservabile"
    ]:
        if eventi.get(evento):
            evento_ricerca = evento
            break

    try:
        conoscenze = recupera_conoscenze_stabili_rilevanti(
            mondo,
            evento=evento_ricerca
        )
        stato_runtime["conoscenze_semantiche_attive"] = conoscenze
        return conoscenze
    except Exception as e:
        stato_runtime["conoscenze_semantiche_attive"] = []
        stato_runtime["errore_conoscenze_semantiche_attive"] = str(e)
        logger.warning(
            "[AUTONOMIA][KNOWLEDGE] Recupero conoscenze stabili saltato: "
            "{}".format(e)
        )
        return []


def gestisci_autonomia(mondo, stato_runtime=None):
    """
    Punto unico di ingresso per l'autonomia.

    Input:
        mondo: stringa/report sensoriale prodotto da soul.py
        stato_runtime: dizionario opzionale con dati aggiuntivi

    Output:
        dizionario decisione oppure None
    """

    if stato_runtime is None:
        stato_runtime = {}

    logger.info("[AUTONOMIA] Supervisore attivo")
    _diag_pipeline("gestisci_autonomia.input_mondo", mondo)
    _diag_pipeline(
        "gestisci_autonomia.runtime_evento_strutturato_pre",
        stato_runtime.get("evento_strutturato", {})
    )

    try:
        evento_strutturato = stato_runtime.get("evento_strutturato", {})
        if (
            costruisci_evento_strutturato_layer is not None
            and evento_strutturato_va_ricostruito(
                evento_strutturato,
                mondo
            )
        ):
            evento_strutturato = costruisci_evento_strutturato_layer(
                mondo,
                stato_runtime
            )
            stato_runtime["evento_strutturato"] = evento_strutturato
        _diag_pipeline(
            "gestisci_autonomia.runtime_evento_strutturato_post",
            stato_runtime.get("evento_strutturato", {})
        )

    except Exception as e:
        logger.warning(
            "[AUTONOMIA] Errore costruendo evento strutturato: {}".format(e)
        )

    if stato_runtime.get("usa_agentic_orchestrator", False):
        if esegui_ciclo_agentico is not None:
            logger.info("[AUTONOMIA] Uso orchestratore agentico")

            return esegui_ciclo_agentico(
                mondo,
                stato_runtime,
                costruisci_firma_situazione,
                valuta_condizioni_generate_sicure,
                situazione_merita_generazione,
                prova_generazione_autonoma,
                costruisci_decisione_curiosa,
                _pulisci_mondo_per_unknown
            )

    firma = costruisci_firma_situazione(mondo, stato_runtime)
    esito_world_model = aggiorna_world_model_sicuro(
        mondo,
        firma,
        stato_runtime
    )
    valuta_osservazione_mirata_corrente_sicura(
        mondo,
        firma,
        stato_runtime,
        world_model=esito_world_model
    )

    try:
        stato_runtime["eventi"] = firma.get("eventi", {})
        stato_runtime["eventi_reali"] = firma.get("eventi_attivi", {})

        eventi_descritti = firma.get("eventi_descritti", {})
        eventi_sconosciuti = [
            nome
            for nome, dati in eventi_descritti.items()
            if not dati.get("conosciuto", True)
            and nome not in EVENTI_SUPPORTO_INFORMATIVO_NON_GENERATIVI
        ]

        eventi_sconosciuti = filtra_eventi_helper(eventi_sconosciuti)

        if eventi_sconosciuti:
            stato_runtime["evento_strutturato"] = (
                integra_eventi_sconosciuti_in_evento_strutturato(
                    stato_runtime.get("evento_strutturato", {}),
                    eventi_sconosciuti
                )
            )

    except Exception as e:
        logger.warning(
            "[AUTONOMIA] Errore propagando firma nel runtime: {}".format(e)
        )

    logger.info(
        "[AUTONOMIA] Firma situazione: {}".format(
            _maschera_dati_sensibili(firma)
        )
    )

    recupera_conoscenze_semantiche_attive(
        mondo,
        stato_runtime,
        firma=firma
    )

    try:
        salva_conoscenza_semantica_da_evento(
            mondo,
            stato_runtime,
            firma=firma
        )
    except Exception as e:
        logger.warning(
            "[AUTONOMIA][KNOWLEDGE] Errore salvando conoscenza semantica: {}".format(e)
        )

    if "eventi" not in stato_runtime:
        stato_runtime["eventi"] = firma.get("eventi", {})

    if "eventi_reali" not in stato_runtime:
        stato_runtime["eventi_reali"] = firma.get("eventi_attivi", {})

    # EVENTI UNKNOWN:
    # propago TUTTI gli eventi attivi della firma dentro stato_runtime["eventi"],
    # inclusi quelli scoperti autonomamente.
    try:
        stato_runtime.setdefault("eventi", {})

        eventi_attivi_firma = firma.get("eventi_attivi", {})

        if isinstance(eventi_attivi_firma, dict):
            for nome_evento, valore in eventi_attivi_firma.items():
                if valore not in [False, None, "", [], {}]:
                    stato_runtime["eventi"][nome_evento] = True

        _sanitizza_eventi_supporto_informativo(stato_runtime.get("eventi", {}))
        _sanitizza_eventi_supporto_informativo(
            stato_runtime.get("eventi_reali", {})
        )

    except Exception as e:
        logger.warning(
            "[AUTONOMIA] Errore propagando eventi_attivi nel runtime: {}".format(e)
        )

    if situazione_fallback_visivo_neutra(
        mondo,
        stato_runtime.get("evento_strutturato", {})
    ):
        chiudi_generazione_non_permessa(
            stato_runtime,
            "fallback visivo generico neutro"
        )
        logger.info(
            "[AUTONOMIA] Fallback visivo neutro: nessuna generazione"
        )
        return None

    if evento_strutturato_da_chiudere_senza_decisione(
        stato_runtime.get("evento_strutturato", {})
    ):
        chiudi_generazione_non_permessa(
            stato_runtime,
            "evento strutturato non generativo"
        )
        logger.info(
            "[AUTONOMIA] Evento strutturato non generativo: nessuna generazione"
        )
        return None

    if scena_operativa_gia_compresa(stato_runtime, mondo):
        logger.info(
            "[AUTONOMIA] Scena informativa gia' compresa: evito nuova curiosita'"
        )
        costruisci_sintesi_semantica_osservazione(mondo, stato_runtime)
        stato_runtime["decisione_non_generativa"] = (
            "informazione_operativa_gia_compresa"
        )
        return None

    valutazione_ipotesi_strutturata = valuta_ipotesi_strutturata_sicura(
        stato_runtime,
        stato_runtime.get("evento_strutturato", {}),
        mondo
    )

    if (
        stato_runtime.get("forza_generazione_da_ipotesi_strutturata", False)
        and not evento_strutturato_puo_generare_da_ipotesi(
            stato_runtime.get("evento_strutturato", {})
        )
    ):
        stato_runtime.pop("forza_generazione_da_ipotesi_strutturata", None)
        stato_runtime.pop("motivo_generazione_ipotesi_strutturata", None)

    if stato_runtime.get("forza_generazione_da_ipotesi_strutturata", False):
        motivo_ipotesi_strutturata = stato_runtime.get(
            "motivo_generazione_ipotesi_strutturata",
            "ipotesi strutturata confermata"
        )
        gia_coperta_ipotesi, motivo_coperta_ipotesi, _ = (
            _generazione_gia_coperta_da_memoria(
                mondo,
                firma,
                stato_runtime
            )
        )

        if gia_coperta_ipotesi:
            costruisci_sintesi_semantica_osservazione(mondo, stato_runtime)
            stato_runtime["decisione_non_generativa"] = motivo_coperta_ipotesi
            stato_runtime.pop("forza_generazione_da_ipotesi_strutturata", None)
            stato_runtime.pop("motivo_generazione_ipotesi_strutturata", None)
            archivia_ipotesi_strutturata(
                stato_runtime,
                "gia_coperta",
                motivo_coperta_ipotesi
            )
            nuova_decisione = None
        else:
            nuova_decisione = prova_generazione_autonoma(
                mondo,
                stato_runtime,
                motivo_ipotesi_strutturata
            )
            archivia_ipotesi_strutturata(
                stato_runtime,
                (
                    "generata"
                    if nuova_decisione is not None
                    else "generazione_fallita"
                ),
                motivo_ipotesi_strutturata
            )

        if nuova_decisione is not None:
            logger.info(
                "[AUTONOMIA] Decisione ottenuta da ipotesi strutturata"
            )
            return nuova_decisione

    if (
        osservazioni_mirate_per_scena(stato_runtime, mondo, firma=firma) >= 1
        and evento_rilevante_per_generazione_dopo_osservazione(
            stato_runtime,
            firma=firma
        )
    ):
        gia_coperta_osservazione, motivo_coperta_osservazione, _ = (
            _generazione_gia_coperta_da_memoria(
                mondo,
                firma,
                stato_runtime
            )
        )

        if gia_coperta_osservazione:
            costruisci_sintesi_semantica_osservazione(mondo, stato_runtime)
            stato_runtime["decisione_non_generativa"] = (
                motivo_coperta_osservazione
            )
        else:
            motivo_osservazione = stato_runtime.get(
                "motivo_generazione_dopo_osservazione_mirata",
                "osservazione mirata gia' eseguita per la scena"
            )
            nuova_decisione = prova_generazione_autonoma(
                mondo,
                stato_runtime,
                motivo_osservazione
            )

            if nuova_decisione is not None:
                logger.info(
                    "[AUTONOMIA] Decisione ottenuta dopo osservazione mirata"
                )
                return nuova_decisione

    try:
        valutazione_strutturata = stato_runtime.get(
            "valutazione_ipotesi_strutturata",
            {}
        )
        if not isinstance(valutazione_strutturata, dict):
            valutazione_strutturata = {}

        if (
            decidi_da_evento_strutturato is not None
            and not stato_runtime.get(
                "forza_generazione_da_ipotesi_strutturata",
                False
            )
            and valutazione_strutturata.get("stato") not in [
                "confermata",
                "smentita",
                "scaduta"
            ]
        ):
            decisione_evento_strutturato = (
                decidi_da_evento_strutturato(
                    stato_runtime.get("evento_strutturato", {}),
                    mondo=mondo,
                    stato_runtime=stato_runtime
                )
            )

            if decisione_evento_strutturato is not None:
                logger.info("[AUTONOMIA] Decisione da evento strutturato")
                costruisci_sintesi_semantica_osservazione(
                    mondo,
                    stato_runtime
                )
                salva_ipotesi_temporanea_da_decisione(
                    stato_runtime,
                    decisione_evento_strutturato
                )
                return filtra_curiosita_ripetuta(
                    registra_osservazione_mirata_per_scena(
                        stato_runtime,
                        decisione_evento_strutturato,
                        mondo,
                        firma=firma
                    ),
                    stato_runtime,
                    mondo,
                    firma,
                    "evento_strutturato"
                )

    except Exception as e:
        logger.warning(
            "[AUTONOMIA] Errore policy evento strutturato: {}".format(e)
        )

    decisione_azione_successiva = (
        costruisci_decisione_azione_successiva_sicura(
            stato_runtime
        )
    )

    if decisione_azione_successiva is not None:
        logger.info("[AUTONOMIA] Decisione da azione successiva suggerita")
        return filtra_curiosita_ripetuta(
            registra_osservazione_mirata_per_scena(
                stato_runtime,
                decisione_azione_successiva,
                mondo,
                firma=firma
            ),
            stato_runtime,
            mondo,
            firma,
            "azione_successiva"
        )

    esito_goal = valuta_goal_intent_sicuro(
        mondo,
        firma,
        stato_runtime,
        world_model=esito_world_model
    )
    decisione_goal = costruisci_decisione_goal_sicura(esito_goal)

    if decisione_goal is not None:
        logger.info("[AUTONOMIA] Decisione da goal/intent reasoning")
        registra_revisione_piano_corrente(
            stato_runtime,
            decisione_goal
        )
        return filtra_curiosita_ripetuta(
            registra_osservazione_mirata_per_scena(
                stato_runtime,
                decisione_goal,
                mondo,
                firma=firma
            ),
            stato_runtime,
            mondo,
            firma,
            "goal_intent"
        )

    if stato_runtime.get("forza_generazione_safety", False):
        motivo_safety = stato_runtime.get(
            "motivo_safety",
            "evento safety prioritario"
        )

        logger.warning("[AUTONOMIA] Generazione safety richiesta: {}".format(
            motivo_safety
        ))

        nuova_decisione = prova_generazione_autonoma(
            mondo,
            stato_runtime,
            "safety: {}".format(motivo_safety)
        )

        if nuova_decisione is not None:
            logger.info("[AUTONOMIA] Decisione ottenuta dopo generazione safety")
            return nuova_decisione

        logger.info("[AUTONOMIA] Generazione safety non riuscita: provo condizioni esistenti")

        decisione = valuta_condizioni_generate_sicure(mondo, stato_runtime)

        if decisione is not None:
            if evento_generale_informativo_con_testo_specifico(stato_runtime, mondo):
                logger.info(
                    "[AUTONOMIA] Condizione informativa generale non conclusiva: "
                    "testo visibile potenzialmente specifico"
                )
                stato_runtime["condizione_generale_non_conclusiva"] = True
                stato_runtime["motivo_condizione_generale_non_conclusiva"] = (
                    "testo_visibile_specifico"
                )
            else:
                logger.info("[AUTONOMIA] Decisione ottenuta da condizione generata")
                return rafforza_decisione_informazione_operativa(
                    decisione,
                    stato_runtime,
                    mondo
                )

        return None

    eventi_reali = stato_runtime.get("eventi_reali", {})
    eventi_attivi = list(firma.get("eventi_attivi", {}).keys())

    eventi_reali_generativi = [
        k for k, v in eventi_reali.items()
        if v not in [False, None, "", [], {}]
        and str(k).lower().strip() != "interazione_utente"
    ]

    numero_eventi_reali = len(eventi_reali_generativi)

    eventi_attivi_generativi = [
        e for e in eventi_attivi
        if str(e).lower().strip() != "interazione_utente"
    ]

    evento_composto = (
        len(eventi_attivi_generativi) >= 2
    )

    # CASO SPECIALE:
    # se la situazione e' composta, proviamo prima a generare/imparare
    # la condizione composta. Altrimenti una condizione semplice gia'
    # esistente potrebbe intercettare l'evento e impedire l'apprendimento.
    if evento_composto:
        logger.info("[AUTONOMIA] Evento composto: priorita' alla generazione autonoma")

        esito_ipotesi = valuta_ipotesi_temporanee_sicura(
            mondo,
            firma,
            stato_runtime
        )

        if esito_ipotesi.get("ha_ipotesi") and not esito_ipotesi.get("genera_condizione"):
            decisione_ipotesi = None

            decisione_mirata = costruisci_osservazione_mirata_sicura(
                mondo,
                azione_cognitiva=esito_ipotesi.get("azione_temporanea"),
                motivo=esito_ipotesi.get("motivo"),
                ipotesi=esito_ipotesi.get("ipotesi"),
                world_model=esito_world_model,
                firma=firma
            )

            if decisione_mirata is not None:
                logger.info(
                    "[AUTONOMIA] Decisione da osservazione mirata composta"
                )
                return registra_osservazione_mirata_per_scena(
                    stato_runtime,
                    decisione_mirata,
                    mondo,
                    firma=firma
                )

            if costruisci_decisione_ipotesi is not None:
                decisione_ipotesi = costruisci_decisione_ipotesi(esito_ipotesi)

            if decisione_ipotesi is not None:
                logger.info("[AUTONOMIA] Decisione da ipotesi temporanea composta")
                return decisione_ipotesi

        deve_generare, motivo = situazione_merita_generazione(mondo, stato_runtime)

        if esito_ipotesi.get("genera_condizione"):
            gia_coperta_ipotesi, motivo_coperta_ipotesi, _ = (
                _generazione_gia_coperta_da_memoria(
                    mondo,
                    firma,
                    stato_runtime
                )
            )
            if gia_coperta_ipotesi:
                deve_generare = False
                motivo = motivo_coperta_ipotesi
                costruisci_sintesi_semantica_osservazione(
                    mondo,
                    stato_runtime
                )
                stato_runtime["decisione_non_generativa"] = (
                    motivo_coperta_ipotesi
                )
            else:
                deve_generare = True
                motivo = esito_ipotesi.get(
                    "motivo",
                    "ipotesi temporanea confermata"
                )

        logger.info("[AUTONOMIA] Valutazione generazione autonoma: {} - {}".format(
            deve_generare,
            motivo
        ))

        if deve_generare:
            generazione_da_ipotesi_strutturata = stato_runtime.get(
                "forza_generazione_da_ipotesi_strutturata",
                False
            )
            nuova_decisione = prova_generazione_autonoma(
                mondo,
                stato_runtime,
                "evento composto prioritario: {}".format(motivo)
            )

            if generazione_da_ipotesi_strutturata:
                archivia_ipotesi_strutturata(
                    stato_runtime,
                    "generata" if nuova_decisione is not None else "generazione_fallita",
                    motivo
                )

            if nuova_decisione is not None:
                logger.info("[AUTONOMIA] Decisione ottenuta dopo generazione autonoma composta")
                return nuova_decisione

        logger.info("[AUTONOMIA] Generazione composta non riuscita: provo condizioni esistenti")

        decisione = valuta_condizioni_generate_sicure(mondo, stato_runtime)

        if decisione is not None:
            logger.info("[AUTONOMIA] Decisione ottenuta da condizione generata esistente")
            return rafforza_decisione_informazione_operativa(
                decisione,
                stato_runtime,
                mondo
            )

        return None

    decisione = valuta_condizioni_generate_sicure(mondo, stato_runtime)

    if decisione is not None:
        if evento_generale_informativo_con_testo_specifico(stato_runtime, mondo):
            logger.info(
                "[AUTONOMIA] Condizione informativa generale non conclusiva: "
                "testo visibile potenzialmente specifico"
            )
            stato_runtime["condizione_generale_non_conclusiva"] = True
            stato_runtime["motivo_condizione_generale_non_conclusiva"] = (
                "testo_visibile_specifico"
            )
        else:
            logger.info("[AUTONOMIA] Decisione ottenuta da condizione generata")
            return rafforza_decisione_informazione_operativa(
                decisione,
                stato_runtime,
                mondo
            )
        
    logger.info("[AUTONOMIA] Nessuna condizione autonoma applicabile")

    esito_ipotesi = valuta_ipotesi_temporanee_sicura(
        mondo,
        firma,
        stato_runtime
    )

    if esito_ipotesi.get("ha_ipotesi") and not esito_ipotesi.get("genera_condizione"):
        decisione_ipotesi = None
        ipotesi_runtime = stato_runtime.get("ipotesi_temporanea", {})
        ipotesi_runtime_confermata = (
            isinstance(ipotesi_runtime, dict)
            and ipotesi_runtime.get("confermata")
        )

        if (
            esito_world_model.get("familiare")
            and not esito_world_model.get("anomalia")
            and not stato_runtime.get("forza_generazione_da_ipotesi_strutturata", False)
            and not ipotesi_runtime_confermata
            and costruisci_decisione_world_model is not None
        ):
            decisione_world = costruisci_decisione_world_model(
                esito_world_model
            )

            if decisione_world is not None:
                logger.info("[AUTONOMIA] Decisione da world model stabile")
                return decisione_world

        decisione_mirata = costruisci_osservazione_mirata_sicura(
            mondo,
            azione_cognitiva=esito_ipotesi.get("azione_temporanea"),
            motivo=esito_ipotesi.get("motivo"),
            ipotesi=esito_ipotesi.get("ipotesi"),
            world_model=esito_world_model,
            firma=firma
        )

        if decisione_mirata is not None:
            logger.info("[AUTONOMIA] Decisione da osservazione mirata")
            return filtra_curiosita_ripetuta(
                registra_osservazione_mirata_per_scena(
                    stato_runtime,
                    decisione_mirata,
                    mondo,
                    firma=firma
                ),
                stato_runtime,
                mondo,
                firma,
                "osservazione_mirata"
            )

        if costruisci_decisione_ipotesi is not None:
            decisione_ipotesi = costruisci_decisione_ipotesi(esito_ipotesi)

        if decisione_ipotesi is not None:
            logger.info("[AUTONOMIA] Decisione da ipotesi temporanea")
            return decisione_ipotesi
    
    # Curiosità epistemica:
    # se non ci sono condizioni attive e la scena non merita ancora
    # una condizione permanente, NAO può decidere di osservare meglio.
    try:
        if costruisci_decisione_curiosa is not None:

            mondo_unknown = _pulisci_mondo_per_unknown(
                mondo
            )

            logger.info(
                u"[AUTONOMIA][UNKNOWN] mondo_unknown={}".format(
                    mondo_unknown
                )
            )

            decisione_curiosa = (
                costruisci_decisione_curiosa(
                    mondo_unknown
                )
            )

            logger.info(
                u"[AUTONOMIA][UNKNOWN] decisione_curiosa={}".format(
                    decisione_curiosa
                )
            )

            # Politica: osserva con prudenza
            try:
                from behaviors.event_system.unknown_situation_reasoner import (
                    ragiona_situazione_sconosciuta
                )

                ragionamento = ragiona_situazione_sconosciuta(
                    mondo_unknown
                )

                decisione_mirata = None
                if ragionamento is not None:
                    decisione_mirata = costruisci_osservazione_mirata_sicura(
                        mondo,
                        azione_cognitiva=ragionamento.get("azione_cognitiva"),
                        motivo=ragionamento.get("ipotesi"),
                        world_model=esito_world_model,
                        ragionamento=ragionamento,
                        firma=firma
                    )

                if decisione_mirata is not None:
                    logger.info(
                        "[AUTONOMIA] Decisione curiosa da osservazione mirata"
                    )
                    return filtra_curiosita_ripetuta(
                        registra_osservazione_mirata_per_scena(
                            stato_runtime,
                            decisione_mirata,
                            mondo,
                            firma=firma
                        ),
                        stato_runtime,
                        mondo,
                        firma,
                        "curiosita_osservazione_mirata"
                    )

                if (
                    ragionamento is not None
                    and ragionamento.get("azione_cognitiva")
                    == "osserva_con_prudenza"
                ):
                    return filtra_curiosita_ripetuta({
                        "stato_interno": "prudente",
                        "obiettivo":
                            "valutare un elemento vicino a una zona rilevante",
                        "azioni": [
                            {
                                "tipo": "occhi",
                                "colore": "yellow"
                            },
                            {
                                "tipo": "guarda",
                                "x": 0.0,
                                "y": -0.25
                            },
                            {
                                "tipo": "parla",
                                "testo": (
                                    "Ho notato qualcosa vicino "
                                    "a una zona importante. "
                                    "Lo osservo con prudenza "
                                    "prima di decidere."
                                )
                            }
                        ],
                        "memoria": [
                            {
                                "tipo": "politica_agentica",
                                "azione":
                                    "osserva_con_prudenza",
                                "motivo":
                                    ragionamento.get(
                                        "ipotesi",
                                        "elemento vicino "
                                        "a una zona rilevante"
                                )
                            }
                        ]
                    }, stato_runtime, mondo, firma, "osserva_con_prudenza")

            except Exception as e:
                logger.warning(
                    "[AUTONOMIA] Errore politica prudenza: {}".format(e)
                )

            if decisione_curiosa is not None:
                logger.info(
                    "[AUTONOMIA] Decisione curiosa autonoma senza generare condizione"
                )
                return filtra_curiosita_ripetuta(
                    decisione_curiosa,
                    stato_runtime,
                    mondo,
                    firma,
                    "curiosita_autonoma"
                )

    except Exception as e:
        logger.warning(
            "[AUTONOMIA] Errore curiosita epistemica: {}".format(
                e
            )
        )

    deve_generare, motivo = situazione_merita_generazione(
        mondo,
        stato_runtime
    )

    if esito_ipotesi.get("genera_condizione"):
        gia_coperta_ipotesi, motivo_coperta_ipotesi, _ = (
            _generazione_gia_coperta_da_memoria(
                mondo,
                firma,
                stato_runtime
            )
        )
        if gia_coperta_ipotesi:
            deve_generare = False
            motivo = motivo_coperta_ipotesi
            costruisci_sintesi_semantica_osservazione(
                mondo,
                stato_runtime
            )
            stato_runtime["decisione_non_generativa"] = (
                motivo_coperta_ipotesi
            )
        else:
            deve_generare = True
            motivo = esito_ipotesi.get(
                "motivo",
                "ipotesi temporanea confermata"
            )

    logger.info(
        "[AUTONOMIA] Valutazione generazione autonoma: {} - {}".format(
            deve_generare,
            motivo
        )
    )

    if deve_generare:
        generazione_da_ipotesi_strutturata = stato_runtime.get(
            "forza_generazione_da_ipotesi_strutturata",
            False
        )
        nuova_decisione = prova_generazione_autonoma(mondo, stato_runtime, motivo)

        if generazione_da_ipotesi_strutturata:
            archivia_ipotesi_strutturata(
                stato_runtime,
                "generata" if nuova_decisione is not None else "generazione_fallita",
                motivo
            )

        if nuova_decisione is not None:
            logger.info("[AUTONOMIA] Decisione ottenuta dopo generazione autonoma")
            return nuova_decisione

    return None


def valuta_condizioni_generate_sicure(mondo, stato_runtime):
    """
    Valuta le condizioni generate gia' presenti nel progetto.

    Questa funzione fa da protezione:
    se condition_manager genera errori, soul.py non deve crashare.
    """

    try:
        import behaviors.condition_system.condition_manager as condition_manager

        # Caso piu' probabile nel tuo progetto:
        if hasattr(condition_manager, "valuta_condizioni_generate"):
            return condition_manager.valuta_condizioni_generate(mondo, stato_runtime)

        # Variante possibile:
        if hasattr(condition_manager, "valuta_condizioni_generate_caricate"):
            return condition_manager.valuta_condizioni_generate_caricate(mondo, stato_runtime)

        logger.warning("[AUTONOMIA] Nessuna funzione valida trovata in condition_manager")
        return None

    except Exception as e:
        logger.error("[AUTONOMIA] Errore valutando condizioni generate: {}".format(e))
        logger.error(traceback.format_exc())
        return None


def _eventi_per_memoria_cognitiva(firma, stato_runtime):
    eventi = {}

    for sorgente in [
        firma.get("eventi", {}),
        firma.get("eventi_attivi", {}),
        stato_runtime.get("eventi", {}),
        stato_runtime.get("eventi_reali", {})
    ]:
        if not isinstance(sorgente, dict):
            continue

        for nome_evento, valore in sorgente.items():
            if valore not in [False, None, "", [], {}]:
                eventi[nome_evento] = True

    evento_strutturato = firma.get("evento_strutturato", {})
    if not isinstance(evento_strutturato, dict):
        evento_strutturato = {}

    eventi_core = evento_strutturato.get("eventi_core", [])
    if not isinstance(eventi_core, list):
        eventi_core = []

    for nome_evento in eventi_core:
        nome_evento = str(nome_evento).strip()
        if nome_evento:
            eventi[nome_evento] = True

    return eventi


def _condizione_memoria_eseguibile(voce):
    nome = voce.get("nome", "")

    if not nome:
        return False

    if nome.endswith(".py"):
        nome = nome[:-3]

    path_file = os.path.join(CONDIZIONI_GENERATE_DIR, nome + ".py")

    return os.path.exists(path_file)


def _evento_coperto_da_voce(evento, voce):
    evento_norm = str(evento).lower().replace("-", "_").strip()

    if not evento_norm:
        return False

    testi_voce = [
        voce.get("nome", ""),
        voce.get("contesto_semantico", "")
    ]

    for evento_voce in voce.get("eventi_attivi_origine", []):
        testi_voce.append(str(evento_voce))

    testo_voce = " ".join(testi_voce).lower().replace("-", "_")

    if evento_norm in testo_voce:
        return True

    pezzi = [
        pezzo.strip()
        for pezzo in evento_norm.split("_")
        if len(pezzo.strip()) >= 4
    ]

    for pezzo in pezzi:
        if pezzo in testo_voce:
            return True

    return False


def _numero_eventi_coperti_da_voce(firma, stato_runtime, voce):
    eventi = _eventi_per_memoria_cognitiva(firma, stato_runtime)
    coperti = 0

    for nome_evento in eventi.keys():
        nome_norm = str(nome_evento).lower().strip()

        if nome_norm in [
            "fermo",
            "interazione_utente"
        ]:
            continue

        if _evento_coperto_da_voce(nome_evento, voce):
            coperti += 1

    return coperti


def _nome_condizione_senza_estensione(nome):
    nome = str(nome or "").strip()

    if nome.endswith(".py"):
        nome = nome[:-3]

    return nome


def _evento_informativo_generale(evento_strutturato, eventi_core):
    if not isinstance(evento_strutturato, dict):
        evento_strutturato = {}

    categoria = str(evento_strutturato.get("categoria", "") or "").lower()
    tipo = str(evento_strutturato.get("tipo", "") or "").lower()

    if not isinstance(eventi_core, list):
        eventi_core = []

    eventi_core = [
        str(e).lower().strip()
        for e in eventi_core
        if e not in [None, False, "", [], {}]
    ]

    return (
        categoria in ["informazione", "supporto_informativo"]
        or tipo in [
            "informazione_operativa",
            "contenuto_informativo_rilevante",
            "supporto_informativo_potenziale",
            "dettaglio_funzionale_osservabile"
        ]
        or "informazione_operativa" in eventi_core
        or "contenuto_informativo_rilevante" in eventi_core
        or "supporto_informativo_potenziale" in eventi_core
        or "dettaglio_funzionale_osservabile" in eventi_core
    )


def _testo_contiene_termine_operativo(testo):
    testo = _testo_sicuro(testo).lower()

    for termine in TERMINI_TESTO_OPERATIVO_SPECIFICO:
        termine = str(termine or "").lower().strip()

        if not termine:
            continue

        pattern = r"(^|[^a-z0-9_]){}($|[^a-z0-9_])".format(
            re.escape(termine)
        )

        if re.search(pattern, testo):
            return True

    return False


def _evento_ha_novita_specifica_generativa(mondo, evento_strutturato, eventi_core):
    if not isinstance(evento_strutturato, dict):
        evento_strutturato = {}

    if not isinstance(eventi_core, list):
        eventi_core = []

    eventi_core_norm = [
        str(e).lower().strip()
        for e in eventi_core
        if e not in [None, False, "", [], {}]
    ]

    categoria = str(evento_strutturato.get("categoria", "") or "").lower()
    tipo = str(evento_strutturato.get("tipo", "") or "").lower()
    stato = str(evento_strutturato.get("stato", "") or "").lower()

    if categoria in [
        "accesso",
        "ostacolo_spazio",
        "anomalia",
        "evento_composto"
    ]:
        return True

    if stato in ["non_disponibile", "anomalo", "potenzialmente_ostruito"]:
        return True

    if tipo in EVENTI_NOVITA_SPECIFICHE_GENERATIVE:
        return True

    for evento in eventi_core_norm:
        if evento in EVENTI_NOVITA_SPECIFICHE_GENERATIVE:
            return True

    return _testo_contiene_termine_operativo(mondo)


def _copertura_informativa_affidabile(
    voce,
    punteggio,
    positivi,
    negativi
):
    nome = _nome_condizione_senza_estensione(voce.get("nome", ""))
    categoria_voce = str(
        voce.get("categoria_cognitiva", "") or ""
    ).lower()
    motivi = voce.get("motivi_similarita", [])

    if nome not in CONDIZIONI_INFORMATIVE_GENERALI:
        return False

    if categoria_voce not in ["informazione", "curiosita", ""]:
        return False

    if not _condizione_memoria_eseguibile(voce):
        return False

    if negativi > 0 and negativi >= positivi:
        return False

    if punteggio >= 5:
        return True

    return punteggio >= 4 and "categoria" in motivi


def _generazione_gia_coperta_da_memoria(mondo, firma, stato_runtime):
    """
    Recupera condizioni simili prima di arrivare al prompt LLM.

    Il filtro e' conservativo: blocca la generazione solo quando la memoria
    contiene una condizione molto vicina e non chiaramente fragile.
    """

    if trova_condizioni_simili is None:
        return False, "", []

    try:
        eventi = _eventi_per_memoria_cognitiva(firma, stato_runtime)
        simili = trova_condizioni_simili(mondo, eventi, limite=5)
    except Exception as e:
        logger.warning(
            "[AUTONOMIA] Errore recuperando condizioni simili: {}".format(e)
        )
        return False, "", []

    if not simili:
        return False, "", []

    simili_eseguibili = [
        voce for voce in simili
        if _condizione_memoria_eseguibile(voce)
    ]

    if not simili_eseguibili:
        return False, "", simili

    stato_runtime["condizioni_simili_richiamate"] = simili

    scena_composta = (
        firma.get("eventi_multipli", False)
        or firma.get("situazione_composta", False)
    )
    evento_strutturato = firma.get("evento_strutturato", {})
    if not isinstance(evento_strutturato, dict):
        evento_strutturato = {}

    eventi_core = firma.get("eventi_core", [])
    if not isinstance(eventi_core, list):
        eventi_core = []

    informativo_generale = _evento_informativo_generale(
        evento_strutturato,
        eventi_core
    )
    novita_specifica = _evento_ha_novita_specifica_generativa(
        mondo,
        evento_strutturato,
        eventi_core
    )

    if novita_specifica:
        return False, "", simili

    for voce in simili_eseguibili:
        punteggio = voce.get("punteggio_similarita", 0)
        positivi = voce.get("numero_esempi_positivi", 0)
        negativi = voce.get("numero_esempi_negativi", 0)
        motivi = voce.get("motivi_similarita", [])

        eventi_match = [
            motivo for motivo in motivi
            if str(motivo).startswith("evento:")
        ]

        testo_match = [
            motivo for motivo in motivi
            if str(motivo).startswith("testo:")
        ]

        if negativi > positivi and negativi >= 2:
            continue

        if (
            informativo_generale
            and not novita_specifica
            and _copertura_informativa_affidabile(
                voce,
                punteggio,
                positivi,
                negativi
            )
        ):
            return True, (
                "contenuto informativo gia' coperto da condizione esistente"
            ), simili

        if scena_composta:
            eventi_coperti = _numero_eventi_coperti_da_voce(
                firma,
                stato_runtime,
                voce
            )

            if eventi_coperti < 2:
                continue

        if punteggio >= 11:
            return True, (
                "condizione simile gia' appresa: {} (punteggio {})"
                .format(voce.get("nome", "sconosciuta"), punteggio)
            ), simili

        if punteggio >= 8 and eventi_match and testo_match:
            return True, (
                "condizione simile recuperata dalla memoria: {}"
                .format(voce.get("nome", "sconosciuta"))
            ), simili

        if punteggio >= 7 and eventi_match and positivi >= 2 and negativi == 0:
            return True, (
                "condizione simile affidabile gia' presente: {}"
                .format(voce.get("nome", "sconosciuta"))
            ), simili

    return False, "", simili


def valuta_ipotesi_temporanee_sicura(mondo, firma, stato_runtime):
    if stato_runtime is None:
        stato_runtime = {}

    cache = stato_runtime.get("_esito_ipotesi_temporanea")

    if isinstance(cache, dict) and cache.get("mondo") == mondo:
        return cache.get("esito", {
            "ha_ipotesi": False,
            "genera_condizione": False,
            "motivo": "ipotesi temporanea non disponibile"
        })

    if valuta_ipotesi_temporanee is None:
        return {
            "ha_ipotesi": False,
            "genera_condizione": False,
            "motivo": "memoria ipotesi temporanee non disponibile"
        }

    try:
        esito = valuta_ipotesi_temporanee(
            mondo,
            firma,
            stato_runtime
        )
        stato_runtime["_esito_ipotesi_temporanea"] = {
            "mondo": mondo,
            "esito": esito
        }
        return esito
    except Exception as e:
        logger.warning(
            "[AUTONOMIA] Errore memoria ipotesi temporanee: {}".format(e)
        )
        return {
            "ha_ipotesi": False,
            "genera_condizione": False,
            "motivo": "errore memoria ipotesi temporanee"
        }
    
def situazione_merita_generazione(mondo, stato_runtime):
    """
    Decide se la situazione osservata merita una nuova condizione autonoma.

    Versione finale:
    - gli eventi unknown/scoperta devono poter generare davvero;
    - non dipende piu' dal flag abilita_generazione_eventi_sconosciuti;
    - mantiene i filtri contro mondo vuoto, banale e gia' tentato.
    """

    firma = costruisci_firma_situazione(mondo, stato_runtime)
    logger.info(
        "[AUTONOMIA] Firma situazione: {}".format(
            _maschera_dati_sensibili(firma)
        )
    )

    if firma["mondo_vuoto"]:
        return False, "mondo vuoto"

    if firma["gia_tentata"]:
        return False, "situazione gia' tentata"

    evento_strutturato = firma.get("evento_strutturato", {})
    if not isinstance(evento_strutturato, dict):
        evento_strutturato = {}

    if situazione_fallback_visivo_neutra(mondo, evento_strutturato):
        chiudi_generazione_non_permessa(
            stato_runtime,
            "fallback visivo generico neutro"
        )
        return False, "fallback visivo generico neutro non generativo"

    if evento_strutturato_non_deve_generare(evento_strutturato):
        chiudi_generazione_non_permessa(
            stato_runtime,
            "evento strutturato non generativo"
        )
        return False, "evento strutturato non generativo"

    if _evento_strutturato_neutro_non_generativo(evento_strutturato):
        chiudi_generazione_non_permessa(
            stato_runtime,
            "evento strutturato neutro non generativo"
        )
        return False, "evento strutturato neutro non generativo"

    if firma["banale"]:
        return False, "situazione banale"

    tipo = str(evento_strutturato.get("tipo", "")).lower()
    categoria = str(evento_strutturato.get("categoria", "")).lower()
    origine = str(evento_strutturato.get("origine", "")).lower()

    eventi_core = firma.get("eventi_core", [])

        # Propago SEMPRE tutti gli eventi attivi della firma
    # dentro stato_runtime["eventi"], inclusi gli unknown.
    try:
        stato_runtime.setdefault("eventi", {})

        eventi_attivi_firma = firma.get("eventi_attivi", {})

        if isinstance(eventi_attivi_firma, dict):
            for nome_evento, valore in eventi_attivi_firma.items():
                if valore not in [False, None, "", [], {}]:
                    stato_runtime["eventi"][nome_evento] = True

        _sanitizza_eventi_supporto_informativo(stato_runtime.get("eventi", {}))
        _sanitizza_eventi_supporto_informativo(
            stato_runtime.get("eventi_reali", {})
        )

    except Exception as e:
        logger.warning(
            "[AUTONOMIA] Errore propagando eventi_attivi nel runtime: {}".format(e)
        )

    if not isinstance(eventi_core, list):
        eventi_core = []

    eventi_core = filtra_eventi_helper(eventi_core)

    if stato_runtime.get("forza_generazione_da_ipotesi_strutturata", False):
        if evento_strutturato_puo_generare_da_ipotesi(evento_strutturato):
            return True, stato_runtime.get(
                "motivo_generazione_ipotesi_strutturata",
                "ipotesi strutturata confermata"
            )

        stato_runtime.pop("forza_generazione_da_ipotesi_strutturata", None)
        stato_runtime.pop("motivo_generazione_ipotesi_strutturata", None)
        return False, "ipotesi strutturata non generativa"

    if (
        osservazioni_mirate_per_scena(stato_runtime, mondo, firma=firma) >= 1
        and evento_rilevante_per_generazione_dopo_osservazione(
            stato_runtime,
            firma=firma
        )
    ):
        gia_coperta_osservazione, motivo_coperta_osservazione, _ = (
            _generazione_gia_coperta_da_memoria(
                mondo,
                firma,
                stato_runtime
            )
        )

        if gia_coperta_osservazione:
            return False, motivo_coperta_osservazione

        return True, "osservazione mirata gia' eseguita per la scena"

    gia_coperta, motivo_memoria, condizioni_simili = (
        _generazione_gia_coperta_da_memoria(
            mondo,
            firma,
            stato_runtime
        )
    )

    if condizioni_simili:
        logger.info(
            "[AUTONOMIA][MEMORIA] Condizioni simili richiamate: {}".format(
                [
                    (
                        voce.get("nome"),
                        voce.get("punteggio_similarita")
                    )
                    for voce in condizioni_simili[:3]
                ]
            )
        )

    if gia_coperta:
        costruisci_sintesi_semantica_osservazione(mondo, stato_runtime)
        logger.info(
            "[AUTONOMIA][MEMORIA] Generazione evitata: {}".format(
                motivo_memoria
            )
        )
        return False, motivo_memoria

    if evento_generale_informativo_con_testo_specifico(stato_runtime, mondo):
        return True, "testo visibile con possibile significato specifico"

    esito_ipotesi = valuta_ipotesi_temporanee_sicura(
        mondo,
        firma,
        stato_runtime
    )

    if esito_ipotesi.get("ha_ipotesi"):
        if esito_ipotesi.get("genera_condizione"):
            return True, esito_ipotesi.get(
                "motivo",
                "ipotesi temporanea confermata"
            )

        costruisci_sintesi_semantica_osservazione(mondo, stato_runtime)
        return False, esito_ipotesi.get(
            "motivo",
            "ipotesi temporanea ancora debole"
        )

    esito_world_model = stato_runtime.get("world_model", {})
    ipotesi_attiva = stato_runtime.get("ipotesi_temporanea", {})
    if (
        isinstance(esito_world_model, dict)
        and esito_world_model.get("familiare")
        and not esito_world_model.get("anomalia")
        and not stato_runtime.get(
            "forza_generazione_da_ipotesi_strutturata",
            False
        )
        and not (
            isinstance(ipotesi_attiva, dict)
            and ipotesi_attiva.get("confermata")
        )
    ):
        return False, "situazione gia' familiare nel world model"

    if (
        tipo in ["unknown", "sconosciuto", "scoperta"]
        or categoria in ["unknown", "sconosciuta", "scoperta"]
        or origine in ["unknown", "scoperta"]
    ):
        if len(eventi_core) > 0:
            return True, "evento sconosciuto/scoperta valido"

        return False, "evento sconosciuto senza eventi_core"

    if firma["eventi_multipli"]:
        return True, "eventi multipli rilevati"

    if firma["situazione_composta"]:
        return True, "situazione composta non banale"

    if firma["ha_novita_runtime"]:
        eventi_descritti = firma.get("eventi_descritti", {})

        eventi_sconosciuti = [
            nome
            for nome, dati in eventi_descritti.items()
            if not dati.get("conosciuto", True)
            and nome not in EVENTI_SUPPORTO_INFORMATIVO_NON_GENERATIVI
        ]

        if eventi_sconosciuti:
            return True, "eventi sconosciuti rilevati: {}".format(
                ", ".join(eventi_sconosciuti)
            )

        return True, "novita' runtime non ancora coperta"

    if firma["ha_testo_sensoriale_non_banale"]:
        if len(firma.get("eventi_attivi", {}).keys()) == 0:
            return False, "situazione sensoriale osservata ma senza eventi attivi"

        return True, "situazione sensoriale non banale"

    return False, "situazione non abbastanza significativa"

def _estrai_eventi_noti_minimi(mondo):
    testo = (mondo or "").lower()

    eventi = {
        "carezza_testa": "testa" in testo and ("tocc" in testo or "carezza" in testo),
        "mano_destra": "mano destra" in testo,
        "mano_sinistra": "mano sinistra" in testo,
        "entrambe_mani": "entrambe le mani" in testo,
        "volto_riconosciuto": "riconosco" in testo,
        "volto_ignoto": "volto ignoto" in testo or "non riconosco" in testo,
        "ostacolo_destra": "ostacolo a destra" in testo,
        "ostacolo_sinistra": "ostacolo a sinistra" in testo,
        "ostacolo_frontale": "ostacolo frontale" in testo,
        "rumore_improvviso": "rumore improvviso" in testo or "suono improvviso" in testo,
        "rumore_singolo": "rumore singolo" in testo or "colpo" in testo,
        "battiti_mani": "battiti" in testo or "battito" in testo,
        "fermo": "sono fermo" in testo,
        "camminando": "sto camminando" in testo
    }

    if eventi.get("camminando", False):
        eventi["fermo"] = False

    if eventi.get("fermo", False):
        eventi["camminando"] = False

    return eventi

def _pulisci_mondo_per_unknown(mondo):
    """
    Rimuove marker tecnici usati da soul.py per attivare la curiosità.
    Gli eventi UNKNOWN devono nascere dal contenuto osservato,
    non da PRENDI L'INIZIATIVA / OSSERVAZIONE_AUTONOMA.
    """
    testo = (mondo or "").lower()

    marker = [
        "report:",
        "prendi l'iniziativa",
        "prendi l iniziativa",
        "prendi liniziativa",
        "osservazione_autonoma",
        "osservazione autonoma",
        "nessuna_condizione_attiva",
        "nessuna condizione attiva",
        "sono fermo",
        "sto camminando"
    ]

    for m in marker:
        testo = testo.replace(m, " ")

    # Se c'è VEDO:, privilegio la parte visiva.
    if "vedo:" in testo:
        testo = testo.split("vedo:", 1)[1]

    testo = testo.replace("vedo:", " ")
    testo = testo.replace(".", " ")
    testo = " ".join(testo.split())

    return testo

def costruisci_firma_situazione(mondo, stato_runtime):
    """
    Trasforma il mondo attuale in una descrizione piu' astratta.

    L'obiettivo e' non dipendere solo da condizioni scritte a mano
    come tocco testa, tocco piede, ostacolo, volto, ecc.
    """

    if stato_runtime is None:
        stato_runtime = {}

    _diag_pipeline("costruisci_firma.input_mondo", mondo)

    testo = (mondo or "").strip().lower()
    eventi = dict(stato_runtime.get("eventi", {}))
    eventi_reali = dict(stato_runtime.get("eventi_reali", {}))
    evento_strutturato = stato_runtime.get("evento_strutturato", {})
    _diag_pipeline("costruisci_firma.input_eventi", eventi)
    _diag_pipeline("costruisci_firma.input_eventi_reali", eventi_reali)
    _diag_pipeline("costruisci_firma.input_evento_strutturato", evento_strutturato)

    if not isinstance(evento_strutturato, dict):
        evento_strutturato = {}

    if not isinstance(eventi, dict):
        eventi = {}
    
    if not isinstance(eventi_reali, dict):
        eventi_reali = {}

    eventi_noti_testo = _estrai_eventi_noti_minimi(mondo)

    for chiave, valore in eventi_noti_testo.items():
        if chiave not in eventi:
            eventi[chiave] = valore
    
    # Eventi UNKNOWN cognitivamente significativi.
    # NON trasformiamo descrizioni statiche in eventi.
    # Usiamo solo situazioni utili al comportamento.

    try:
        if estrai_eventi_sconosciuti is not None:

            mondo_unknown = _pulisci_mondo_per_unknown(
                mondo
            )
            _diag_pipeline("costruisci_firma.mondo_unknown", mondo_unknown)

        if mondo_unknown:
            # Reasoner semantico generalista
            try:
                from behaviors.event_system.unknown_situation_reasoner import (
                    ragiona_situazione_sconosciuta
                )

                ragionamento = (
                    ragiona_situazione_sconosciuta(
                        mondo_unknown
                    )
                )
                _diag_pipeline("costruisci_firma.reasoner_output", ragionamento)

                if (
                    isinstance(ragionamento, dict)
                    and ragionamento.get("evento")
                ):
                    eventi[
                        ragionamento["evento"]
                    ] = True

            except Exception as e:
                logger.warning(
                    "[AUTONOMIA] Errore reasoner semantico: {}".format(e)
                )

            # Extractor eventi sconosciuti
            eventi_unknown = (
                estrai_eventi_sconosciuti(
                    mondo_unknown
                )
            )
            _diag_pipeline("costruisci_firma.extractor_output", eventi_unknown)

            for ev in eventi_unknown:

                if not isinstance(ev, dict):
                    continue

                nome = ev.get("nome")

                if nome:
                    eventi[nome] = True
                    if not isinstance(ev, dict):
                        continue

                    nome = ev.get("nome")

                    if nome:
                        eventi[nome] = True

    except Exception as e:
        logger.warning(
            "[AUTONOMIA] Errore estrazione eventi sconosciuti: {}".format(e)
        )

    _sanitizza_eventi_supporto_informativo(eventi)
    _sanitizza_eventi_supporto_informativo(eventi_reali)
    
    parole_banali = [
        "la mia batteria",
        "batteria",
        "sono fermo",
        "fermo",
        "nessun evento",
        "nessuna interazione"
    ]

    parole_sensoriali_generiche = [
        "sento",
        "percepisco",
        "rilevo",
        "vedo",
        "tocca",
        "tocco",
        "pressione",
        "contatto",
        "movimento",
        "ostacolo",
        "volto",
        "rumore",
        "suono",
        "voce",
        "interazione",
        "evento"
    ]

    chiavi_runtime_banali = [
        "batteria",
        "battery",
        "livello_batteria",
        "postura",
        "stato_movimento",
        "fermo",
        "timestamp",
        "tempo"
    ]

    eventi_attivi = {}

    # Eventi estratti dal testo
    for chiave, valore in eventi.items():
        chiave_norm = str(chiave).lower()

        if chiave_norm in chiavi_runtime_banali:
            continue

        if valore not in [None, False, "", [], {}]:
            eventi_attivi[chiave] = valore

    # Eventi reali dei sensori (priorità alta)
    for chiave, valore in eventi_reali.items():
        chiave_norm = str(chiave).lower()

        if chiave_norm in chiavi_runtime_banali:
            continue

        if valore not in [None, False, "", [], {}]:
            eventi_attivi[chiave] = valore

    indicatori_composti = [
        ["sinistra", "destra"],
        ["mano", "piede"],
        ["testa", "mano"],
        ["volto", "voce"],
        ["interazione", "movimento"]
    ]

    # EVENTI STRUTTURATI PRIORITARI
    # Se ho eventi reali coerenti, li uso prima del parsing testo.
    eventi_sociali = [
        "carezza_testa",
        "mano_sinistra",
        "mano_destra",
        "entrambe_mani",
        "volto_riconosciuto",
        "volto_ignoto"
    ]

    eventi_safety = [
        "ostacolo_sinistra",
        "ostacolo_destra",
        "ostacolo_frontale",
        "urto_piedi",
        "piede_sinistro",
        "piede_destro",
        "pericolo_caduta"
    ]

    eventi_audio = [
        "rumore_improvviso",
        "rumore_singolo",
        "battiti_mani"
    ]

    mondo_vuoto = not testo

    solo_banale = False
    if testo:
        contiene_banale = any(p in testo for p in parole_banali)
        contiene_sensoriale = any(p in testo for p in parole_sensoriali_generiche)
        solo_banale = contiene_banale and not contiene_sensoriale and len(eventi_attivi) == 0

    eventi_core = evento_strutturato.get("eventi_core", [])

    if not isinstance(eventi_core, list):
        eventi_core = []

    eventi_core = [
        e for e in eventi_core
        if str(e).lower().strip() != "interazione_utente"
    ]
    
    numero_eventi_reali = len(eventi_attivi.keys())

    # Se gli eventi strutturati reali esistono,
    # considero la situazione significativa anche con poco testo.
    presenza_eventi_reali = any([
        k in eventi_attivi
        for k in (
            eventi_sociali +
            eventi_safety +
            eventi_audio
        )
    ])

    eventi_attivi_generativi = [
        k for k in eventi_attivi.keys()
        if str(k).lower().strip() != "interazione_utente"
    ]

    eventi_multipli = (
        len(eventi_core) >= 2
        or len(eventi_attivi_generativi) >= 2
        or (
            evento_strutturato.get("evento_composto", False)
            and len(eventi_core) >= 2
        )
    )

    situazione_composta = False

    for gruppo in indicatori_composti:
        if all(parola in testo for parola in gruppo):
            situazione_composta = True
            break

    chiavi_eventi_attivi = " ".join(str(k).lower() for k in eventi_attivi.keys())

    if not situazione_composta:
        for gruppo in indicatori_composti:
            if all(parola in chiavi_eventi_attivi for parola in gruppo):
                situazione_composta = True
                break

    eventi_significativi = [
        k for k in eventi_attivi.keys()
        if str(k).lower().strip() not in [
            "fermo",
            "camminando",
            "interazione_utente"
        ]
    ]

    fallback_visivo_neutro = situazione_fallback_visivo_neutra(
        mondo,
        evento_strutturato
    )

    ha_novita_runtime = (
        presenza_eventi_reali
        or len(eventi_significativi) > 0
        or (
            evento_strutturato.get("tipo", "generico") != "generico"
            and not fallback_visivo_neutro
        )
    )

    ha_testo_sensoriale_non_banale = (
        bool(testo)
        and not solo_banale
        and (
            any(p in testo for p in parole_sensoriali_generiche)
            or len(testo.split()) >= 8
        )
    )

    mondo_normalizzato = testo
    gia_tentata = mondo_normalizzato == ULTIMO_MONDO_GENERATO

    eventi_descritti = {}

    try:
        if arricchisci_eventi_registro is not None:
            eventi_descritti = arricchisci_eventi_registro(eventi_attivi)
    except Exception:
        eventi_descritti = {}

    firma = {
        "testo": testo,
        "eventi": eventi,
        "eventi_attivi": eventi_attivi,
        "eventi_descritti": eventi_descritti,
        "mondo_vuoto": mondo_vuoto,
        "banale": solo_banale,
        "eventi_multipli": eventi_multipli,
        "situazione_composta": situazione_composta,
        "ha_novita_runtime": ha_novita_runtime,
        "ha_testo_sensoriale_non_banale": ha_testo_sensoriale_non_banale,
        "evento_strutturato": evento_strutturato,
        "eventi_core": eventi_core,
        "gia_tentata": gia_tentata
    }

    _diag_pipeline("costruisci_firma.output", firma)
    return firma
    

def prova_generazione_autonoma(mondo, stato_runtime, motivo):
    """
    Prova a generare una nuova condizione tramite condition_generator.

    FASE C:
    - limita la frequenza di generazione
    - passa al generator i 4 argomenti corretti
    - non fa crashare soul.py
    - dopo la generazione rivaluta subito le condizioni
    """

    global ULTIMA_GENERAZIONE
    global ULTIMO_MONDO_GENERATO

    adesso = time.time()
    mondo_normalizzato = (mondo or "").strip().lower()

    evento_non_generativo = evento_strutturato_non_deve_generare(
        stato_runtime.get("evento_strutturato", {})
    )
    if (
        evento_non_generativo
        and "ipotesi" not in str(motivo or "").lower()
        and "osservazione mirata" not in str(motivo or "").lower()
        and not evento_rilevante_per_generazione_dopo_osservazione(
            stato_runtime
        )
    ):
        chiudi_generazione_non_permessa(
            stato_runtime,
            "evento strutturato non generativo"
        )
        logger.info(
            "[AUTONOMIA] Generazione saltata: evento strutturato non generativo"
        )
        return None

    chiave_privata_runtime = (
        stato_runtime.get("openai_api_key")
        or os.environ.get("OPENAI_API_KEY")
    )

    if (
        stato_runtime.get("llm_generazione_non_disponibile", False)
        and not str(chiave_privata_runtime or "").strip()
    ):
        stato_runtime["llm_generazione_non_disponibile"] = True
        stato_runtime["motivo_llm_generazione_non_disponibile"] = (
            stato_runtime.get("motivo_llm_generazione_non_disponibile")
            or "llm_non_disponibile"
        )
        logger.warning(
            "[AUTONOMIA] Generazione saltata: LLM temporaneamente non disponibile"
        )
        return None

    if stato_runtime.get("llm_generazione_non_disponibile", False):
        stato_runtime.pop("llm_generazione_non_disponibile", None)
        stato_runtime.pop("motivo_llm_generazione_non_disponibile", None)

    if (
        not str(chiave_privata_runtime or "").strip()
        and stato_runtime.get("openai_api_key") in [None, ""]
    ):
        try:
            import behaviors.condition_system.condition_generator as condition_generator_stato
            if getattr(condition_generator_stato, "LLM_NON_DISPONIBILE", False):
                stato_runtime["llm_generazione_non_disponibile"] = True
                stato_runtime["motivo_llm_generazione_non_disponibile"] = (
                    getattr(
                        condition_generator_stato,
                        "LLM_MOTIVO_NON_DISPONIBILE",
                        None
                    )
                    or "llm_non_disponibile"
                )
                logger.warning(
                    "[AUTONOMIA] Generazione saltata: LLM temporaneamente non disponibile"
                )
                return None
        except Exception:
            pass

    if ULTIMO_MONDO_GENERATO == mondo_normalizzato:
        logger.info("[AUTONOMIA] Generazione saltata: situazione gia' tentata")
        return None

    if adesso - ULTIMA_GENERAZIONE < INTERVALLO_MINIMO_GENERAZIONE:
        logger.info("[AUTONOMIA] Generazione saltata: troppo ravvicinata")
        return None

    ULTIMA_GENERAZIONE = adesso

    try:
        import behaviors.condition_system.condition_generator as condition_generator

        logger.info("[AUTONOMIA] Provo generazione autonoma. Motivo: {}".format(motivo))

        if (
            getattr(condition_generator, "LLM_NON_DISPONIBILE", False)
            and not getattr(condition_generator, "LLM_CHIAVE_NON_DISPONIBILE", None)
        ):
            stato_runtime["llm_generazione_non_disponibile"] = True
            stato_runtime["motivo_llm_generazione_non_disponibile"] = (
                getattr(
                    condition_generator,
                    "LLM_MOTIVO_NON_DISPONIBILE",
                    None
                )
                or "llm_non_disponibile"
            )
            logger.warning(
                "[AUTONOMIA] Generazione saltata: LLM temporaneamente non disponibile"
            )
            return None

        if hasattr(condition_generator, "genera_condizione_autonoma"):
            dati_memoria_runtime = stato_runtime.get("memoria", {})
            if not isinstance(dati_memoria_runtime, dict):
                dati_memoria_runtime = {}

            dati_memoria = dict(dati_memoria_runtime)
            if stato_runtime.get("world_model"):
                dati_memoria["world_model"] = stato_runtime.get("world_model")
            stato_robot = stato_runtime.get("stato_robot", {})
            storia_episodica = stato_runtime.get("ipotesi_temporanea")

            if isinstance(storia_episodica, dict):
                storia_episodica = dict(storia_episodica)
                storia_episodica["motivo_cognitivo_generazione"] = motivo
            else:
                storia_episodica = None

            chiave_privata = (
                chiave_privata_runtime
            )
            logger.info(
                "[AUTONOMIA][LLM] API key presente per generator: {} | fonte={}".format(
                    bool(str(chiave_privata or "").strip()),
                    "runtime" if stato_runtime.get("openai_api_key") else "env"
                )
            )

            path_nuova_condizione = chiama_genera_condizione_autonoma_sicura(
                condition_generator.genera_condizione_autonoma,
                mondo,
                dati_memoria,
                stato_robot,
                chiave_privata,
                storia_episodica=storia_episodica
            )

            if getattr(condition_generator, "LLM_NON_DISPONIBILE", False):
                stato_runtime["llm_generazione_non_disponibile"] = True
                stato_runtime["motivo_llm_generazione_non_disponibile"] = (
                    getattr(
                        condition_generator,
                        "LLM_MOTIVO_NON_DISPONIBILE",
                        None
                    )
                    or "llm_non_disponibile"
                )
                logger.warning(
                    "[AUTONOMIA] API key non valida: generazione disabilitata temporaneamente"
                )
                return None

            if path_nuova_condizione:
                ULTIMO_MONDO_GENERATO = mondo_normalizzato

                logger.info("[AUTONOMIA] Nuova condizione generata: {}".format(
                    path_nuova_condizione
                ))

                try:
                    if hasattr(condition_generator, "reset_cache_condizioni"):
                        condition_generator.reset_cache_condizioni()
                except Exception:
                    pass

                try:
                    from behaviors.condition_system.condition_manager import reset_cache_condizioni
                    reset_cache_condizioni()
                except Exception:
                    pass
            else:
                logger.info(
                    "[AUTONOMIA] Nessuna nuova condizione generata: rivaluto condizioni esistenti"
                )

                try:
                    from behaviors.condition_system.condition_manager import (
                        reset_cache_condizioni
                    )
                    reset_cache_condizioni()
                except Exception:
                    pass

                return valuta_condizioni_generate_sicure(
                    mondo,
                    stato_runtime
                )

        elif hasattr(condition_generator, "genera_condizione_da_mondo"):
            condition_generator.genera_condizione_da_mondo(mondo, stato_runtime)

        elif hasattr(condition_generator, "valuta_e_genera_condizione"):
            condition_generator.valuta_e_genera_condizione(mondo, stato_runtime)

        else:
            logger.warning("[AUTONOMIA] Nessuna funzione di generazione compatibile trovata")
            return None

        logger.info("[AUTONOMIA] Generazione completata, rivaluto condizioni")

        return valuta_condizioni_generate_sicure(mondo, stato_runtime)

    except Exception as e:
        logger.error("[AUTONOMIA] Errore durante generazione autonoma: {}".format(e))
        logger.error(traceback.format_exc())
        return None
