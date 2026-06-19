# -*- coding: utf-8 -*-
"""
Generatore autonomo di condizioni Python tramite LLM.

Flusso:
1. chiede al LLM codice Python libero;
2. salva il codice in quarantine_conditions;
3. analizza il codice;
4. se sicuro, lo importa e lo valida;
5. se valido, lo promuove in generated_conditions;
6. se non valido, lo sposta in rejected_conditions.
"""

import os
import re
import time
import shutil
import logging
import requests
import json
try:
    import importlib.util
except ImportError:
    importlib = None

try:
    import imp
except ImportError:
    imp = None
import ast

try:
    unicode
except NameError:
    unicode = str

try:
    basestring
except NameError:
    basestring = str

from behaviors.condition_system.condition_manager import reset_cache_condizioni
from behaviors.condition_system.condition_memory import (
    memoria_cognitiva_condizioni,
    salva_metadati_condizione,
    trova_condizioni_simili
)

try:
    from behaviors.event_system.unknown_event_extractor import arricchisci_eventi_con_sconosciuti
except Exception:
    arricchisci_eventi_con_sconosciuti = None

try:
    from behaviors.event_system.event_registry import arricchisci_eventi_registro
except Exception:
    arricchisci_eventi_registro = None

try:
    from behaviors.event_system.world_model_memory import (
        recupera_credenze_rilevanti
    )
except Exception:
    recupera_credenze_rilevanti = None

logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

LLM_NON_DISPONIBILE = False
LLM_NON_DISPONIBILE_LOGGATO = False
LLM_MOTIVO_NON_DISPONIBILE = None
OPENAI_CHAT_COMPLETIONS_ENDPOINT = "https://api.openai.com/v1/chat/completions"
OPENAI_MODEL_GENERATORE = "gpt-4o-mini"


def _key_presente(chiave_privata):
    try:
        return bool(str(chiave_privata or "").strip())
    except Exception:
        return False


def _log_richiesta_llm(area, chiave_privata, endpoint, modello):
    logger.info(u"[GENERATOR][{}] API key presente: {}".format(
        area,
        _key_presente(chiave_privata)
    ))
    logger.info(u"[GENERATOR][{}] endpoint usato: {}".format(
        area,
        endpoint
    ))
    logger.info(u"[GENERATOR][{}] modello usato: {}".format(
        area,
        modello
    ))


def _log_richiesta_inviata(area):
    logger.info(u"[GENERATOR][{}] richiesta inviata".format(area))


def _log_fallback(area, motivo):
    logger.warning(u"[GENERATOR][{}] fallback attivato: {}".format(
        area,
        motivo
    ))


def _llm_disponibile(chiave_privata):
    global LLM_NON_DISPONIBILE_LOGGATO

    if LLM_NON_DISPONIBILE or not _key_presente(chiave_privata):
        if not LLM_NON_DISPONIBILE_LOGGATO:
            logger.warning(u"[GENERATOR] API key non valida: generazione disabilitata temporaneamente")
            LLM_NON_DISPONIBILE_LOGGATO = True
        return False

    return True


def _risposta_indica_api_key_invalida(testo):
    try:
        testo = unicode(testo or "").lower()
    except Exception:
        testo = ""

    return (
        "invalid_api_key" in testo or
        "incorrect api key" in testo or
        "you didn't provide an api key" in testo or
        "you did not provide an api key" in testo or
        "401" in testo
    )


def _marca_llm_non_disponibile(testo):
    global LLM_NON_DISPONIBILE
    global LLM_NON_DISPONIBILE_LOGGATO
    global LLM_MOTIVO_NON_DISPONIBILE

    if not _risposta_indica_api_key_invalida(testo):
        return False

    LLM_NON_DISPONIBILE = True
    LLM_MOTIVO_NON_DISPONIBILE = "invalid_api_key"
    if not LLM_NON_DISPONIBILE_LOGGATO:
        logger.warning(u"[GENERATOR] API key non valida: generazione disabilitata temporaneamente")
        LLM_NON_DISPONIBILE_LOGGATO = True

    return True

BASE_DIR = os.path.dirname(__file__)

QUARANTINE_DIR = os.path.join(BASE_DIR, "quarantine_conditions")
GENERATED_DIR = os.path.join(BASE_DIR, "generated_conditions")
REJECTED_DIR = os.path.join(BASE_DIR, "rejected_conditions")

AZIONI_CONSENTITE = [
    "parla",
    "guarda",
    "occhi",
    "animazione",
    "posa",
    "fermati",
    "cammina",
    "gira"
]

TOKEN_VIETATI = [
    "import os",
    "import sys",
    "import subprocess",
    "import socket",
    "import shutil",
    "import requests",
    "open(",
    "file(",
    "exec",
    "eval",
    "compile",
    "__import__",
    "globals",
    "locals",
    "input(",
    "raw_input(",
    "while True",
    "while 1",
    "for ever",
    "ALProxy",
    "naoqi",
    "thread",
    "multiprocessing"
]

def estrai_eventi(mondo, stato_runtime):
    testo = mondo.lower()

    batteria_valore = None

    try:
        match_batteria = re.search(r"batteria.*?(\d+)%", testo)
        if match_batteria:
            batteria_valore = int(match_batteria.group(1))
    except Exception:
        batteria_valore = None

    piede_sinistro = "piede sinistro" in testo
    piede_destro = "piede destro" in testo

    evento_tattile_umano = (
        "mano sinistra" in testo or
        "mano destra" in testo or
        "entrambe le mani" in testo or
        "carezza" in testo or
        "testa" in testo
    )

    robot_fermo = "sono fermo" in testo
    robot_cammina = "sto camminando" in testo

    qualcosa_sinistra = "qualcosa" in testo and "sinistra" in testo
    qualcosa_destra = "qualcosa" in testo and "destra" in testo

    ostacolo_sinistra_reale = (
        "ostacolo a sinistra" in testo or
        ("urto tattile" in testo and "sinistra" in testo) or
        (
            qualcosa_sinistra and
            not (robot_fermo and evento_tattile_umano)
        )
    )

    ostacolo_destra_reale = (
        "ostacolo a destra" in testo or
        ("urto tattile" in testo and "destra" in testo) or
        (
            qualcosa_destra and
            not (robot_fermo and evento_tattile_umano)
        )
    )

    ostacolo_frontale_reale = (
        "ostacolo frontale" in testo or
        (
            (
                "vedo qualcosa vicino" in testo or
                "qualcosa vicino" in testo
            ) and
            not (robot_fermo and evento_tattile_umano)
        )
    )

    eventi = {
        "batteria_percentuale": batteria_valore,
        "batteria_bassa": batteria_valore is not None and batteria_valore <= 25,
        "batteria_critica": batteria_valore is not None and batteria_valore <= 15,

        "carezza_testa": "testa" in testo and ("tocc" in testo or "carezza" in testo),

        "mano_sinistra": "mano sinistra" in testo,
        "mano_destra": "mano destra" in testo,
        "entrambe_mani": "entrambe le mani" in testo,

        "piede_sinistro": piede_sinistro,
        "piede_destro": piede_destro,
        "entrambi_piedi": (
            "ostacolo frontale ai piedi" in testo or
            "entrambi i piedi" in testo or
            "due piedi" in testo or
            (piede_sinistro and piede_destro)
        ),

        "urto": "urto" in testo,
        "urto_piedi": (
            "urto tattile" in testo and (
                "piede" in testo or
                "piedi" in testo
            )
        ),

        "ostacolo_sinistra": ostacolo_sinistra_reale,
        "ostacolo_destra": ostacolo_destra_reale,
        "ostacolo_frontale": ostacolo_frontale_reale,

        "fermo": "sono fermo" in testo,
        "camminando": "sto camminando" in testo,

        "volto_riconosciuto": "riconosco" in testo,
        "volto_ignoto": "volto ignoto" in testo or "non riconosco" in testo,

        "pericolo": (
            "pericolo" in testo or
            "caduta" in testo or
            "cadere" in testo or
            "sollevamento" in testo or
            "pavimento mancante" in testo
        ),

        "rumore_improvviso": (
            "rumore improvviso" in testo or
            "suono improvviso" in testo
        ),

        "rumore_singolo": (
            "rumore singolo" in testo or
            "colpo" in testo
        ),

        "battiti_mani": (
            "battiti" in testo or
            "battito" in testo
        ),
    }

    # PRIORITÀ AGLI EVENTI STRUTTURATI REALI
    try:
        eventi_runtime = stato_runtime.get("eventi", {})
        if isinstance(eventi_runtime, dict):
            eventi.update(eventi_runtime)
    except Exception:
        pass

    try:
        eventi_reali = stato_runtime.get("eventi_reali", {})
        if isinstance(eventi_reali, dict):
            eventi.update(eventi_reali)
    except Exception:
        pass

    # Coerenza movimento: gli eventi strutturati prevalgono sul testo
    if eventi.get("camminando", False):
        eventi["fermo"] = False

    if eventi.get("fermo", False):
        eventi["camminando"] = False

    # Eventi sconosciuti:
    # aggiunge concetti nuovi senza sovrascrivere eventi noti.
    try:
        if arricchisci_eventi_con_sconosciuti is not None:
            eventi = arricchisci_eventi_con_sconosciuti(mondo, eventi)
    except Exception as e:
        logger.warning(u"[GENERATOR] Errore estrazione eventi sconosciuti: {}".format(e))

    return eventi

def _normalizza_eventi_sconosciuti(eventi_sconosciuti):
    """
    Converte gli eventi unknown in formato compatibile col generator.

    INPUT:
    [
        {
            "nome": "accesso_non_disponibile",
            "priorita": "alta",
            ...
        }
    ]

    OUTPUT:
    {
        "accesso_non_disponibile": True
    }
    """

    risultato = {}

    if not eventi_sconosciuti:
        return risultato

    for ev in eventi_sconosciuti:

        if isinstance(ev, dict):
            nome = ev.get("nome")

            if nome:
                risultato[nome] = True

        elif isinstance(ev, basestring):
            risultato[ev] = True

    return risultato

def _carica_modulo_da_file(nome_modulo, path_file):
    """
    Carica un modulo Python da file.
    Compatibile sia con Python 3 sia con Python 2.7/NAO.
    """

    if importlib is not None:
        try:
            spec = importlib.util.spec_from_file_location(nome_modulo, path_file)
            modulo = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(modulo)
            return modulo
        except Exception:
            pass

    if imp is not None:
        return imp.load_source(nome_modulo, path_file)

    raise ImportError("Nessun sistema disponibile per caricare il modulo")

def _assicura_cartelle():
    for cartella in [QUARANTINE_DIR, GENERATED_DIR, REJECTED_DIR]:
        if not os.path.exists(cartella):
            os.makedirs(cartella)


def _slug_testo(testo):
    testo_originale = testo
    testo = testo.lower()

    testo = testo.replace("report:", " ")
    testo = testo.replace("evento recente:", " ")
    testo = testo.replace("interazione_utente", " ")

    camminando = "sto camminando" in testo
    fermo = "sono fermo" in testo

    ha_batteria_bassa = False
    ha_batteria_critica = False

    try:
        match_batteria = re.search(r"batteria.*?(\d+)%", testo)
        if match_batteria:
            batteria_valore = int(match_batteria.group(1))
            ha_batteria_bassa = batteria_valore <= 25
            ha_batteria_critica = batteria_valore <= 15
    except Exception:
        ha_batteria_bassa = False
        ha_batteria_critica = False

    ha_carezza = "carezza" in testo and "testa" in testo
    ha_mano_sx = "mano sinistra" in testo
    ha_mano_dx = "mano destra" in testo
    ha_entrambe_mani = "entrambe le mani" in testo
    ha_evento_tattile_umano = (
        ha_carezza or
        ha_mano_sx or
        ha_mano_dx or
        ha_entrambe_mani
    )
    ha_volto_noto = "riconosco" in testo
    ha_volto_ignoto = "volto ignoto" in testo
    ha_oggetto_vicino = "vedo qualcosa vicino" in testo or "qualcosa vicino" in testo
    ha_ostacolo_sx = (
        "ostacolo a sinistra" in testo or
        ("urto tattile" in testo and "sinistra" in testo) or
        (
            "qualcosa" in testo and
            "sinistra" in testo and
            not (fermo and ha_evento_tattile_umano)
        )
    )
    ha_ostacolo_dx = (
        "ostacolo a destra" in testo or
        ("urto tattile" in testo and "destra" in testo) or
        (
            "qualcosa" in testo and
            "destra" in testo and
            not (fermo and ha_evento_tattile_umano)
        )
    )
    ha_urto_piede_sx = "piede sinistro" in testo
    ha_urto_piede_dx = "piede destro" in testo
    ha_urto_piedi = (
        "ostacolo frontale ai piedi" in testo or
        ("urto tattile" in testo and "pied" in testo) or
        (ha_urto_piede_sx and ha_urto_piede_dx)
    )

    ha_rumore_improvviso = "rumore improvviso" in testo or "suono improvviso" in testo
    ha_rumore_singolo = "rumore singolo" in testo or "colpo" in testo
    ha_battiti = "battiti" in testo or "battito" in testo

    if ha_batteria_critica and ha_volto_noto:
        return "batteria_critica_e_volto_riconosciuto"

    if ha_batteria_bassa and ha_volto_noto:
        return "batteria_bassa_e_volto_riconosciuto"
    
    # COMBINAZIONI CON CAMMINO
    # Queste hanno priorita' assoluta per sicurezza.
    if camminando and ha_carezza:
        return "carezza_durante_cammino"

    if camminando and ha_mano_sx:
        return "mano_sinistra_durante_cammino"

    if camminando and ha_mano_dx:
        return "mano_destra_durante_cammino"

    if camminando and ha_volto_noto:
        return "volto_riconosciuto_durante_cammino"

    if camminando and ha_volto_ignoto:
        return "volto_ignoto_durante_cammino"
    
    if camminando and ha_rumore_improvviso:
        return "rumore_improvviso_durante_cammino"

    if camminando and ha_rumore_singolo:
        return "rumore_singolo_durante_cammino"

    if camminando and ha_battiti:
        return "battiti_durante_cammino"

    if camminando and ha_ostacolo_sx:
        return "ostacolo_sinistra_durante_cammino"

    if camminando and ha_ostacolo_dx:
        return "ostacolo_destra_durante_cammino"

    if camminando and ha_urto_piede_sx:
        return "piede_sinistro_durante_cammino"

    if camminando and ha_urto_piede_dx:
        return "piede_destro_durante_cammino"

    if camminando and ha_urto_piedi:
        return "urto_piedi_durante_cammino"
    
    # COMBINAZIONI SOCIALI / TATTILI
    # Devono stare PRIMA degli ostacoli.
    # Altrimenti "C'e' qualcosa a sinistra + carezza + mano"
    # viene classificato come ostacolo invece che come interazione sociale composta.
    if ha_carezza and ha_mano_sx:
        return "carezza_e_mano_sinistra"

    if ha_carezza and ha_mano_dx:
        return "carezza_e_mano_destra"

    if ha_carezza and ha_volto_noto:
        return "carezza_e_volto_riconosciuto"

    if ha_carezza and ha_volto_ignoto:
        return "carezza_e_volto_ignoto"

    if ha_mano_sx and ha_volto_noto:
        return "mano_sinistra_e_volto_riconosciuto"

    if ha_mano_dx and ha_volto_noto:
        return "mano_destra_e_volto_riconosciuto"

    if ha_mano_sx and ha_volto_ignoto:
        return "mano_sinistra_e_volto_ignoto"

    if ha_mano_dx and ha_volto_ignoto:
        return "mano_destra_e_volto_ignoto"

    if ha_entrambe_mani:
        return "tocco_entrambe_mani"

    if ha_mano_sx and ha_mano_dx:
        return "tocco_entrambe_mani"
    
    if ha_rumore_improvviso and fermo:
        return "rumore_improvviso_fermo"

    if ha_rumore_singolo and fermo:
        return "rumore_singolo_fermo"

    if ha_battiti and fermo:
        return "battiti_fermo"

    # COMBINAZIONI OSTACOLI / SPAZIO
    # Dopo i casi sociali.
    if ha_ostacolo_sx and ha_ostacolo_dx:
        return "ostacoli_sinistra_e_destra"

    # CASI SINGOLI
    if ha_carezza:
        return "carezza_testa"

    if ha_entrambe_mani:
        return "tocco_entrambe_mani"
    
    if ha_mano_sx:
        return "tocco_mano_sinistra"

    if ha_mano_dx:
        return "tocco_mano_destra"

    if ha_volto_noto:
        return "volto_riconosciuto"

    if ha_volto_ignoto:
        return "volto_ignoto"

    if ha_oggetto_vicino:
        return "oggetto_vicino"

    if ha_ostacolo_sx:
        return "ostacolo_sinistra"

    if ha_ostacolo_dx:
        return "ostacolo_destra"

    if ha_urto_piedi:
        return "urto_piedi"
    
    if ha_urto_piede_sx:
        return "piede_sinistro"

    if ha_urto_piede_dx:
        return "piede_destro"

    if "pericolo caduta" in testo or "sollevamento" in testo or "pavimento mancante" in testo:
        return "pericolo_caduta"

    if "battiti di mani" in testo or "battito" in testo:
        return "battito_mani"

    if "prendi l'iniziativa" in testo or "prendi l iniziativa" in testo:
        return "curiosita_dinamica"

    # 4) FALLBACK
    testo = testo_originale
    testo = testo.replace("report:", " ")
    testo = testo.replace("interazione_utente", " ")
    testo = testo.replace("sono fermo", " ")
    testo = testo.replace("sto camminando", " ")

    testo = re.sub(r"[^a-z0-9àèéìòù_ ]+", " ", testo)
    testo = re.sub(r"\s+", " ", testo).strip()

    parole_vietate = [
        "report", "sono", "fermo", "sto", "camminando",
        "interazione", "utente", "mia", "mio",
        "evento", "recente", "recenti",
        "sento", "vedo", "rilevo",
        "destra", "sinistra",
        "la", "il", "lo", "gli", "le",
        "un", "una", "di", "a", "da", "in", "con", "per",
        "che", "sulla", "sullo", "sul",
        "del", "della", "dei", "degli", "delle",
        "qualcosa"
    ]
    parole_utili = []

    for parola in testo.split(" "):
        parola = parola.strip("_ ").lower()

        if len(parola) < 4:
            continue

        if parola in parole_vietate:
            continue

        if parola not in parole_utili:
            parole_utili.append(parola)

    if not parole_utili:
        return "generica"

    return "_".join(parole_utili[:3])


def _estrai_codice_python(testo):
    testo = testo.strip()

    if "```python" in testo:
        testo = testo.split("```python", 1)[1]
        testo = testo.split("```", 1)[0]

    elif "```" in testo:
        testo = testo.split("```", 1)[1]
        testo = testo.split("```", 1)[0]

    return testo.strip()

def _normalizza_testo_trigger(testo):
    testo = testo.lower()
    testo = testo.replace("report:", " ")
    testo = testo.replace("interazione_utente", " ")
    testo = testo.replace("sono fermo", " ")
    testo = testo.replace("sto camminando", " ")
    testo = re.sub(r"[^a-z0-9àèéìòù_ ]+", " ", testo)
    testo = re.sub(r"\s+", " ", testo)
    return testo.strip()


def _estrai_trigger_da_mondo(mondo):
    """
    Estrae parole semplici dal mondo corrente per costruire automaticamente
    una condizione quando l'LLM genera solo comportamento().
    """
    testo = _normalizza_testo_trigger(mondo)

    parole_vietate = [
        "report",
        "sono",
        "fermo",
        "sto",
        "camminando",
        "interazione",
        "utente",
        "mia",
        "mio",
        "la",
        "il",
        "lo",
        "gli",
        "le",
        "un",
        "una",
        "di",
        "a",
        "da",
        "in",
        "con",
        "per",
        "che",
        "sulla",
        "sullo",
        "sul",
        "del",
        "della",
        "dei",
        "degli",
        "delle"
    ]

    parole = []

    for parola in testo.split(" "):
        parola = parola.strip()

        if len(parola) < 4:
            continue

        if parola in parole_vietate:
            continue

        if parola not in parole:
            parole.append(parola)

    # Limitiamo i trigger per evitare condizioni troppo larghe o troppo lunghe.
    return parole[:5]


def _costruisci_condizione_automatica(mondo):
    """
    Crea automaticamente la funzione condizione(mondo, stato_runtime)
    quando l'LLM si dimentica di generarla.
    """
    trigger = _estrai_trigger_da_mondo(mondo)

    if not trigger:
        trigger = ["interazione"]

    righe = []
    righe.append("def condizione(mondo, stato_runtime):")
    righe.append("    testo = mondo.lower()")

    controlli = []

    for parola in trigger:
        parola = parola.replace('"', "").replace("'", "")
        controlli.append('u"{}" in testo'.format(parola))

    righe.append("    return " + " and ".join(controlli))
    righe.append("")

    return "\n".join(righe)


def _contiene_funzione(codice, nome_funzione):
    pattern = r"def\s+" + re.escape(nome_funzione) + r"\s*\("
    return re.search(pattern, codice) is not None


def _aggiungi_condizione_automatica_se_manca(codice, mondo):
    """
    Se il codice generato contiene comportamento() ma non condizione(),
    aggiunge automaticamente una condizione basata sul mondo corrente.
    """
    ha_condizione = _contiene_funzione(codice, "condizione")
    ha_comportamento = _contiene_funzione(codice, "comportamento")

    if ha_condizione:
        return codice

    if not ha_comportamento:
        return codice

    logger.warning(u"[GENERATOR] LLM ha generato comportamento() senza condizione(). Creo condizione automatica.")

    intestazione = "# -*- coding: utf-8 -*-\n\n"

    codice_senza_encoding = codice.replace("# -*- coding: utf-8 -*-", "").strip()

    condizione_auto = _costruisci_condizione_automatica(mondo)

    return intestazione + condizione_auto + "\n" + codice_senza_encoding + "\n"

def _scrivi_file(path_file, contenuto):
    with open(path_file, "wb") as f:
        f.write(contenuto.encode("utf-8"))


def _leggi_file(path_file):
    with open(path_file, "rb") as f:
        return f.read().decode("utf-8")


def _codice_contiene_token_vietati(codice):
    codice_lower = codice.lower()

    for token in TOKEN_VIETATI:
        if token.lower() in codice_lower:
            return token

    return None


def _valida_struttura_codice(codice):
    token_vietato = _codice_contiene_token_vietati(codice)

    if token_vietato:
        return False, "Token vietato trovato: {}".format(token_vietato)

    try:
        if isinstance(codice, unicode):
            codice_ast = codice.encode("utf-8")
        else:
            codice_ast = codice

        albero = ast.parse(codice_ast)
    except Exception as e:
        return False, "Errore sintassi Python: {}".format(e)

    funzioni_trovate = []

    for nodo in albero.body:
        if isinstance(nodo, ast.FunctionDef):
            funzioni_trovate.append(nodo.name)
        elif isinstance(nodo, ast.Expr) and isinstance(nodo.value, ast.Str):
            continue
        else:
            return False, "Il file deve contenere solo funzioni, nessun codice eseguito fuori funzione"

    if "condizione" not in funzioni_trovate:
        return False, "Manca funzione condizione(mondo, stato_runtime)"

    if "comportamento" not in funzioni_trovate:
        return False, "Manca funzione comportamento()"

    if len(funzioni_trovate) != 2:
        return False, "Sono consentite solo due funzioni: condizione e comportamento"

    for nodo in ast.walk(albero):
        if isinstance(nodo, ast.Subscript):
            return False, "Accesso diretto con parentesi quadre vietato: usare .get()"
        
        if isinstance(nodo, (ast.Import, ast.ImportFrom)):
            return False, "Import vietato"

        if isinstance(nodo, ast.Global):
            return False, "Uso di global vietato"

        if isinstance(nodo, ast.Lambda):
            return False, "Lambda vietata"

        if isinstance(nodo, ast.ClassDef):
            return False, "Classi vietate"

        if isinstance(nodo, ast.While):
            return False, "While vietato"

        if isinstance(nodo, ast.For):
            return False, "For vietato"

        if hasattr(ast, "Try") and isinstance(nodo, ast.Try):
            return False, "Try/except vietato"

        if hasattr(ast, "TryExcept") and isinstance(nodo, ast.TryExcept):
            return False, "Try/except vietato"

        if hasattr(ast, "TryFinally") and isinstance(nodo, ast.TryFinally):
            return False, "Try/finally vietato"

        if isinstance(nodo, ast.With):
            return False, "With vietato"

        if isinstance(nodo, ast.Call):
            nome_chiamata = ""

            if isinstance(nodo.func, ast.Name):
                nome_chiamata = nodo.func.id

            elif isinstance(nodo.func, ast.Attribute):
                nome_chiamata = nodo.func.attr

            chiamate_permesse = [
                "lower",
                "upper",
                "strip",
                "get"
            ]

            if nome_chiamata not in chiamate_permesse:
                return False, "Chiamata funzione non consentita: {}".format(nome_chiamata)

        if isinstance(nodo, ast.Attribute):
            if nodo.attr.startswith("__"):
                return False, "Accesso ad attributo speciale vietato"

        if isinstance(nodo, ast.Name):
            if nodo.id.startswith("__"):
                return False, "Nome speciale vietato"

    return True, "ok"


def _valida_modulo_python(path_file):
    nome_modulo = os.path.basename(path_file).replace(".py", "")

    try:
        modulo = _carica_modulo_da_file(nome_modulo, path_file)

        if not hasattr(modulo, "condizione"):
            return False, "Funzione condizione assente"

        if not hasattr(modulo, "comportamento"):
            return False, "Funzione comportamento assente"

        test_mondo = u"REPORT: situazione di test. SONO FERMO."
        test_runtime = {
            "batteria": 80,
            "sta_camminando": False,
            "utente_presente": True
        }

        risultato_condizione = modulo.condizione(test_mondo, test_runtime)

        if not isinstance(risultato_condizione, bool):
            return False, "condizione() deve restituire True/False"

        comportamento = modulo.comportamento()

        if not isinstance(comportamento, dict):
            return False, "comportamento() deve restituire un dizionario"

        azioni = comportamento.get("azioni", [])

        if not isinstance(azioni, list):
            return False, "azioni deve essere una lista"

        if len(azioni) == 0:
            return False, "Il comportamento deve contenere almeno una azione"

        if len(azioni) > 4:
            return False, "Massimo 4 azioni consentite"

        ha_reazione_fisica = False

        for azione in azioni:
            if not isinstance(azione, dict):
                return False, "Ogni azione deve essere un dizionario"

            tipo = azione.get("tipo", "")

            if tipo not in AZIONI_CONSENTITE:
                return False, "Azione non consentita: {}".format(tipo)

            if tipo in ["occhi", "guarda", "posa", "fermati", "animazione"]:
                ha_reazione_fisica = True

            if tipo == "parla":
                testo = azione.get("testo", "")

                if not isinstance(testo, basestring):
                    return False, "parla.testo deve essere una stringa"

                if len(testo) > 120:
                    return False, "Testo parlato troppo lungo"

            elif tipo == "occhi":
                colore = azione.get("colore", "")

                if colore not in ["white", "red", "green", "blue", "yellow", "purple", "cyan"]:
                    return False, "Colore occhi non consentito: {}".format(colore)

            elif tipo == "guarda":
                x = azione.get("x", 0.0)
                y = azione.get("y", -0.25)

                if not isinstance(x, (int, float)):
                    return False, "guarda.x deve essere numerico"

                if not isinstance(y, (int, float)):
                    return False, "guarda.y deve essere numerico"

                if x < -1.0 or x > 1.0:
                    return False, "guarda.x fuori range"

                if y < -0.5 or y > -0.1:
                    return False, "guarda.y fuori range"

            elif tipo == "cammina":
                x = azione.get("x", 0.0)
                g = azione.get("g", 0.0)

                if not isinstance(x, (int, float)):
                    return False, "cammina.x deve essere numerico"

                if not isinstance(g, (int, float)):
                    return False, "cammina.g deve essere numerico"

                if x < -0.2 or x > 0.2:
                    return False, "cammina.x fuori range"

                if g < -0.2 or g > 0.2:
                    return False, "cammina.g fuori range"

            elif tipo == "gira":
                v = azione.get("v", 0.0)

                if not isinstance(v, (int, float)):
                    return False, "gira.v deve essere numerico"

                if v < -0.3 or v > 0.3:
                    return False, "gira.v fuori range"

            elif tipo == "posa":
                nome_posa = azione.get("nome", "")

                if nome_posa not in ["Stand", "Crouch", "Sit", "SitRelax"]:
                    return False, "Posa non consentita: {}".format(nome_posa)

            elif tipo == "animazione":
                path = azione.get("path", "")

                if not isinstance(path, basestring):
                    return False, "animazione.path deve essere una stringa"

                if not path.startswith("animations/Stand/"):
                    return False, "Path animazione non sicuro"

        if not ha_reazione_fisica:
            return False, "Il comportamento deve avere almeno una reazione fisica"

        if len(azioni) == 1 and azioni[0].get("tipo") == "parla":
            return False, "Vietato comportamento solo verbale"

        return True, "ok"

    except Exception as e:
        return False, "Errore import/test modulo: {}".format(e)

def _valida_semantica_condizione(path_file, mondo_originale, stato_runtime_originale=None):
    """
    Verifica che la condizione generata:
    - si attivi sul mondo originale;
    - non si attivi su situazioni banali;
    - non si attivi su casi simili ma diversi.
    """

    if stato_runtime_originale is None:
        stato_runtime_originale = {}

    nome_modulo = os.path.basename(path_file).replace(".py", "")

    try:
        modulo = _carica_modulo_da_file(nome_modulo + "_semantica", path_file)

        if not hasattr(modulo, "condizione"):
            return False, "Funzione condizione assente nella validazione semantica"

        eventi_originali = estrai_eventi(mondo_originale, stato_runtime_originale)
        nome_base = _slug_testo(mondo_originale)

        # Se il mondo nasce da osservazione autonoma, aggiungo anche
        # gli eventi unknown estratti dal testo visivo pulito.
        try:
            from behaviors.event_system.unknown_event_extractor import estrai_eventi_sconosciuti

            mondo_unknown = _pulisci_mondo_per_unknown(mondo_originale)
            eventi_unknown = estrai_eventi_sconosciuti(mondo_unknown)

            eventi_unknown = _normalizza_eventi_sconosciuti(
                eventi_unknown
            )

            if eventi_unknown:
                eventi_originali.update(eventi_unknown)
                nome_base = list(eventi_unknown.keys())[0]
        except Exception as e:
            logger.warning(u"[GENERATOR] Errore arricchendo runtime positivo unknown: {}".format(e))
        runtime_positivo = {
            "eventi": eventi_originali,
            "eventi_reali": eventi_originali
        }

        def _runtime_test(mondo_test, eventi_forzati=None):
            eventi_test = estrai_eventi(mondo_test, {})
            if eventi_forzati:
                eventi_test.update(eventi_forzati)

            if eventi_test.get("camminando", False):
                eventi_test["fermo"] = False

            if eventi_test.get("fermo", False):
                eventi_test["camminando"] = False

            return {
                "eventi": eventi_test,
                "eventi_reali": eventi_test
            }

        positivo = modulo.condizione(mondo_originale, runtime_positivo)

        if positivo is not True:
            return False, "La condizione non si attiva sul mondo originale"

        casi_negativi = [
            (
                u"REPORT: SONO FERMO.",
                _runtime_test(u"REPORT: SONO FERMO.")
            ),
            (
                u"REPORT: La mia batteria e' al 90%. SONO FERMO.",
                _runtime_test(u"REPORT: La mia batteria e' al 90%. SONO FERMO.")
            )
        ]

        comportamento = modulo.comportamento()
        azioni = comportamento.get("azioni", [])

        valido_azioni, motivo_azioni = _valida_semantica_azioni(
            nome_base,
            eventi_originali,
            azioni
        )

        if not valido_azioni:
            return False, motivo_azioni

        condizione_tattile = (
            "mano" in nome_base or
            "carezza" in nome_base or
            "entrambe" in nome_base
        )

        condizione_identita = (
            "volto" in nome_base or
            "riconosciuto" in nome_base or
            "ignoto" in nome_base
        )

        frasi_identita = [
            "chi sei",
            "come ti chiami",
            "non ti riconosco",
            "sei nuovo",
            "sei nuova"
        ]

        if condizione_tattile and not condizione_identita:
            for azione in azioni:
                if azione.get("tipo", "") == "parla":
                    testo_azione = azione.get("testo", "").lower()

                    for frase in frasi_identita:
                        if frase in testo_azione:
                            return False, "Frase di identita' non coerente con condizione tattile"

        condizione_sociale = (
            "carezza" in nome_base or
            "mano" in nome_base or
            "volto" in nome_base or
            "entrambe" in nome_base
        )

        mondo_spaziale = (
            not condizione_sociale and
            (
                eventi_originali.get("ostacolo_sinistra", False) or
                eventi_originali.get("ostacolo_destra", False) or
                eventi_originali.get("ostacolo_frontale", False) or
                eventi_originali.get("urto_piedi", False)
            )
        )

        frasi_sociali_non_coerenti = [
            "ciao",
            "come stai",
            "cosa stai facendo",
            "come posso aiutarti",
            "come ti senti"
        ]

        if mondo_spaziale:
            for azione in azioni:
                if azione.get("tipo", "") == "parla":
                    testo_azione = azione.get("testo", "").lower()

                    for frase in frasi_sociali_non_coerenti:
                        if frase in testo_azione:
                            return False, "Frase sociale non coerente con condizione spaziale/ostacolo"
        
        if not condizione_sociale:
            if (
                eventi_originali.get("ostacolo_sinistra", False) and
                eventi_originali.get("ostacolo_destra", False)
            ):
                mondo_solo_sinistra = u"REPORT: Ostacolo a sinistra. SONO FERMO."
                mondo_solo_destra = u"REPORT: Ostacolo a destra. SONO FERMO."

                casi_negativi.append((
                    mondo_solo_sinistra,
                    {"eventi": estrai_eventi(mondo_solo_sinistra, {})}
                ))

                casi_negativi.append((
                    mondo_solo_destra,
                    {"eventi": estrai_eventi(mondo_solo_destra, {})}
                ))

            elif eventi_originali.get("ostacolo_sinistra", False):
                mondo_invertito = u"REPORT: Ostacolo a destra. "

                if eventi_originali.get("camminando", False):
                    mondo_invertito += u"STO CAMMINANDO."
                else:
                    mondo_invertito += u"SONO FERMO."

                casi_negativi.append((
                    mondo_invertito,
                    {"eventi": estrai_eventi(mondo_invertito, {})}
                ))

            elif eventi_originali.get("ostacolo_destra", False):
                mondo_invertito = u"REPORT: Ostacolo a sinistra. "

                if eventi_originali.get("camminando", False):
                    mondo_invertito += u"STO CAMMINANDO."
                else:
                    mondo_invertito += u"SONO FERMO."

                casi_negativi.append((
                    mondo_invertito,
                    {"eventi": estrai_eventi(mondo_invertito, {})}
                ))

                if eventi_originali.get("fermo", False):
                    mondo_cammino = mondo_originale.replace("SONO FERMO", "STO CAMMINANDO").replace("sono fermo", "sto camminando")

                    casi_negativi.append((
                        mondo_cammino,
                        {"eventi": estrai_eventi(mondo_cammino, {})}
                    ))

                # Se la condizione riguarda un rumore, non deve attivarsi senza rumore.
            if (
                eventi_originali.get("rumore_improvviso", False) or
                eventi_originali.get("rumore_singolo", False) or
                eventi_originali.get("battiti_mani", False)
            ):
                mondo_senza_rumore = (
                    u"REPORT: SONO FERMO."
                    if eventi_originali.get("fermo", False)
                    else u"REPORT: STO CAMMINANDO."
                )

                casi_negativi.append((
                    mondo_senza_rumore,
                    {"eventi": estrai_eventi(mondo_senza_rumore, {})}
                ))

        if eventi_originali.get("camminando", False):
            mondo_fermo = mondo_originale.replace("STO CAMMINANDO", "SONO FERMO").replace("sto camminando", "sono fermo")

            casi_negativi.append((
                mondo_fermo,
                {"eventi": estrai_eventi(mondo_fermo, {})}
            ))


        for mondo_negativo, runtime_negativo in casi_negativi:
            risultato = modulo.condizione(mondo_negativo, runtime_negativo)

            if risultato is True:
                return False, "La condizione si attiva su caso negativo: {}".format(mondo_negativo)

        return True, "ok"

    except Exception as e:
        return False, "Errore validazione semantica: {}".format(e)

def _sposta_in_rejected(path_file, motivo):
    _assicura_cartelle()

    nome = os.path.basename(path_file)
    nuovo_nome = nome.replace(".py", "_rejected.py")
    path_rejected = os.path.join(REJECTED_DIR, nuovo_nome)

    try:
        shutil.move(path_file, path_rejected)

        motivo_path = path_rejected + ".reason.txt"

        with open(motivo_path, "wb") as f:
            f.write(motivo.encode("utf-8"))

        logger.warning(u"[GENERATOR] Condizione rifiutata: {}".format(motivo))

    except Exception as e:
        logger.warning(u"[GENERATOR] Errore spostamento rejected: {}".format(e))


def _promuovi_in_generated(path_file):
    _assicura_cartelle()

    nome = os.path.basename(path_file)
    path_finale = os.path.join(GENERATED_DIR, nome)

    if os.path.exists(path_finale):
        base, ext = os.path.splitext(nome)
        nome = "{}_{}".format(base, int(time.time())) + ext
        path_finale = os.path.join(GENERATED_DIR, nome)

    shutil.move(path_file, path_finale)
    reset_cache_condizioni()

    logger.info(u"[GENERATOR] Nuova condizione promossa: {}".format(path_finale))
    return path_finale


def _costruisci_prompt(
    mondo,
    dati_memoria,
    stato_robot,
    eventi_sconosciuti=None,
    storia_episodica=None
):

    sezione_sconosciuti = u""
    if eventi_sconosciuti:
        nome_ev = list(eventi_sconosciuti.keys())[0]
        parole_ev = nome_ev.replace("_", " e ")
        sezione_sconosciuti = (
            u"\nEVENTI SCONOSCIUTI RILEVATI:\n"
            u"Il testo del MONDO contiene concetti nuovi non presenti tra gli eventi noti del robot.\n"
            u"Devi generare una condizione specifica per questo evento: {nome_ev}\n"
            u"La funzione condizione() DEVE usare eventi.get(\"{nome_ev}\", False) oppure cercare "
            u"le parole {parole_ev} nel testo con mondo.lower().\n"
            u"Non generare una condizione generica: deve riconoscere esattamente questo concetto.\n\n"
        ).format(nome_ev=nome_ev, parole_ev=parole_ev)

    try:
        memoria_cognitiva = memoria_cognitiva_condizioni(limite=8)
    except Exception:
        memoria_cognitiva = []

    try:
        condizioni_simili = trova_condizioni_simili(
            mondo,
            eventi_sconosciuti or {},
            limite=5
        )
    except Exception:
        condizioni_simili = []

    try:
        if recupera_credenze_rilevanti is not None:
            credenze_world_model = recupera_credenze_rilevanti(
                mondo,
                {
                    "eventi_attivi": eventi_sconosciuti or {}
                },
                limite=5
            )
        else:
            credenze_world_model = []
    except Exception:
        credenze_world_model = []

    return (
        u"Sei un generatore di codice Python per un robot NAO.\n"
        u"Devi generare UNA nuova condizione Python autonoma.\n\n"

        u"REGOLE OBBLIGATORIE:\n"
        u"- La funzione condizione() DEVE usare stato_runtime.get(\"eventi\", {}).\n"
        u"- NON usare parsing fragile del testo come 'parola' in mondo, salvo curiosità visiva.\n"
        u"- Per condizioni multiple usa AND tra eventi reali.\n"
        u"- Esempio corretto:\n"
        u"  eventi = stato_runtime.get(\"eventi\", {})\n"
        u"  return eventi.get(\"rumore_improvviso\", False) and eventi.get(\"camminando\", False)\n"
        u"- Esempio sbagliato:\n"
        u"  return u\"rumore\" in mondo and u\"camminando\" in mondo\n"
        u"- Genera SOLO codice Python.\n"
        u"- Non scrivere spiegazioni.\n"
        u"- Non usare import.\n"
        u"- Non usare open, exec, eval, subprocess, socket, thread.\n"
        u"- Non chiamare direttamente NAOqi o ALProxy.\n"
        u"- Non creare loop infiniti.\n"
        u"- Il file deve contenere SOLO due funzioni:\n"
        u"  1) condizione(mondo, stato_runtime)\n"
        u"  2) comportamento()\n\n"

        u"FORMATO OBBLIGATORIO:\n"
        u"# -*- coding: utf-8 -*-\n\n"
        u"def condizione(mondo, stato_runtime):\n"
        u"    eventi = stato_runtime.get(\"eventi\", {})\n"
        u"    return eventi.get(\"nome_evento\", False)\n\n"
        u"def comportamento():\n"
        u"    return {\n"
        u"        \"stato_interno\": \"prudente/sociale/curioso/allerta/neutro\",\n"
        u"        \"obiettivo\": \"descrizione breve\",\n"
        u"        \"azioni\": [\n"
        u"            {\"tipo\": \"occhi\", \"colore\": \"yellow\"},\n"
        u"            {\"tipo\": \"guarda\", \"x\": 0.0, \"y\": -0.25},\n"
        u"            {\"tipo\": \"parla\", \"testo\": \"Frase breve e sicura.\"}\n"
        u"        ],\n"
        u"        \"memoria\": []\n"
        u"    }\n\n"

        u"AZIONI CONSENTITE:\n"
        u"- parla: risposta vocale breve\n"
        u"- guarda: orienta la testa, usa x tra -1.0 e 1.0, y tra -0.5 e -0.1 (NON usare 0.0)\n"
        u"- occhi: cambia colore occhi tra white/red/green/blue/yellow/purple/cyan\n"
        u"- animazione: usa path sicuri come animations/Stand/Gestures/Hey_1\n"
        u"- posa: usa Stand, Crouch, Sit, SitRelax\n"
        u"- fermati: arresta il movimento\n"
        u"- Evita y = 0.0 perché fa perdere il tracking del volto.\n"
        u"- cammina: solo per micro-movimenti prudenti, x tra -0.2 e 0.2, g tra -0.2 e 0.2\n"
        u"- gira: rotazione prudente, v tra -0.3 e 0.3\n\n"

        u"REGOLE SEMANTICHE PER EVENTI FUNZIONALI:\n"
        u"- Se l'evento e' elemento_ambientale_anomalo o elemento_fuori_posto: usa stato_interno 'prudente' o 'allerta', occhi yellow/red, guarda l'elemento e pronuncia una frase breve di cautela o osservazione. Non usare tono sociale.\n"
        u"- Se l'evento riguarda accesso_non_disponibile o accesso_o_percorso_limitato: usa prudenza, occhi red/yellow, guarda verso l'accesso/percorso e NON proporre esplorazione immediata.\n"
        u"- Se l'evento riguarda accesso_disponibile: usa curiosita' controllata, occhi green/yellow, guarda verso l'accesso e proponi esplorazione cauta.\n"
        u"- Se l'evento riguarda informazione_operativa: usa stato_interno 'attento', occhi blue/yellow, guarda il contenuto e memorizza/considera l'informazione. Non generare allerta rossa.\n"
        u"- Se l'evento riguarda contenuto_informativo_rilevante o contenuto_testuale_da_approfondire: usa curiosita' o attenzione, occhi blue/yellow, osserva meglio.\n"
        u"- Se l'evento riguarda vincolo_comportamentale: usa prudenza, occhi red/yellow e frase che indichi rispetto del vincolo.\n"
        u"- Se l'evento riguarda oggetto_in_zona_rilevante: usa prudenza spaziale, occhi yellow/red, guarda l'elemento e non camminare se il robot e' fermo.\n"
        u"- Non nominare oggetti specifici se non sono presenti nel MONDO. Ragiona sulla funzione dell'evento.\n"
        u"- Non trasformare eventi cognitivi in saluti o dialogo sociale.\n\n"

        u"MEMORIA COGNITIVA DELLE CONDIZIONI ESISTENTI:\n"
        u"- Usa questa memoria per capire quali famiglie di situazioni NAO ha gia' appreso.\n"
        u"- Non copiare vecchi comportamenti in modo cieco.\n"
        u"- Se una categoria simile esiste gia', genera solo se il nuovo evento e' semanticamente diverso o piu' specifico.\n"
        u"- Le riparazioni e i rifiuti indicano cautela: preferisci condizioni piu' strette e azioni piu' prudenti.\n"
        + json.dumps(memoria_cognitiva, ensure_ascii=False)
        + u"\n\n"

        u"CONDIZIONI SIMILI RICHIAMATE DALLA MEMORIA:\n"
        u"- Usa questi richiami per evitare duplicati semantici.\n"
        u"- Se una condizione simile ha esempi negativi, restringi il trigger e scegli azioni prudenti.\n"
        u"- Se la somiglianza e' alta ma il nuovo evento e' diverso, genera una condizione piu' specifica.\n"
        + json.dumps(condizioni_simili, ensure_ascii=False)
        + u"\n\n"

        u"CREDENZE RILEVANTI DEL WORLD MODEL:\n"
        u"- Usa queste credenze per capire se l'entita' osservata ha uno stato abituale noto.\n"
        u"- Se stato_corrente differisce da stato_normale ed e' marcato come anomalia, genera un comportamento prudente o attento.\n"
        u"- Se l'anomalia riguarda informazione_rilevante, usa stato_interno 'attento', occhi blue/yellow, guarda il contenuto e memorizza/considera l'informazione. Non usare curiosita' generica.\n"
        u"- Se l'anomalia riguarda accesso non_disponibile rispetto a uno stato normale disponibile, usa prudenza, occhi red/yellow e non proporre esplorazione immediata.\n"
        u"- Se la credenza e' familiare e non anomala, evita di trattarla come novita'.\n"
        u"- Non inventare entita' o stati non presenti in MONDO o nel world model.\n"
        + json.dumps(credenze_world_model, ensure_ascii=False)
        + u"\n\n"

        u"STORIA EPISODICA CHE HA PORTATO ALLA GENERAZIONE:\n"
        u"- Se presente, questa e' l'evidenza accumulata prima di rendere stabile la condizione.\n"
        u"- Usa conferme, smentite ed esempi per generare una condizione stretta e generalizzabile.\n"
        + json.dumps(storia_episodica or {}, ensure_ascii=False)
        + u"\n\n"

        u"REGOLE PER COMPORTAMENTO AUTONOMO:\n"
        u"- Il comportamento NON deve essere solo verbale, salvo casi banali.\n"
        u"- Combina almeno 2 azioni quando possibile: occhi + guarda + parla, oppure fermati + guarda + parla.\n"
        u"- Per interazioni sociali positive, usa occhi verdi/cyan, guarda verso la persona e rispondi con tono amichevole.\n"
        u"- Per ostacoli frontali o laterali durante il cammino, NON fermarti subito: prova prima una micro-schivata prudente.\n"
        u"- Usa occhi rossi/gialli, guarda verso l'ostacolo e pronuncia una frase breve di allerta.\n"
        u"- Se ostacolo a destra durante cammino: usa cammina con x almeno 0.12 e g positivo, esempio {\"tipo\": \"cammina\", \"x\": 0.16, \"g\": 0.12}.\n"
        u"- Se ostacolo a sinistra durante cammino: usa cammina con x almeno 0.12 e g negativo, esempio {\"tipo\": \"cammina\", \"x\": 0.16, \"g\": -0.12}.\n"
        u"- Se ostacolo frontale durante cammino: usa gira oppure una micro-correzione prudente con cammina.\n"
        u"- Usa fermati solo se c'e' urto ai piedi, pericolo/caduta, robot bloccato oppure nessuna strada libera.\n"
        u"- Non usare cammina se il robot e' fermo e non c'e' una richiesta esplicita o una situazione di evitamento.\n"
        u"- Non usare gira/cammina per eventi sociali come carezza o volto.\n"
        u"- Se l'evento e' tocco mano o carezza durante cammino, NON trattarlo come ostacolo.\n"
        u"- Per tocco mano durante cammino: guarda verso la mano, usa occhi verdi/cyan e rispondi socialmente.\n"
        u"- Per tocco mano o carezza durante cammino, NON usare cammina/gira e NON cambiare traiettoria.\n"
        u"- Per eventi tattili umani (mano sinistra, mano destra, carezza, entrambe le mani), usa frasi coerenti col contatto fisico.\n"
        u"- Esempi validi: 'Ho sentito un tocco sulla mano sinistra', 'Ti ho sentito', 'Che bello sentirti vicino', 'Ho percepito la tua mano'.\n"
        u"- NON usare frasi di identita' ('chi sei', 'come ti chiami', 'sei nuovo', 'non ti riconosco') per eventi tattili senza volto.\n"
        u"- Se non e' presente un volto, NON assumere che ci sia una persona davanti.\n"
        u"- Per tocco mano: guarda verso la mano e usa occhi verdi/cyan.\n"
        u"- Usa cammina/gira solo per ostacoli reali, urti ai piedi o pericolo.\n"
        u"- Massimo 4 azioni.\n"
        u"- Vietato generare un comportamento con una sola azione di tipo parla.\n"
        u"- Ogni comportamento deve contenere almeno una reazione fisica: occhi, guarda, posa, fermati o animazione.\n\n"

        u"\nGESTIONE CURIOSITÀ:\n"
        u"- Se MONDO contiene 'PRENDI L'INIZIATIVA', stai osservando una scena reale tramite immagine.\n"
        u"- In questo caso puoi creare una nuova condizione di curiosità riutilizzabile.\n"
        u"- La condizione NON deve dipendere da 'PRENDI L'INIZIATIVA'.\n"
        u"- Deve invece attivarsi su dettagli visivi concreti (oggetti, ambienti, persone).\n"
        u"- Usa mondo.lower() e cerca parole chiave.\n"
        u"- Esempio corretto:\n"
        u"  testo = mondo.lower()\n"
        u"  return u\"armadio\" in testo or u\"foto\" in testo\n"
        u"- Esempio sbagliato:\n"
        u"  return u\"PRENDI L'INIZIATIVA\" in mondo\n"
        u"- Il comportamento deve essere curioso ma semplice, non complesso.\n\n"

        + sezione_sconosciuti

        + u"MONDO ATTUALE:\n"
        + mondo
        + u"\n\nMEMORIA:\n"
        + json.dumps(dati_memoria, ensure_ascii=False)
        + u"\n\nSTATO ROBOT:\n"
        + json.dumps(stato_robot, ensure_ascii=False)
    )


def _chiama_llm_codice(
    mondo,
    dati_memoria,
    stato_robot,
    chiave_privata,
    eventi_sconosciuti=None,
    storia_episodica=None
):
    area = "GENERAZIONE_CODICE"
    _log_richiesta_llm(
        area,
        chiave_privata,
        OPENAI_CHAT_COMPLETIONS_ENDPOINT,
        OPENAI_MODEL_GENERATORE
    )

    if not _llm_disponibile(chiave_privata):
        _log_fallback(area, "LLM non disponibile prima della richiesta")
        raise Exception("LLM non disponibile")

    prompt = _costruisci_prompt(
        mondo,
        dati_memoria,
        stato_robot,
        eventi_sconosciuti,
        storia_episodica=storia_episodica
    )

    payload = {
        "model": OPENAI_MODEL_GENERATORE,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": mondo}
        ],
        "temperature": 0.1,
        "max_tokens": 700
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + chiave_privata
    }

    _log_richiesta_inviata(area)
    res = requests.post(
        OPENAI_CHAT_COMPLETIONS_ENDPOINT,
        headers=headers,
        data=json.dumps(payload),
        timeout=10
    )

    if res.status_code != 200:
        if _marca_llm_non_disponibile(res.text):
            _log_fallback(area, "API key assente o invalida")
            raise Exception("LLM non disponibile")
        _log_fallback(area, "HTTP {}".format(res.status_code))
        raise Exception("Errore HTTP LLM: {}".format(res.text))

    return res.json()["choices"][0]["message"]["content"]

def valuta_se_generare_condizione(mondo, ultima_decisione, dati_memoria, stato_robot, chiave_privata):
    """
    Decide se creare una nuova condizione Python autonoma.

    Prima controlla eventi e combinazioni utili in modo deterministico.
    Poi, solo se serve, chiede al supervisore LLM.
    """

    area = "VALUTAZIONE_GENERAZIONE"
    _log_richiesta_llm(
        area,
        chiave_privata,
        OPENAI_CHAT_COMPLETIONS_ENDPOINT,
        OPENAI_MODEL_GENERATORE
    )

    if not _llm_disponibile(chiave_privata):
        _log_fallback(area, "LLM non disponibile prima della richiesta")
        return False

    try:
        testo_mondo = mondo.lower()
    except:
        testo_mondo = ""

    # Osservazione autonoma/visiva:
    # NON generiamo una condizione su "PRENDI L'INIZIATIVA",
    # ma possiamo generare condizioni su dettagli visivi concreti
    # emersi dall'immagine: zaino, porta chiusa, muro rotto, sedia spostata, ecc.
    osservazione_autonoma = (
        "prendi l'iniziativa" in testo_mondo or
        "prendi l iniziativa" in testo_mondo or
        "osservazione_autonoma" in testo_mondo or
        "vedo:" in testo_mondo
    )

    if osservazione_autonoma:
        logger.info(u"[GENERATOR] Osservazione autonoma visiva: valuto eventi sconosciuti concreti, non il trigger di iniziativa.")

    # Eventi utili. Bastano a far partire la generazione.
    eventi_generabili = [
        "sento un tocco su entrambe le mani",
        "ostacolo frontale ai piedi",
        "urto tattile",
        "piede sinistro premuto",
        "piede destro premuto",

        "sento una carezza sulla testa",
        "sento un tocco sulla mano sinistra",
        "sento un tocco sulla mano destra",

        "vedo qualcosa vicino",
        "ostacolo frontale",
        "ostacolo a sinistra",
        "ostacolo a destra",

        "riconosco",
        "volto ignoto",

        "pericolo caduta",
        "pavimento mancante",
        "sollevamento"
    ]

    evento_rilevato = None

    for evento in eventi_generabili:
        if evento in testo_mondo:
            evento_rilevato = evento
            break

    if evento_rilevato:
        nome_base = _slug_testo(mondo)
        nome_file = "condizione_{}.py".format(nome_base)

        path_generato = os.path.join(GENERATED_DIR, nome_file)
        path_quarantena = os.path.join(QUARANTINE_DIR, nome_file)
        path_rifiutato = os.path.join(REJECTED_DIR, nome_file.replace(".py", "_rejected.py"))

        if os.path.exists(path_generato):
            logger.info(u"[GENERATOR] Condizione gia' esistente, non genero duplicato: {}".format(nome_file))
            return False

        if os.path.exists(path_quarantena):
            logger.info(u"[GENERATOR] Condizione gia' in quarantena, non genero duplicato: {}".format(nome_file))
            return False

        if os.path.exists(path_rifiutato):
            logger.warning(u"[GENERATOR] Esiste una vecchia condizione rifiutata, ma posso rigenerarla dopo correzione validatore: {}".format(nome_file))

        logger.info(u"[GENERATOR] Evento utile rilevato, genero condizione: {} -> {}".format(
            evento_rilevato,
            nome_file
        ))
        return True
    
        # EVENTI UNKNOWN AUTONOMI
    if evento_rilevato is None:
        try:
            from behaviors.event_system.unknown_event_extractor import (
                estrai_eventi_sconosciuti
            )

            mondo_unknown = _pulisci_mondo_per_unknown(
                mondo
            )

            eventi_unknown = estrai_eventi_sconosciuti(
                mondo_unknown
            )

            eventi_unknown = (
                _normalizza_eventi_sconosciuti(
                    eventi_unknown
                )
            )

            if eventi_unknown:

                nome_evento = list(
                    eventi_unknown.keys()
                )[0]

                nome_file = (
                    "condizione_{}.py"
                    .format(nome_evento)
                )

                path_generato = os.path.join(
                    GENERATED_DIR,
                    nome_file
                )

                path_quarantena = os.path.join(
                    QUARANTINE_DIR,
                    nome_file
                )

                if (
                    not os.path.exists(path_generato)
                    and
                    not os.path.exists(path_quarantena)
                ):

                    logger.info(
                        u"[GENERATOR] Evento unknown significativo rilevato: {} -> genero condizione".format(
                            nome_evento
                        )
                    )

                    return True

        except Exception as e:
            logger.warning(
                u"[GENERATOR] Errore valutazione unknown: {}".format(e)
            )

    try:
        memoria_cognitiva = memoria_cognitiva_condizioni(limite=8)
    except Exception:
        memoria_cognitiva = []

    try:
        condizioni_simili = trova_condizioni_simili(
            mondo,
            {},
            limite=5
        )
    except Exception:
        condizioni_simili = []

    prompt = (
        u"Sei il supervisore cognitivo di un robot NAO.\n"
        u"Devi decidere se la situazione osservata merita la creazione di una NUOVA condizione Python autonoma.\n\n"

        u"Rispondi SOLO con JSON valido nel formato:\n"
        u"{\"genera\": true/false, \"motivo\": \"breve spiegazione\"}\n\n"

        u"Devi rispondere true solo se:\n"
        u"- nessuna condizione già nota sembra coprire bene la situazione;\n"
        u"- la situazione è utile e generalizzabile;\n"
        u"- il comportamento può essere riutilizzato in futuro;\n"
        u"- la situazione combina più eventi sensoriali utili, per esempio volto + tocco, volto + carezza, cammino + ostacolo.\n\n"

        u"Devi rispondere false se:\n"
        u"- è solo batteria, stato fermo/cammino o informazione banale;\n"
        u"- riguarda un input diretto dell'utente non riutilizzabile;\n"
        u"- la memoria cognitiva mostra gia' una condizione semanticamente equivalente;\n"
        u"- la decisione corrente è già adeguata e non c'è nulla di nuovo da apprendere.\n\n"

        u"MONDO:\n"
        + mondo +
        u"\n\nULTIMA DECISIONE:\n"
        + json.dumps(ultima_decisione, ensure_ascii=False) +
        u"\n\nMEMORIA COGNITIVA CONDIZIONI:\n"
        + json.dumps(memoria_cognitiva, ensure_ascii=False) +
        u"\n\nCONDIZIONI SIMILI RICHIAMATE:\n"
        + json.dumps(condizioni_simili, ensure_ascii=False) +
        u"\n\nMEMORIA:\n"
        + json.dumps(dati_memoria, ensure_ascii=False) +
        u"\n\nSTATO ROBOT:\n"
        + json.dumps(stato_robot, ensure_ascii=False)
    )

    payload = {
        "model": OPENAI_MODEL_GENERATORE,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": mondo}
        ],
        "temperature": 0.0,
        "max_tokens": 120
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + chiave_privata
    }

    try:
        _log_richiesta_inviata(area)
        res = requests.post(
            OPENAI_CHAT_COMPLETIONS_ENDPOINT,
            headers=headers,
            data=json.dumps(payload),
            timeout=8
        )

        if res.status_code != 200:
            if _marca_llm_non_disponibile(res.text):
                _log_fallback(area, "API key assente o invalida")
                return False
            logger.warning(u"[GENERATOR] Errore HTTP valutazione: {}".format(res.text))
            _log_fallback(area, "HTTP {}".format(res.status_code))
            return False

        risposta = res.json()["choices"][0]["message"]["content"].strip()
        risposta = risposta.replace("```json", "").replace("```", "").strip()

        dati = json.loads(risposta)

        genera = dati.get("genera", False)
        motivo = dati.get("motivo", "")

        logger.info(u"[GENERATOR] Valutazione generazione: {} - {}".format(
            genera,
            motivo
        ))

        return bool(genera)

    except Exception as e:
        logger.warning(u"[GENERATOR] Errore valutazione generazione: {}".format(e))
        return False
    
def _costruisci_condizione_specifica_da_slug(nome_base):
    """
    Costruisce automaticamente una condizione precisa in base al tipo di evento.
    Serve per evitare trigger troppo generici come:
    interazione, interazione_utente, sono fermo, report.
    """

    righe = []
    righe.append("def condizione(mondo, stato_runtime):")
    righe.append("    testo = mondo.lower()")


    # COMBINAZIONI OSTACOLI / SPAZIO
    if nome_base == "ostacoli_sinistra_e_destra":
        righe.append('    eventi = stato_runtime.get("eventi", {})')
        righe.append('    return eventi.get("ostacolo_sinistra", False) and eventi.get("ostacolo_destra", False)')

    elif nome_base == "batteria_bassa_e_volto_riconosciuto":
        righe.append('    eventi = stato_runtime.get("eventi", {})')
        righe.append('    return eventi.get("batteria_bassa", False) and eventi.get("volto_riconosciuto", False)')
    
    elif nome_base == "batteria_critica_e_volto_riconosciuto":
        righe.append('    eventi = stato_runtime.get("eventi", {})')
        righe.append('    return eventi.get("batteria_critica", False) and eventi.get("volto_riconosciuto", False)')

    # COMBINAZIONI DURANTE CAMMINO
    elif nome_base == "carezza_durante_cammino":
        righe.append('    eventi = stato_runtime.get("eventi", {})')
        righe.append('    return eventi.get("carezza_testa", False) and eventi.get("camminando", False)')

    elif nome_base == "mano_sinistra_durante_cammino":
        righe.append('    eventi = stato_runtime.get("eventi", {})')
        righe.append('    return eventi.get("mano_sinistra", False) and eventi.get("camminando", False)')

    elif nome_base == "mano_destra_durante_cammino":
        righe.append('    eventi = stato_runtime.get("eventi", {})')
        righe.append('    return eventi.get("mano_destra", False) and eventi.get("camminando", False)')

    elif nome_base == "volto_riconosciuto_durante_cammino":
        righe.append('    eventi = stato_runtime.get("eventi", {})')
        righe.append('    return eventi.get("volto_riconosciuto", False) and eventi.get("camminando", False)')

    elif nome_base == "volto_ignoto_durante_cammino":
        righe.append('    eventi = stato_runtime.get("eventi", {})')
        righe.append('    return eventi.get("volto_ignoto", False) and eventi.get("camminando", False)')

    elif nome_base == "oggetto_vicino_durante_cammino":
        righe.append('    eventi = stato_runtime.get("eventi", {})')
        righe.append('    return (eventi.get("oggetto_vicino", False)) and eventi.get("camminando", False)')

    elif nome_base == "ostacolo_sinistra_durante_cammino":
        righe.append('    eventi = stato_runtime.get("eventi", {})')
        righe.append('    return eventi.get("ostacolo_sinistra", False) and eventi.get("camminando", False)')

    elif nome_base == "ostacolo_destra_durante_cammino":
        righe.append('    eventi = stato_runtime.get("eventi", {})')
        righe.append('    return eventi.get("ostacolo_destra", False) and eventi.get("camminando", False)')

    elif nome_base == "ostacolo_frontale_durante_cammino":
        righe.append('    eventi = stato_runtime.get("eventi", {})')
        righe.append('    return eventi.get("ostacolo_frontale", False) and eventi.get("camminando", False)')

    elif nome_base == "urto_piedi_durante_cammino":
        righe.append('    eventi = stato_runtime.get("eventi", {})')
        righe.append('    return (eventi.get("urto_piedi", False) or eventi.get("entrambi_piedi", False)) and eventi.get("camminando", False)')

    elif nome_base == "pericolo_caduta_durante_cammino":
        righe.append('    eventi = stato_runtime.get("eventi", {})')
        righe.append('    return eventi.get("pericolo", False) and eventi.get("camminando", False)')

    # COMBINAZIONI SOCIALI / MULTI-EVENTO
    elif nome_base == "carezza_e_mano_sinistra":
        righe.append('    eventi = stato_runtime.get("eventi", {})')
        righe.append('    return eventi.get("carezza_testa", False) and eventi.get("mano_sinistra", False)')

    elif nome_base == "carezza_e_mano_destra":
        righe.append('    eventi = stato_runtime.get("eventi", {})')
        righe.append('    return eventi.get("carezza_testa", False) and eventi.get("mano_destra", False)')

    elif nome_base == "carezza_e_volto_riconosciuto":
        righe.append('    eventi = stato_runtime.get("eventi", {})')
        righe.append('    return eventi.get("carezza_testa", False) and eventi.get("volto_riconosciuto", False)')

    elif nome_base == "carezza_e_volto_ignoto":
        righe.append('    eventi = stato_runtime.get("eventi", {})')
        righe.append('    return eventi.get("carezza_testa", False) and eventi.get("volto_ignoto", False)')

    elif nome_base == "mano_sinistra_e_volto_riconosciuto":
        righe.append('    eventi = stato_runtime.get("eventi", {})')
        righe.append('    return eventi.get("mano_sinistra", False) and eventi.get("volto_riconosciuto", False)')

    elif nome_base == "mano_destra_e_volto_riconosciuto":
        righe.append('    eventi = stato_runtime.get("eventi", {})')
        righe.append('    return eventi.get("mano_destra", False) and eventi.get("volto_riconosciuto", False)')

    elif nome_base == "mano_sinistra_e_volto_ignoto":
        righe.append('    eventi = stato_runtime.get("eventi", {})')
        righe.append('    return eventi.get("mano_sinistra", False) and eventi.get("volto_ignoto", False)')

    elif nome_base == "mano_destra_e_volto_ignoto":
        righe.append('    eventi = stato_runtime.get("eventi", {})')
        righe.append('    return eventi.get("mano_destra", False) and eventi.get("volto_ignoto", False)')

    elif nome_base == "tocco_entrambe_mani":
        righe.append('    eventi = stato_runtime.get("eventi", {})')
        righe.append('    return eventi.get("entrambe_mani", False) or (eventi.get("mano_sinistra", False) and eventi.get("mano_destra", False))')
    
    elif nome_base == "rumore_improvviso_durante_cammino":
        righe.append('    eventi = stato_runtime.get("eventi", {})')
        righe.append('    return eventi.get("rumore_improvviso", False) and eventi.get("camminando", False)')

    elif nome_base == "rumore_improvviso_fermo":
        righe.append('    eventi = stato_runtime.get("eventi", {})')
        righe.append('    return eventi.get("rumore_improvviso", False) and eventi.get("fermo", False)')

    elif nome_base == "rumore_e_mano_destra":
        righe.append('    eventi = stato_runtime.get("eventi", {})')
        righe.append('    return eventi.get("rumore_improvviso", False) and eventi.get("mano_destra", False)')

    elif nome_base == "rumore_e_mano_sinistra":
        righe.append('    eventi = stato_runtime.get("eventi", {})')
        righe.append('    return eventi.get("rumore_improvviso", False) and eventi.get("mano_sinistra", False)')

    # EVENTI SINGOLI
    elif nome_base == "carezza_testa":
        righe.append('    eventi = stato_runtime.get("eventi", {})')
        righe.append('    return eventi.get("carezza_testa", False)')

    elif nome_base == "tocco_mano_sinistra":
        righe.append('    eventi = stato_runtime.get("eventi", {})')
        righe.append('    return eventi.get("mano_sinistra", False)')

    elif nome_base == "tocco_mano_destra":
        righe.append('    eventi = stato_runtime.get("eventi", {})')
        righe.append('    return eventi.get("mano_destra", False)')

    elif nome_base == "piede_sinistro":
        righe.append('    eventi = stato_runtime.get("eventi", {})')
        righe.append('    return eventi.get("piede_sinistro", False)')

    elif nome_base == "piede_destro":
        righe.append('    eventi = stato_runtime.get("eventi", {})')
        righe.append('    return eventi.get("piede_destro", False)')

    elif nome_base == "pericolo_caduta":
        righe.append('    eventi = stato_runtime.get("eventi", {})')
        righe.append('    return eventi.get("pericolo", False)')

    elif nome_base == "volto_riconosciuto":
        righe.append('    eventi = stato_runtime.get("eventi", {})')
        righe.append('    return eventi.get("volto_riconosciuto", False)')

    elif nome_base == "volto_ignoto":
        righe.append('    eventi = stato_runtime.get("eventi", {})')
        righe.append('    return eventi.get("volto_ignoto", False)')

    elif nome_base == "curiosita_dinamica":
        righe.append('    return False')

        # EVENTI SCONOSCIUTI AUTONOMI
    elif "_" in nome_base and nome_base not in [
        "generica",
        "curiosita_dinamica"
    ]:
        righe.append('    eventi = stato_runtime.get("eventi", {})')
        righe.append(
            '    return eventi.get("{}", False)'.format(nome_base)
        )

    else:
        return None

    righe.append("")
    return "\n".join(righe)

def _forza_condizione_specifica(codice, mondo, eventi_sconosciuti=None):
    """
    Sostituisce automaticamente la funzione condizione() generata dall'LLM
    con una versione più precisa, quando l'evento è riconoscibile.

    PRIORITÀ:
    1. evento sconosciuto estratto autonomamente;
    2. slug testuale per eventi noti;
    3. nessuna forzatura.
    """

    nome_base = None

    try:
        if eventi_sconosciuti:
            nome_base = list(eventi_sconosciuti.keys())[0]
    except Exception:
        nome_base = None

    if not nome_base:
        nome_base = _slug_testo(mondo)

    condizione_specifica = _costruisci_condizione_specifica_da_slug(nome_base)

    if not condizione_specifica:
        return codice

    pattern = r"def\s+condizione\s*\(\s*mondo\s*,\s*stato_runtime\s*\)\s*:.*?(?=\ndef\s+comportamento\s*\()"

    nuovo_codice, numero_sostituzioni = re.subn(
        pattern,
        condizione_specifica + "\n",
        codice,
        flags=re.DOTALL
    )

    if numero_sostituzioni > 0:
        logger.info(u"[GENERATOR] Trigger reso specifico automaticamente: {}".format(nome_base))
        return nuovo_codice

    return codice

def _pulisci_mondo_per_unknown(mondo):
    """
    Rimuove marker tecnici della curiosita autonoma.
    Gli eventi sconosciuti devono nascere dal contenuto visivo reale,
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

    if "vedo:" in testo:
        testo = testo.split("vedo:", 1)[1]

    testo = testo.replace("vedo:", " ")
    testo = testo.replace(".", " ")
    testo = " ".join(testo.split())

    return testo


def genera_condizione_autonoma(
    mondo,
    dati_memoria,
    stato_robot,
    chiave_privata,
    storia_episodica=None
):
    _assicura_cartelle()

    if not _llm_disponibile(chiave_privata):
        return None

    try:
        logger.info(u"[GENERATOR] Richiesta nuova condizione Python al LLM")

        # Pulisco il mondo solo per l'estrazione dell'evento sconosciuto.
        # Il mondo originale resta usato per prompt, validazione e metadati.
        mondo_unknown = _pulisci_mondo_per_unknown(mondo)

        eventi_sconosciuti = None

        try:
            from behaviors.event_system.unknown_event_extractor import estrai_eventi_sconosciuti
            eventi_sconosciuti = estrai_eventi_sconosciuti(
                mondo_unknown
            )

            eventi_sconosciuti = _normalizza_eventi_sconosciuti(
                eventi_sconosciuti
            )
        except Exception as e:
            logger.warning(u"[GENERATOR] Errore pre-estrazione eventi sconosciuti: {}".format(e))
            eventi_sconosciuti = None

        risposta = _chiama_llm_codice(
            mondo,
            dati_memoria,
            stato_robot,
            chiave_privata,
            eventi_sconosciuti=eventi_sconosciuti,
            storia_episodica=storia_episodica
        )

        codice = _estrai_codice_python(risposta)

        codice = _aggiungi_condizione_automatica_se_manca(codice, mondo)
        codice = _forza_condizione_specifica(
            codice,
            mondo,
            eventi_sconosciuti=eventi_sconosciuti
        )

        # Valida la condizione se è legata a un evento sconosciuto
        try:
            from behaviors.event_system.unknown_condition_validator import valida_condizione_sconosciuta
            from behaviors.event_system.unknown_event_extractor import estrai_eventi_sconosciuti

            eventi_sconosciuti = estrai_eventi_sconosciuti(
                mondo_unknown
            )

            eventi_sconosciuti = _normalizza_eventi_sconosciuti(
                eventi_sconosciuti
            )

            if eventi_sconosciuti:
                nome_ev = list(eventi_sconosciuti.keys())[0]
                valido_sconosciuto, motivo_sconosciuto = valida_condizione_sconosciuta(nome_ev, codice)

                if not valido_sconosciuto:
                    logger.warning(u"[GENERATOR] Condizione per evento sconosciuto '{}' troppo generica: {}. Ri-chiedo al LLM.".format(
                        nome_ev, motivo_sconosciuto
                    ))

                    risposta = _chiama_llm_codice(
                        mondo,
                        dati_memoria,
                        stato_robot,
                        chiave_privata,
                        eventi_sconosciuti=eventi_sconosciuti,
                        storia_episodica=storia_episodica
                    )

                    codice = _estrai_codice_python(risposta)
                    codice = _aggiungi_condizione_automatica_se_manca(codice, mondo)
                    codice = _forza_condizione_specifica(
                        codice,
                        mondo,
                        eventi_sconosciuti=eventi_sconosciuti
                    )

                    # Ri-valida dopo il retry: se ancora generica, abbandona
                    valido_retry, motivo_retry = valida_condizione_sconosciuta(nome_ev, codice)
                    if not valido_retry:
                        logger.warning(u"[GENERATOR] Anche dopo retry la condizione e' generica: {}. Abbandono.".format(
                            motivo_retry
                        ))
                        return None

        except Exception as e:
            logger.warning(u"[GENERATOR] Errore validazione sconosciuto: {}".format(e))

        nome_base = _slug_testo(mondo)

        try:
            if eventi_sconosciuti:
                nome_base = list(eventi_sconosciuti.keys())[0]
        except Exception:
            pass

        nome_file = "condizione_{}.py".format(nome_base)

        path_generato = os.path.join(GENERATED_DIR, nome_file)
        path_rifiutato = os.path.join(
            REJECTED_DIR,
            nome_file.replace(".py", "_rejected.py")
        )

        if os.path.exists(path_generato):
            logger.info(u"[GENERATOR] Condizione gia' esistente, non genero duplicato: {}".format(nome_file))
            return None

        if os.path.exists(path_rifiutato):
            logger.warning(u"[GENERATOR] Esiste una vecchia condizione rifiutata, ma posso rigenerarla dopo correzione validatore: {}".format(nome_file))

        path_quarantine = os.path.join(QUARANTINE_DIR, nome_file)

        _scrivi_file(path_quarantine, codice)

        valido, motivo = _valida_struttura_codice(codice)
        if not valido:
            _sposta_in_rejected(path_quarantine, motivo)
            return None

        valido, motivo = _valida_modulo_python(path_quarantine)
        if not valido:
            _sposta_in_rejected(path_quarantine, motivo)
            return None

        valido, motivo = _valida_semantica_condizione(
            path_quarantine,
            mondo,
            {
                "memoria": dati_memoria,
                "stato_robot": stato_robot
            }
        )

        if not valido:
            _sposta_in_rejected(path_quarantine, motivo)
            return None

        path_finale = _promuovi_in_generated(path_quarantine)

        try:
            nome_condizione = os.path.basename(path_finale).replace(".py", "")

            eventi_origine = estrai_eventi(
                mondo,
                {
                    "memoria": dati_memoria,
                    "stato_robot": stato_robot
                }
            )

            salva_metadati_condizione(
                nome_condizione,
                mondo,
                eventi_origine,
                stato_robot,
                origine="autogenerata_llm",
                storia_episodica=storia_episodica,
                motivo_cognitivo=(
                    storia_episodica or {}
                ).get("motivo_cognitivo_generazione", None)
            )

        except Exception as e:
            logger.warning(u"[GENERATOR] Condizione promossa, ma metadati non creati: {}".format(e))

        return path_finale

    except Exception as e:
        logger.warning(u"[GENERATOR] Errore generazione condizione: {}".format(e))
        return None
    
def _valida_semantica_azioni(nome_base, eventi_originali, azioni):
    tipi_azioni = []

    for azione in azioni:
        if isinstance(azione, dict):
            tipi_azioni.append(azione.get("tipo", ""))

    ha_fermati = "fermati" in tipi_azioni
    ha_cammina_o_gira = "cammina" in tipi_azioni or "gira" in tipi_azioni

    ostacolo_laterale_cammino = (
        eventi_originali.get("camminando", False) and
        (
            eventi_originali.get("ostacolo_destra", False) or
            eventi_originali.get("ostacolo_sinistra", False)
        ) and
        not eventi_originali.get("ostacolo_frontale", False) and
        not eventi_originali.get("urto_piedi", False) and
        not eventi_originali.get("pericolo", False)
    )

    ostacolo_frontale_cammino = (
        eventi_originali.get("camminando", False) and
        eventi_originali.get("ostacolo_frontale", False) and
        not eventi_originali.get("urto_piedi", False) and
        not eventi_originali.get("pericolo", False)
    )

    if ostacolo_laterale_cammino and ha_fermati:
        return False, "Ostacolo laterale durante cammino: vietato usare fermati"

    if ostacolo_laterale_cammino and not ha_cammina_o_gira:
        return False, "Ostacolo laterale durante cammino: serve micro-correzione con cammina o gira"

    if ostacolo_laterale_cammino:
        ha_schivata_valida = False

        for azione in azioni:
            if not isinstance(azione, dict):
                continue

            if azione.get("tipo") == "cammina":
                x = azione.get("x", 0.0)
                g = azione.get("g", 0.0)

                if x < 0.12:
                    return False, "Schivata troppo debole: cammina.x deve essere almeno 0.12"

                if eventi_originali.get("ostacolo_destra", False) and g <= 0.05:
                    return False, "Ostacolo a destra durante cammino: serve g positivo"

                if eventi_originali.get("ostacolo_sinistra", False) and g >= -0.05:
                    return False, "Ostacolo a sinistra durante cammino: serve g negativo"

                ha_schivata_valida = True

        if not ha_schivata_valida:
            return False, "Ostacolo laterale durante cammino: serve azione cammina con direzione valida"
    
    if ostacolo_frontale_cammino and ha_fermati:
        return False, "Ostacolo frontale durante cammino: vietato fermarsi subito, serve tentativo di schivata"
    if ostacolo_frontale_cammino and not ha_cammina_o_gira:
        return False, "Ostacolo frontale durante cammino: serve micro-schivata con cammina o gira"
    
    pericolo_reale = (
        eventi_originali.get("urto_piedi", False) or
        eventi_originali.get("pericolo", False)
    )

    if eventi_originali.get("camminando", False) and pericolo_reale and not ha_fermati:
        return False, "Pericolo/frontale/urto durante cammino: serve fermati"

    for azione in azioni:
        if not isinstance(azione, dict):
            continue

        if azione.get("tipo", "") != "parla":
            continue

        testo = azione.get("testo", "").lower()

        if eventi_originali.get("ostacolo_sinistra", False):
            if "davanti" in testo or "frontale" in testo or "destra" in testo:
                return False, "Frase non coerente: ostacolo sinistra descritto come davanti/destra"

        if eventi_originali.get("ostacolo_destra", False):
            if "davanti" in testo or "frontale" in testo or "sinistra" in testo:
                return False, "Frase non coerente: ostacolo destra descritto come davanti/sinistra"
            
    return True, "ok"

def costruisci_evento_strutturato(mondo, stato_runtime=None):
    """
    Converte il report testuale + runtime in una firma evento strutturata.

    Obiettivo:
    - ridurre dipendenza da stringhe sparse in soul.py;
    - distinguere eventi spaziali/sociali/safety;
    - preparare condizioni singole e multiple;
    - dare al supervisore una rappresentazione stabile.
    """

    if stato_runtime is None:
        stato_runtime = {}

    eventi = estrai_eventi(mondo, stato_runtime)

    tipo = "generico"
    direzione = None
    categoria = "neutra"
    gravita = "bassa"

    camminando = eventi.get("camminando", False)
    fermo = eventi.get("fermo", False)

    # Safety / pericolo
    if eventi.get("pericolo", False):
        tipo = "pericolo"
        categoria = "safety"
        gravita = "alta"

    elif eventi.get("urto_piedi", False) or eventi.get("entrambi_piedi", False):
        tipo = "urto_piedi"
        categoria = "safety"
        gravita = "alta"

    # Ostacoli spaziali
    elif eventi.get("ostacolo_frontale", False):
        tipo = "ostacolo"
        direzione = "frontale"
        categoria = "spaziale"
        gravita = "media"

    elif eventi.get("ostacolo_destra", False):
        tipo = "ostacolo"
        direzione = "destra"
        categoria = "spaziale"
        gravita = "media"

    elif eventi.get("ostacolo_sinistra", False):
        tipo = "ostacolo"
        direzione = "sinistra"
        categoria = "spaziale"
        gravita = "media"

    # Eventi sociali / tattili
    elif eventi.get("carezza_testa", False):
        tipo = "carezza"
        categoria = "sociale"
        gravita = "bassa"

    elif eventi.get("entrambe_mani", False):
        tipo = "tocco_mani"
        categoria = "sociale"
        gravita = "bassa"

    elif eventi.get("mano_sinistra", False):
        tipo = "tocco_mano"
        direzione = "sinistra"
        categoria = "sociale"
        gravita = "bassa"

    elif eventi.get("mano_destra", False):
        tipo = "tocco_mano"
        direzione = "destra"
        categoria = "sociale"
        gravita = "bassa"

    elif eventi.get("volto_riconosciuto", False):
        tipo = "volto_riconosciuto"
        categoria = "sociale"
        gravita = "bassa"

    elif eventi.get("volto_ignoto", False):
        tipo = "volto_ignoto"
        categoria = "sociale"
        gravita = "bassa"

    # Suoni / audio
    elif eventi.get("rumore_improvviso", False):
        tipo = "rumore_improvviso"
        categoria = "audio"
        gravita = "media"

    elif eventi.get("rumore_singolo", False):
        tipo = "rumore_singolo"
        categoria = "audio"
        gravita = "bassa"

    elif eventi.get("battiti_mani", False):
        tipo = "battiti_mani"
        categoria = "audio"
        gravita = "bassa"

    # Batteria
    elif eventi.get("batteria_critica", False):
        tipo = "batteria_critica"
        categoria = "sistema"
        gravita = "alta"

    elif eventi.get("batteria_bassa", False):
        tipo = "batteria_bassa"
        categoria = "sistema"
        gravita = "media"

    eventi_attivi = []

    for chiave, valore in eventi.items():
        if valore not in [None, False, "", [], {}]:
            eventi_attivi.append(chiave)

    eventi_core = []

    for chiave in eventi_attivi:
        if chiave in [
            "fermo",
            "camminando",
            "batteria_percentuale"
        ]:
            continue

        eventi_core.append(chiave)

    if "batteria_critica" in eventi_core and "batteria_bassa" in eventi_core:
        eventi_core.remove("batteria_bassa")

    evento_composto = len(eventi_core) >= 2

    if eventi.get("camminando", False) and len(eventi_core) >= 1:
        evento_composto = True

        eventi_descritti = {}

    try:
        if arricchisci_eventi_registro is not None:
            eventi_descritti = arricchisci_eventi_registro(eventi)
    except Exception:
        eventi_descritti = {}

    firma = {
        "tipo": tipo,
        "direzione": direzione,
        "categoria": categoria,
        "gravita": gravita,
        "camminando": camminando,
        "fermo": fermo,
        "durante_cammino": camminando,
        "eventi": eventi,
        "eventi_descritti": eventi_descritti,
        "eventi_attivi": eventi_attivi,
        "eventi_core": eventi_core,
        "evento_composto": evento_composto
    }

    return firma
