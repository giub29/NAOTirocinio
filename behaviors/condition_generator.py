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


def _assicura_cartelle():
    for cartella in [QUARANTINE_DIR, GENERATED_DIR, REJECTED_DIR]:
        if not os.path.exists(cartella):
            os.makedirs(cartella)


def _slug_testo(testo):
    testo = testo.lower()
    testo = re.sub(r"[^a-z0-9_]+", "_", testo)
    testo = re.sub(r"_+", "_", testo)
    testo = testo.strip("_")

    if not testo:
        testo = "condizione_generata"

    return testo[:50]


def _estrai_codice_python(testo):
    testo = testo.strip()

    if "```python" in testo:
        testo = testo.split("```python", 1)[1]
        testo = testo.split("```", 1)[0]

    elif "```" in testo:
        testo = testo.split("```", 1)[1]
        testo = testo.split("```", 1)[0]

    return testo.strip()


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

        if isinstance(nodo, ast.Try):
            return False, "Try/except vietato"

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
    if not chiave_privata:
        logger.warning(u"[GENERATOR] OPENAI_API_KEY assente. Non posso valutare generazione.")
        return False

    prompt = (
        u"Sei il supervisore cognitivo di un robot NAO.\n"
        u"Devi decidere se la situazione osservata merita la creazione di una NUOVA condizione Python autonoma.\n\n"

        u"Rispondi SOLO con JSON valido nel formato:\n"
        u"{\"genera\": true/false, \"motivo\": \"breve spiegazione\"}\n\n"

        u"Devi rispondere true solo se:\n"
        u"- nessuna condizione già nota sembra coprire bene la situazione;\n"
        u"- la situazione è utile e generalizzabile;\n"
        u"- il comportamento può essere riutilizzato in futuro.\n\n"

        u"Devi rispondere false se:\n"
        u"- è solo batteria, stato fermo/cammino o informazione banale;\n"
        u"- riguarda riconoscimento volto già gestito;\n"
        u"- è un input diretto dell'utente;\n"
        u"- la decisione corrente è già adeguata.\n\n"

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

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        nome_base = _slug_testo(mondo)
        nome_file = "condizione_{}_{}.py".format(nome_base, timestamp)

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

        return _promuovi_in_generated(path_quarantine)

    except Exception as e:
        logger.warning(u"[GENERATOR] Errore generazione condizione: {}".format(e))
        return None