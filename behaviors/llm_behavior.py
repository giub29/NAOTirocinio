# -*- coding: utf-8 -*-
import requests
import json

try:
    unicode
except NameError:
    unicode = str

LLM_NON_DISPONIBILE = False
LLM_NON_DISPONIBILE_LOGGATO = False


def _llm_disponibile(chiave_privata):
    global LLM_NON_DISPONIBILE_LOGGATO

    if LLM_NON_DISPONIBILE or not chiave_privata:
        if not LLM_NON_DISPONIBILE_LOGGATO:
            print(u"[LLM] LLM non disponibile: chiave OpenAI assente o invalida")
            LLM_NON_DISPONIBILE_LOGGATO = True
        return False

    return True


def _marca_llm_non_disponibile(dati=None):
    global LLM_NON_DISPONIBILE
    global LLM_NON_DISPONIBILE_LOGGATO

    testo = u""
    try:
        testo = json.dumps(dati or {})
    except Exception:
        testo = unicode(dati or "")

    if "invalid_api_key" in testo or "Incorrect API key" in testo or "401" in testo:
        LLM_NON_DISPONIBILE = True
        if not LLM_NON_DISPONIBILE_LOGGATO:
            print(u"[LLM] LLM non disponibile: chiave OpenAI assente o invalida")
            LLM_NON_DISPONIBILE_LOGGATO = True
        return True

    return False


def analizza_immagine(img_b64, chiave_privata, contesto="ostacolo"):
    if not _llm_disponibile(chiave_privata):
        return u"un ambiente familiare"

    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + str(chiave_privata or "")
        }

        if contesto == "stanza":
            testo_prompt = (
                "Osserva attentamente la scena come un robot autonomo. "
                "NON limitarti a descrivere genericamente l'ambiente. "
                "Se vedi schermi, monitor, documenti, cartelli, fogli o testo leggibile, "
                "prova a capire se contengono informazioni utili. "
                "Indica SEMPRE se c'e' testo visibile, codice sorgente, messaggi, documenti, "
                "contenuti leggibili, schermate di programmi, finestre aperte, errori o avvisi. "
                "Se vedi un monitor o un computer acceso, specifica se mostra codice, testo, finestre, "
                "documenti, programmi o solo elementi non leggibili. "
                "Se non c'e' nulla di leggibile, dillo chiaramente. "
                "Non inventare parole non visibili. "
                "Rispondi in una frase naturale breve."
            )
        else:
            testo_prompt = (
                "Cosa vedi? Max 15 parole. "
                "Segnala se c'e' testo visibile, ostacoli, danni, passaggi bloccati o elementi anomali."
            )

        payload = {
            "model": "gpt-4o-mini",
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": testo_prompt},
                    {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + img_b64}}
                ]
            }],
            "max_tokens": 80
        }

        res = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=10
        )

        dati = res.json()

        if "choices" not in dati:
            if _marca_llm_non_disponibile(dati):
                return u"un ambiente familiare"
            print(u"[ERRORE ANALISI IMMAGINE HTTP {}]: {}".format(
                res.status_code,
                dati
            ))
            return u"un ambiente familiare"

        return dati['choices'][0]['message']['content']

    except:
        return u"un ambiente familiare"

def analizza_testo_visivo(img_b64, chiave_privata):
    """
    Prova a leggere testo visibile da schermi, fogli, documenti,
    cartelli o codice nell'immagine.

    Non inventa: se non legge chiaramente, restituisce TESTO_NON_LEGGIBILE.
    """
    if not _llm_disponibile(chiave_privata):
        return u"TESTO_NON_LEGGIBILE"

    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + str(chiave_privata or "")
        }

        testo_prompt = (
            "Osserva attentamente l'immagine. "
            "Se vedi uno schermo, un monitor, un foglio, un documento, un cartello o codice, "
            "trascrivi SOLO il testo chiaramente leggibile. "
            "Se riconosci che c'e' codice ma non riesci a leggerlo, scrivi CODICE_NON_LEGGIBILE. "
            "Se vedi testo ma non riesci a leggerlo, scrivi TESTO_NON_LEGGIBILE. "
            "Se non c'e' testo visibile, scrivi NESSUN_TESTO_VISIBILE. "
            "Non inventare parole."
        )

        payload = {
            "model": "gpt-4o-mini",
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": testo_prompt},
                    {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + img_b64}}
                ]
            }],
            "max_tokens": 160,
            "temperature": 0.0
        }

        res = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=12
        )

        dati = res.json()

        if "choices" not in dati:
            if _marca_llm_non_disponibile(dati):
                return u"TESTO_NON_LEGGIBILE"
            print(u"[ERRORE TESTO VISIVO HTTP {}]: {}".format(
                res.status_code,
                dati
            ))
            return u"TESTO_NON_LEGGIBILE"

        return dati['choices'][0]['message']['content'].strip()

    except Exception as e:
        print(u"[ERRORE LETTURA TESTO VISIVO]: " + str(e))
        return u"TESTO_NON_LEGGIBILE"

def estrai_json(testo):
    try:
        testo = testo.strip()
        testo = testo.replace("```json", "").replace("```", "").strip()

        inizio = testo.find("{")
        fine = testo.rfind("}")

        if inizio != -1 and fine != -1 and fine > inizio:
            testo = testo[inizio:fine + 1]

        return json.loads(testo)

    except Exception as e:
        print(u"[ERRORE JSON]: " + str(e))
        print(u"[RISPOSTA GREZZA]: " + testo)
        return {"azioni": []}


def genera_decisione_anima(contesto, dati_memoria, stato_robot, chiave_privata):
    if not _llm_disponibile(chiave_privata):
        return {"azioni": []}

    url = "https://api.openai.com/v1/chat/completions"

    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + str(chiave_privata or "")
    }

    prompt = (
        u"Sei l'anima di NAO. Tu SEI il robot.\n"
        u"Non sei un assistente esterno: sei il livello deliberativo interno del robot.\n\n"

        u"REGOLE DI OUTPUT:\n"
        u"Rispondi SOLO con JSON valido. Nessun testo fuori dal JSON.\n"
        u"Formato obbligatorio:\n"
        u"{\n"
        u'  "stato_interno": "curioso/prudente/sociale/allerta/neutro",\n'
        u'  "obiettivo": "breve descrizione",\n'
        u'  "azioni": [\n'
        u'    {"tipo": "parla", "testo": "testo da dire"}\n'
        u"  ],\n"
        u'  "memoria": []\n'
        u"}\n\n"

        u"AZIONI CONSENTITE:\n"
        u'{"tipo":"parla","testo":"..."}\n'
        u'{"tipo":"cammina","x":0.3,"g":0.0}\n'
        u'{"tipo":"gira","v":0.1}\n'
        u'{"tipo":"fermati"}\n'
        u'{"tipo":"posa","nome":"Stand"}\n'
        u'{"tipo":"guarda","x":0.0,"y":-0.2}\n'
        u'{"tipo":"occhi","colore":"yellow"}\n'
        u'{"tipo":"animazione","path":"animations/Stand/Gestures/Stretch_1"}\n'
        u'{"tipo":"apprendi_volto","nome":"Nome"}\n'
        u'{"tipo":"foto","camera_id":0,"file":"foto.jpg"}\n\n'

        u"REGOLE DI SICUREZZA ASSOLUTA:\n"
        u"1. Se il report contiene 'SONO FERMO', NON usare cammina o gira di tua iniziativa per esplorare.\n"
        u"2. Se vedi qualcosa vicino o lontano mentre sei fermo, usa solo guarda, parla, occhi o animazione.\n"
        u"3. Se leggi 'URTO TATTILE' o 'URTO LATERALE', puoi fare micro-schivata: cammina -0.1 e gira 0.1.\n"
        u"4. Se leggi 'PERICOLO CADUTA', devi fermarti, andare in Crouch e parlare.\n"
        u"5. Se l'utente dice 'vai' o 'cammina', devi: posa Stand, cammina 0.3 0.0, parla.\n"
        u"6. Se l'utente dice 'stop' o 'fermati', devi: fermati, posa Stand, parla.\n"
        u"7. Se STAI CAMMINANDO e riconosci un volto, saluta ma NON fermarti.\n"
        u"8. Se STAI CAMMINANDO e c'è ostacolo a sinistra: cammina 0.3 -0.05.\n"
        u"9. Se STAI CAMMINANDO e c'è ostacolo a destra: cammina 0.3 0.05.\n"
        u"10. Se STAI CAMMINANDO e c'è ostacolo frontale: cammina -0.1 0.0 e gira 0.1.\n\n"

        u"MEMORIA:\n"
        u"Se l'utente rivela fatti personali importanti, aggiungi un elemento in memoria.\n"
        u"Esempio memoria:\n"
        u'{"tipo":"fatto_utente","chiave":"materia","valore":"robotica"}\n\n'

        u"MODALITÀ INIZIATIVA AUTONOMA:\n"
        u"Se il report contiene PRENDI L'INIZIATIVA:\n"
        u"- usa occhi yellow;\n"
        u"- puoi fare stretching;\n"
        u"- ragiona su ciò che vedi;\n"
        u"- collega ciò che vedi alla memoria;\n"
        u"- NON chiedere all'utente cosa fare.\n"
        u"- formula una breve osservazione autonoma e scegli tu una micro-azione sicura.\n"
        u"- se non serve agire, dì solo cosa hai notato in modo naturale.\n"
        u"- NON usare cammina o gira.\n\n"

        u"DATI MEMORIA ATTUALE:\n"
        + json.dumps(dati_memoria, ensure_ascii=False)
        + u"\n\nSTATO INTERNO ATTUALE DEL ROBOT:\n"
        + json.dumps(stato_robot, ensure_ascii=False)
        + u"\n\nOBIETTIVO ATTUALE DEL ROBOT:\n"
        + stato_robot.get("obiettivo_corrente", "nessuno")
    )

    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": contesto}
        ],
        "temperature": 0.0
    }

    try:
        res = requests.post(url, headers=headers, data=json.dumps(payload), timeout=5)
        dati = res.json()

        if "choices" not in dati:
            if _marca_llm_non_disponibile(dati):
                return {"azioni": []}
            print(u"[ERRORE LLM HTTP {}]: {}".format(
                res.status_code,
                dati
            ))
            return {"azioni": []}

        risposta = dati['choices'][0]['message']['content'].strip()
        return estrai_json(risposta)

    except Exception as e:
        print(u"[ERRORE LLM]: " + str(e))
        return {"azioni": []}
