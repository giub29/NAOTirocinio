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
import imp
import ast

from behaviors.condition_manager import reset_cache_condizioni

logger = logging.getLogger(__name__)

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

    piede_sinistro = "piede sinistro" in testo
    piede_destro = "piede destro" in testo

    return {
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

        "ostacolo_sinistra": ("ostacolo" in testo or "qualcosa" in testo) and "sinistra" in testo,
        "ostacolo_destra": ("ostacolo" in testo or "qualcosa" in testo) and "destra" in testo,
        "ostacolo_frontale": (
            "ostacolo frontale" in testo or
            "vedo qualcosa vicino" in testo or
            "qualcosa vicino" in testo
        ),

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
    }

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

    ha_carezza = "carezza" in testo and "testa" in testo
    ha_mano_sx = "mano sinistra" in testo
    ha_mano_dx = "mano destra" in testo
    ha_entrambe_mani = "entrambe le mani" in testo
    ha_volto_noto = "riconosco" in testo
    ha_volto_ignoto = "volto ignoto" in testo
    ha_oggetto_vicino = "vedo qualcosa vicino" in testo or "qualcosa vicino" in testo
    ha_ostacolo_sx = (
        ("ostacolo" in testo or "qualcosa" in testo)
        and "sinistra" in testo
    )
    ha_ostacolo_dx = (
        ("ostacolo" in testo or "qualcosa" in testo)
        and "destra" in testo
    )
    ha_urto_piede_sx = "piede sinistro" in testo
    ha_urto_piede_dx = "piede destro" in testo
    ha_urto_piedi = (
        "ostacolo frontale ai piedi" in testo or
        "urto tattile" in testo and "pied" in testo or
        (ha_urto_piede_sx and ha_urto_piede_dx)
    )

     # COMBINAZIONI OSTACOLI / SPAZIO
    if ha_ostacolo_sx and ha_ostacolo_dx:
        return "ostacoli_sinistra_e_destra"
    
    # COMBINAZIONI CON CAMMINO
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

    if ha_mano_sx and ha_mano_dx:
        return "tocco_entrambe_mani"

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
        modulo = imp.load_source(nome_modulo, path_file)

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
        modulo = imp.load_source(nome_modulo + "_semantica", path_file)

        if not hasattr(modulo, "condizione"):
            return False, "Funzione condizione assente nella validazione semantica"

        eventi_originali = estrai_eventi(mondo_originale, stato_runtime_originale)

        runtime_positivo = {
            "eventi": eventi_originali
        }

        positivo = modulo.condizione(mondo_originale, runtime_positivo)

        if positivo is not True:
            return False, "La condizione non si attiva sul mondo originale"

        casi_negativi = [
            (
                u"REPORT: SONO FERMO.",
                {"eventi": estrai_eventi(u"REPORT: SONO FERMO.", {})}
            ),
            (
                u"REPORT: La mia batteria e' al 90%. SONO FERMO.",
                {"eventi": estrai_eventi(u"REPORT: La mia batteria e' al 90%. SONO FERMO.", {})}
            )
        ]

        testo = mondo_originale.lower()
        comportamento = modulo.comportamento()
        azioni = comportamento.get("azioni", [])

        mondo_spaziale = (
            "ostacolo" in testo or
            "qualcosa a destra" in testo or
            "qualcosa a sinistra" in testo or
            "vedo qualcosa vicino" in testo
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

        if "sinistra" in testo and "destra" in testo:
            casi_negativi.append((
                u"REPORT: C'e' qualcosa a sinistra. SONO FERMO.",
                {"eventi": estrai_eventi(u"REPORT: C'e' qualcosa a sinistra. SONO FERMO.", {})}
            ))

            casi_negativi.append((
                u"REPORT: C'e' qualcosa a destra. SONO FERMO.",
                {"eventi": estrai_eventi(u"REPORT: C'e' qualcosa a destra. SONO FERMO.", {})}
            ))

        elif "sinistra" in testo and "destra" not in testo:
            mondo_invertito = mondo_originale.replace("sinistra", "destra")
            casi_negativi.append((
                mondo_invertito,
                {"eventi": estrai_eventi(mondo_invertito, {})}
            ))

        elif "destra" in testo and "sinistra" not in testo:
            mondo_invertito = mondo_originale.replace("destra", "sinistra")
            casi_negativi.append((
                mondo_invertito,
                {"eventi": estrai_eventi(mondo_invertito, {})}
            ))

        if "sto camminando" in testo:
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


def _costruisci_prompt(mondo, dati_memoria, stato_robot):
    return (
        u"Sei un generatore di codice Python per un robot NAO.\n"
        u"Devi generare UNA nuova condizione Python autonoma.\n\n"

        u"REGOLE OBBLIGATORIE:\n"
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
        u"    return u\"testo trigger\" in mondo\n\n"
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

        u"REGOLE PER COMPORTAMENTO AUTONOMO:\n"
        u"- Il comportamento NON deve essere solo verbale, salvo casi banali.\n"
        u"- Combina almeno 2 azioni quando possibile: occhi + guarda + parla, oppure fermati + guarda + parla.\n"
        u"- Per interazioni sociali positive, usa occhi verdi/cyan, guarda verso la persona e rispondi con tono amichevole.\n"
        u"- Per ostacoli o pericolo, usa fermati, occhi gialli/rossi, guarda verso il lato del problema e parla.\n"
        u"- Non usare cammina se il robot è fermo e non c'è una richiesta esplicita o una situazione di evitamento.\n"
        u"- Non usare gira/cammina per eventi sociali come carezza o volto.\n"
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

        u"MONDO ATTUALE:\n"
        + mondo +
        u"\n\nMEMORIA:\n"
        + json.dumps(dati_memoria, ensure_ascii=False) +
        u"\n\nSTATO ROBOT:\n"
        + json.dumps(stato_robot, ensure_ascii=False)
    )


def _chiama_llm_codice(mondo, dati_memoria, stato_robot, chiave_privata):
    prompt = _costruisci_prompt(mondo, dati_memoria, stato_robot)

    payload = {
        "model": "gpt-4o-mini",
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

    res = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers=headers,
        data=json.dumps(payload),
        timeout=10
    )

    if res.status_code != 200:
        raise Exception("Errore HTTP LLM: {}".format(res.text))

    return res.json()["choices"][0]["message"]["content"]

def valuta_se_generare_condizione(mondo, ultima_decisione, dati_memoria, stato_robot, chiave_privata):
    """
    Decide se creare una nuova condizione Python autonoma.

    Prima controlla eventi e combinazioni utili in modo deterministico.
    Poi, solo se serve, chiede al supervisore LLM.
    """

    if not chiave_privata:
        logger.warning(u"[GENERATOR] OPENAI_API_KEY assente. Non posso valutare generazione.")
        return False

    try:
        testo_mondo = mondo.lower()
    except:
        testo_mondo = ""

    # Non generiamo condizioni statiche dalla curiosità dinamica.
    if "prendi l'iniziativa" in testo_mondo or "prendi l iniziativa" in testo_mondo:
        logger.info(u"[GENERATOR] Curiosita visiva dinamica: non genero condizione statica.")
        return False

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
            logger.info(u"[GENERATOR] Condizione gia' rifiutata in passato, non rigenero: {}".format(nome_file))
            return False

        logger.info(u"[GENERATOR] Evento utile rilevato, genero condizione: {} -> {}".format(
            evento_rilevato,
            nome_file
        ))
        return True

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
        u"- la decisione corrente è già adeguata e non c'è nulla di nuovo da apprendere.\n\n"

        u"MONDO:\n"
        + mondo +
        u"\n\nULTIMA DECISIONE:\n"
        + json.dumps(ultima_decisione, ensure_ascii=False) +
        u"\n\nMEMORIA:\n"
        + json.dumps(dati_memoria, ensure_ascii=False) +
        u"\n\nSTATO ROBOT:\n"
        + json.dumps(stato_robot, ensure_ascii=False)
    )

    payload = {
        "model": "gpt-4o-mini",
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
        res = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            data=json.dumps(payload),
            timeout=8
        )

        if res.status_code != 200:
            logger.warning(u"[GENERATOR] Errore HTTP valutazione: {}".format(res.text))
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

    # COMBINAZIONI DURANTE CAMMINO
    elif nome_base == "carezza_durante_cammino":
        righe.append('    return u"carezza" in testo and u"testa" in testo and u"sto camminando" in testo')

    elif nome_base == "mano_sinistra_durante_cammino":
        righe.append('    return u"mano sinistra" in testo and u"sto camminando" in testo')

    elif nome_base == "mano_destra_durante_cammino":
        righe.append('    return u"mano destra" in testo and u"sto camminando" in testo')

    elif nome_base == "volto_riconosciuto_durante_cammino":
        righe.append('    return u"riconosco" in testo and u"sto camminando" in testo')

    elif nome_base == "volto_ignoto_durante_cammino":
        righe.append('    return u"volto ignoto" in testo and u"sto camminando" in testo')

    elif nome_base == "oggetto_vicino_durante_cammino":
        righe.append('    return (u"vedo qualcosa vicino" in testo or u"qualcosa vicino" in testo) and u"sto camminando" in testo')

    elif nome_base == "ostacolo_sinistra_durante_cammino":
        righe.append('    return u"ostacolo" in testo and u"sinistra" in testo and u"sto camminando" in testo')

    elif nome_base == "ostacolo_destra_durante_cammino":
        righe.append('    return u"ostacolo" in testo and u"destra" in testo and u"sto camminando" in testo')

    elif nome_base == "ostacolo_frontale_durante_cammino":
        righe.append('    return (u"ostacolo frontale" in testo or u"qualcosa davanti" in testo) and u"sto camminando" in testo')

    elif nome_base == "urto_piedi_durante_cammino":
        righe.append('    eventi = stato_runtime.get("eventi", {})')
        righe.append('    return (eventi.get("urto_piedi", False) or eventi.get("entrambi_piedi", False)) and eventi.get("camminando", False)')

    elif nome_base == "pericolo_caduta_durante_cammino":
        righe.append('    return (u"pericolo caduta" in testo or u"sollevamento" in testo or u"pavimento mancante" in testo) and u"sto camminando" in testo')

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

    # EVENTI SINGOLI
    elif nome_base == "carezza_testa":
        righe.append('    return u"carezza" in testo and u"testa" in testo')

    elif nome_base == "tocco_mano_sinistra":
        righe.append('    return u"mano sinistra" in testo')

    elif nome_base == "tocco_mano_destra":
        righe.append('    return u"mano destra" in testo')

    elif nome_base == "oggetto_vicino":
        righe.append('    return u"vedo qualcosa vicino" in testo or u"qualcosa vicino" in testo')

    elif nome_base == "ostacolo_sinistra":
        righe.append('    return u"ostacolo" in testo and u"sinistra" in testo')

    elif nome_base == "ostacolo_destra":
        righe.append('    return u"ostacolo" in testo and u"destra" in testo')

    elif nome_base == "ostacolo_frontale":
        righe.append('    return u"ostacolo frontale" in testo or u"qualcosa davanti" in testo')

    elif nome_base == "urto_piedi":
        righe.append('    eventi = stato_runtime.get("eventi", {})')
        righe.append('    return eventi.get("urto_piedi", False) or eventi.get("entrambi_piedi", False)')

    elif nome_base == "piede_sinistro":
        righe.append('    return u"piede sinistro" in testo')

    elif nome_base == "piede_destro":
        righe.append('    return u"piede destro" in testo')

    elif nome_base == "pericolo_caduta":
        righe.append('    return u"pericolo caduta" in testo or u"sollevamento" in testo or u"pavimento mancante" in testo')

    elif nome_base == "battito_mani":
        righe.append('    return u"battiti di mani" in testo or u"battito" in testo')

    elif nome_base == "volto_riconosciuto":
        righe.append('    return u"riconosco" in testo')

    elif nome_base == "volto_ignoto":
        righe.append('    return u"volto ignoto" in testo')

    elif nome_base == "curiosita_dinamica":
        righe.append('    return False')

    else:
        return None

    righe.append("")
    return "\n".join(righe)

def _forza_condizione_specifica(codice, mondo):
    """
    Sostituisce automaticamente la funzione condizione() generata dall'LLM
    con una versione più precisa, quando l'evento è riconoscibile.

    Il comportamento resta generato dall'LLM.
    Il trigger invece viene reso sicuro e specifico dal sistema.
    """

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

def genera_condizione_autonoma(mondo, dati_memoria, stato_robot, chiave_privata):
    _assicura_cartelle()

    if not chiave_privata:
        logger.warning(u"[GENERATOR] OPENAI_API_KEY assente. Non genero condizioni.")
        return None

    try:
        logger.info(u"[GENERATOR] Richiesta nuova condizione Python al LLM")

        risposta = _chiama_llm_codice(
            mondo,
            dati_memoria,
            stato_robot,
            chiave_privata
        )

        codice = _estrai_codice_python(risposta)

        # AUTORIPARAZIONE:
        # Se l'LLM genera solo comportamento(), il sistema aggiunge da solo
        # la funzione condizione(mondo, stato_runtime).
        codice = _aggiungi_condizione_automatica_se_manca(codice, mondo)

        # SICUREZZA SEMANTICA:
        # Il comportamento resta generato dall'LLM,
        # ma il trigger viene reso specifico automaticamente.
        codice = _forza_condizione_specifica(codice, mondo)

        nome_base = _slug_testo(mondo)
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
            logger.info(u"[GENERATOR] Condizione gia' rifiutata in passato, non rigenero: {}".format(nome_file))
            return None

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

        return _promuovi_in_generated(path_quarantine)

    except Exception as e:
        logger.warning(u"[GENERATOR] Errore generazione condizione: {}".format(e))
        return None