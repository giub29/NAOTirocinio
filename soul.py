# -*- coding: utf-8 -*-
import requests, json, time, threading, base64, os, re
from hardware_control import NaoBody
from sensi import NaoSenses
from voice_interaction import NaoVoice
from vision_perception import NaoVision
from system_manager import NaoSystem

IP_ROBOT = "172.16.165.86"
CHIAVE_PRIVATA = os.getenv("OPENAI_API_KEY", "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")

messaggio_utente = ""
attesa_nome = False
riprendi_dopo_nome = False
primo_ignoto_tempo = 0
ultimo_volto_noto_tempo = 0
ultimo_nome_riconosciuto = ""
memoria_fisica = {}
volti_salutati = []
timeout_volto_ignoto = 0
direzione_recente = ""
tempo_direzione = 0
ultima_batteria_letta = -1
in_pattugliamento = False


def carica_memoria():
    try:
        with open('memoria.json', 'r') as f:
            return json.load(f)
    except:
        return {"nome_utente": "Sconosciuto", "fatti_importanti": {"batteria": 100}, "ricordi_recenti": []}


def salva_memoria(dati):
    try:
        with open('memoria.json', 'w') as f:
            json.dump(dati, f, indent=4)
        return True
    except:
        return False


def analizza_immagine(img_b64, contesto="ostacolo"):
    try:
        headers = {"Content-Type": "application/json", "Authorization": "Bearer " + CHIAVE_PRIVATA}
        testo_prompt = "Descrivi brevemente cosa vedi in una frase naturale." if contesto == "stanza" else "Cosa vedi? Max 10 parole."

        payload = {"model": "gpt-4o-mini", "messages": [{"role": "user", "content": [
            {"type": "text", "text": testo_prompt},
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + img_b64}}]}], "max_tokens": 80}
        res = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=10)
        return res.json()['choices'][0]['message']['content']
    except:
        return u"un ambiente familiare"


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


def genera_decisione_anima(contesto, dati_memoria):
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Content-Type": "application/json", "Authorization": "Bearer " + CHIAVE_PRIVATA}

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
        u"- termina SEMPRE con la frase: Cosa faresti tu?\n"
        u"- NON usare cammina o gira.\n\n"

        u"DATI MEMORIA ATTUALE:\n"
        + json.dumps(dati_memoria, ensure_ascii=False)
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
        risposta = res.json()['choices'][0]['message']['content'].strip()
        return estrai_json(risposta)
    except Exception as e:
        print(u"[ERRORE LLM]: " + str(e))
        return {"azioni": []}


def limita_numero(valore, minimo, massimo, default=0.0):
    try:
        valore = float(valore)
        if valore < minimo:
            return minimo
        if valore > massimo:
            return massimo
        return valore
    except:
        return default


def valida_decisione(decisione, mondo):
    azioni_valide = []
    azioni = decisione.get("azioni", [])

    for az in azioni:
        tipo = az.get("tipo", "")

        if tipo == "parla":
            testo = az.get("testo", "")
            if testo:
                azioni_valide.append({"tipo": "parla", "testo": testo})

        elif tipo == "cammina":
            if "SONO FERMO" in mondo and "L'utente dice" not in mondo and "URTO" not in mondo:
                continue
            x = limita_numero(az.get("x", 0.0), -0.2, 0.3, 0.0)
            g = limita_numero(az.get("g", 0.0), -0.2, 0.2, 0.0)
            azioni_valide.append({"tipo": "cammina", "x": x, "g": g})

        elif tipo == "gira":
            if "SONO FERMO" in mondo and "L'utente dice" not in mondo and "URTO" not in mondo:
                continue
            v = limita_numero(az.get("v", 0.0), -0.3, 0.3, 0.0)
            azioni_valide.append({"tipo": "gira", "v": v})

        elif tipo == "fermati":
            azioni_valide.append({"tipo": "fermati"})

        elif tipo == "posa":
            nome = az.get("nome", "Stand")
            if nome in ["Stand", "Crouch", "Sit", "SitRelax"]:
                azioni_valide.append({"tipo": "posa", "nome": nome})

        elif tipo == "guarda":
            x = limita_numero(az.get("x", 0.0), -1.0, 1.0, 0.0)
            y = limita_numero(az.get("y", 0.0), -0.7, 0.7, 0.0)
            azioni_valide.append({"tipo": "guarda", "x": x, "y": y})

        elif tipo == "occhi":
            colore = az.get("colore", "white")
            if colore in ["white", "red", "green", "blue", "yellow", "purple", "cyan"]:
                azioni_valide.append({"tipo": "occhi", "colore": colore})

        elif tipo == "animazione":
            path = az.get("path", "")
            if path.startswith("animations/"):
                azioni_valide.append({"tipo": "animazione", "path": path})

        elif tipo == "apprendi_volto":
            nome = az.get("nome", "")
            if nome:
                azioni_valide.append({"tipo": "apprendi_volto", "nome": nome})

        elif tipo == "foto":
            camera_id = int(az.get("camera_id", 0))
            file_foto = az.get("file", "foto.jpg")
            if camera_id in [0, 1]:
                azioni_valide.append({"tipo": "foto", "camera_id": camera_id, "file": file_foto})

    decisione["azioni"] = azioni_valide
    return decisione


def aggiorna_memoria_da_decisione(decisione):
    global memoria_fisica

    elementi = decisione.get("memoria", [])
    if not isinstance(elementi, list):
        return

    if "ricordi_recenti" not in memoria_fisica:
        memoria_fisica["ricordi_recenti"] = []

    if "fatti_importanti" not in memoria_fisica:
        memoria_fisica["fatti_importanti"] = {}

    for item in elementi:
        try:
            tipo = item.get("tipo", "ricordo")

            if tipo == "fatto_utente":
                chiave = item.get("chiave", "")
                valore = item.get("valore", "")
                if chiave and valore:
                    memoria_fisica["fatti_importanti"][chiave] = valore

            else:
                memoria_fisica["ricordi_recenti"].append({
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "contenuto": item.get("contenuto", str(item))
                })
        except:
            pass

    memoria_fisica["ricordi_recenti"] = memoria_fisica["ricordi_recenti"][-20:]
    salva_memoria(memoria_fisica)


def esegui_decisione(decisione, corpo, voce, vista, sistema):
    global in_pattugliamento, volti_salutati

    aggiorna_memoria_da_decisione(decisione)

    azioni = decisione.get("azioni", [])

    for az in azioni:
        tipo = az.get("tipo", "")

        try:
            if tipo == "parla":
                testo = az.get("testo", "")
                voce.parla(testo)

                if "Ciao" in testo:
                    m = re.search(r'Ciao (.*?)!', testo)
                    if m:
                        volti_salutati.append(m.group(1))

                if "ignoto" in testo.lower() or "sconosciuto" in testo.lower():
                    volti_salutati.append("Sconosciuto")

            elif tipo == "cammina":
                corpo.cammina(az.get("x", 0.0), az.get("g", 0.0))

            elif tipo == "gira":
                corpo.gira(az.get("v", 0.0))

            elif tipo == "fermati":
                in_pattugliamento = False
                corpo.fermati()

            elif tipo == "posa":
                corpo.vai_in_posa(az.get("nome", "Stand"))

            elif tipo == "guarda":
                corpo.guarda(az.get("x", 0.0), az.get("y", 0.0))

            elif tipo == "occhi":
                corpo.imposta_colore_occhi(az.get("colore", "white"))

            elif tipo == "animazione":
                corpo.esegui_animazione(az.get("path", ""))

            elif tipo == "apprendi_volto":
                vista.apprendi_volto(az.get("nome", ""))

            elif tipo == "foto":
                corpo.scatta_foto(camera_id=az.get("camera_id", 0), nome_file=az.get("file", "foto.jpg"))

        except Exception as e:
            print(u"[ERRORE AZIONE {}]: {}".format(tipo, str(e)))

def gestisci_volto_durante_cammino(mondo, corpo, voce, vista):
    global memoria_fisica, volti_salutati, in_pattugliamento, attesa_nome, riprendi_dopo_nome
    global ultimo_volto_noto_tempo, ultimo_nome_riconosciuto, primo_ignoto_tempo

    # Caso 1: volto già conosciuto
    match = re.search(ur"Riconosco ([^\.]+)\.", mondo)

    if match:
        nome = match.group(1)

        ultimo_volto_noto_tempo = time.time()
        ultimo_nome_riconosciuto = nome

        if attesa_nome:
            attesa_nome = False
            riprendi_dopo_nome = False

        if nome not in volti_salutati:
            corpo.imposta_colore_occhi("green")
            voce.parla(u"Ciao {}, ti ho riconosciuto.".format(nome))
            volti_salutati.append(nome)

        return True

    # Caso 2: volto ignoto
    if u"Vedo un volto ignoto" in mondo:

        # se sto camminando e ho già riconosciuto qualcuno → NON ri-memorizzare subito
        if corpo.sta_camminando() or in_pattugliamento:
            print(u"[VOLTO]: ignoto durante cammino, mi fermo per verificare.")
            corpo.fermati()
            in_pattugliamento = True
            riprendi_dopo_nome = True
            corpo.guarda(0.0, -0.45)
            time.sleep(1.5)

            return True

        # filtro breve (quando fermo)
        if ultimo_nome_riconosciuto != "" and time.time() - ultimo_volto_noto_tempo < 5:
            print(u"[VOLTO]: ignoro falso ignoto, probabilmente è ancora {}".format(ultimo_nome_riconosciuto))
            return True

        # filtro stabilità: non considero subito un ignoto come nuova persona
        if primo_ignoto_tempo == 0:
            primo_ignoto_tempo = time.time()
            print(u"[VOLTO]: volto ignoto rilevato, attendo stabilità...")
            return True

        if time.time() - primo_ignoto_tempo < 2.0:
            print(u"[VOLTO]: volto ignoto ancora instabile...")
            return True

        primo_ignoto_tempo = 0

        if attesa_nome:
            return True

        corpo.imposta_colore_occhi("red")

        stava_camminando = corpo.sta_camminando() or in_pattugliamento
        riprendi_dopo_nome = stava_camminando

        if stava_camminando:
            in_pattugliamento = False
            corpo.fermati()
            time.sleep(1.0)

        corpo.guarda(0.0, -0.45)
        time.sleep(1.0)

        corpo.scatta_foto(camera_id=0, nome_file="sconosciuto.jpg")

        voce.parla(u"Non ti conosco. Ho scattato una foto. Come ti chiami?")
        print(u"\n--- INSERISCI IL NOME E PREMI INVIO ---")
        attesa_nome = True

        return True

    return False

def main():
    global messaggio_utente, attesa_nome, memoria_fisica, volti_salutati, timeout_volto_ignoto
    global direzione_recente, tempo_direzione, ultima_batteria_letta, in_pattugliamento, riprendi_dopo_nome
    global ultimo_volto_noto_tempo, ultimo_nome_riconosciuto, primo_ignoto_tempo

    ultimo_evento_tempo = time.time()
    memoria_fisica = carica_memoria()
    corpo = None

    try:
        corpo = NaoBody(IP_ROBOT)
        sensi = NaoSenses(IP_ROBOT)
        voce = NaoVoice(IP_ROBOT)
        vista = NaoVision(IP_ROBOT)
        sistema = NaoSystem(IP_ROBOT)

        sistema.set_vita_autonoma(False)
        corpo.abilita_motori()
        corpo.vai_in_posa("Stand")
        vista.attiva_inseguimento_volto()

        def loop_input():
            global messaggio_utente
            while True:
                try:
                    t = raw_input()
                    messaggio_utente = t.decode('utf-8', 'ignore')
                except Exception:
                    pass

        threading.Thread(target=loop_input).start()

        print(u"--- ANIMA JSON SICURA PRONTA ---")
        voce.parla(u"Sistemi pronti. Ciao {}, io sono NAO.".format(memoria_fisica.get("nome_utente", "amico")))

        stato_precedente = ""
        ultima_decisione = {"azioni": []}

        while True:
            mondo = sensi.ottieni_report_semantico()

            # PRIORITÀ ASSOLUTA: sicurezza fisica
            if u"URTO TATTILE" in mondo or u"URTO LATERALE" in mondo:
                corpo.fermati()
                in_pattugliamento = False
                attesa_nome = False
                riprendi_dopo_nome = False
                corpo.cammina(-0.1, 0.0)
                time.sleep(0.8)
                corpo.gira(0.15)
                time.sleep(0.8)
                corpo.fermati()
                voce.parla(u"Ho sentito un ostacolo, mi sposto.")
                continue

            if u"PERICOLO CADUTA" in mondo:
                corpo.fermati()
                in_pattugliamento = False
                attesa_nome = False
                riprendi_dopo_nome = False
                corpo.vai_in_posa("Stand")
                voce.parla(u"Mi fermo, rischio di cadere.")
                continue

            # PRIORITÀ ALTA: ostacoli sonar mentre cammina
            if corpo.sta_camminando() or in_pattugliamento:

                if u"Ostacolo frontale molto vicino" in mondo:
                    corpo.cammina(-0.1, 0.0)
                    time.sleep(0.6)
                    corpo.gira(0.15)
                    time.sleep(0.6)
                    corpo.fermati()
                    time.sleep(0.2)
                    corpo.cammina(0.3, 0.0)
                    continue

                elif u"Ostacolo a sinistra" in mondo:
                    corpo.cammina(0.3, -0.08)
                    continue

                elif u"Ostacolo a destra" in mondo:
                    corpo.cammina(0.3, 0.08)
                    continue

            if attesa_nome and messaggio_utente:
                testo = messaggio_utente.strip()
                testo_lower = testo.lower()

                # ENTER senza nome → è la stessa persona
                if testo == "":
                    voce.parla(u"Va bene, continuo.")

                    attesa_nome = False
                    messaggio_utente = ""

                    if riprendi_dopo_nome:
                        riprendi_dopo_nome = False
                        in_pattugliamento = True
                        time.sleep(0.5)
                        corpo.cammina(0.3, 0.0)
                    else:
                        riprendi_dopo_nome = False
                        in_pattugliamento = False
                        corpo.fermati()

                    continue

                # Comandi da NON interpretare come nome
                if testo_lower in ["fermati", "stop", "basta", "annulla"]:
                    attesa_nome = False
                    riprendi_dopo_nome = False
                    in_pattugliamento = False
                    messaggio_utente = ""
                    corpo.fermati()
                    voce.parla(u"Va bene, annullo il riconoscimento e mi fermo.")
                    continue

                if testo_lower in ["vai", "cammina", "va", "i"] or "vai" in testo_lower:
                    voce.parla(u"Sto aspettando un nome. Scrivi per esempio: nome Giulia.")
                    messaggio_utente = ""
                    continue

                # Accetta: "nome X", "mi chiamo X" oppure solo "X"
                nome = ""
                if testo_lower.startswith("nome "):
                    nome = testo[5:].strip()
                elif testo_lower.startswith("mi chiamo "):
                    nome = testo[10:].strip()
                else:
                    nome = testo.strip()

                if len(nome) < 2:
                    voce.parla(u"Il nome è troppo corto. Riprova.")
                    messaggio_utente = ""
                    continue

                corpo.imposta_colore_occhi("yellow")
                voce.parla(u"Piacere {}.".format(nome))

                corpo.guarda(0.0, -0.1)
                time.sleep(1.0)
                riuscito = vista.apprendi_volto(str(nome))

                if riuscito:
                    voce.parla(u"Ti ho memorizzato, {}!".format(nome))
                    corpo.imposta_colore_occhi("green")
                    volti_salutati.append(nome)
                else:
                    voce.parla(u"Non sono riuscito a memorizzarti bene.")
                    corpo.imposta_colore_occhi("red")

                attesa_nome = False
                messaggio_utente = ""

                if riprendi_dopo_nome:
                    riprendi_dopo_nome = False
                    in_pattugliamento = True
                    time.sleep(0.5)
                    corpo.cammina(0.3, 0.0)
                else:
                    riprendi_dopo_nome = False
                    in_pattugliamento = False
                    corpo.fermati()

                continue

            if messaggio_utente:
                testo_user = messaggio_utente.lower()

                if "vai" in testo_user or "cammina" in testo_user:
                    in_pattugliamento = True
                    corpo.guarda(0.0, -0.35)

                elif "stop" in testo_user or "fermati" in testo_user:
                    in_pattugliamento = False
                    corpo.fermati()

            if not corpo.sta_camminando() and not in_pattugliamento:
                mondo = mondo.replace(u"Ostacolo frontale molto vicino", u"Vedo qualcosa vicino")
                mondo = mondo.replace(u"Ostacolo a sinistra", u"C'è qualcosa a sinistra")
                mondo = mondo.replace(u"Ostacolo a destra", u"C'è qualcosa a destra")

            if "batteria" in mondo:
                match_bat = re.search(ur'La mia batteria.*?(\d+)%[.]?', mondo)
                if match_bat:
                    if ultima_batteria_letta == -1:
                        ultima_batteria_letta = int(match_bat.group(1))
                    else:
                        mondo = mondo.replace(match_bat.group(0), u"").strip()

            interazione_reale = (
                messaggio_utente != "" or
                u"Riconosco" in mondo or
                u"Vedo un volto ignoto" in mondo or
                u"carezza" in mondo or
                u"URTO" in mondo or
                u"PERICOLO" in mondo
            )

            if interazione_reale:
                ultimo_evento_tempo = time.time()
            else:
                tempo_di_inerzia = time.time() - ultimo_evento_tempo

                if not corpo.sta_camminando() and messaggio_utente == "" and tempo_di_inerzia > 30:
                    print(u"\n[INIZIATIVA]: NAO analizza la scena...")
                    corpo.imposta_colore_occhi("yellow")
                    corpo.guarda(0.0, -0.2)
                    time.sleep(1)

                    img_b64 = corpo.scatta_foto(camera_id=0, nome_file="curiosita.jpg")
                    desc = analizza_immagine(img_b64, contesto="stanza") if img_b64 else "una stanza tranquilla"

                    mondo += u" PRENDI L'INIZIATIVA. Vedi: {}. Usa la memoria e chiedi 'Cosa faresti tu?'.".format(desc)
                    ultimo_evento_tempo = time.time()

            for nome in volti_salutati:
                mondo = re.sub(ur"Riconosco {}\.".format(nome), u"", mondo, flags=re.IGNORECASE)

            mondo = re.sub(r'\s+', ' ', mondo).strip()

            if corpo.sta_camminando() or in_pattugliamento:
                mondo += u" STO CAMMINANDO."
            else:
                mondo += u" SONO FERMO."

            if messaggio_utente:
                mondo += u" L'utente dice: '{}'.".format(messaggio_utente)
                messaggio_utente = ""

            if not attesa_nome:
                if mondo != stato_precedente and mondo.strip() != "REPORT: SONO FERMO.":
                    print(u"\n[SENSORI]: " + mondo)

                    if gestisci_volto_durante_cammino(mondo, corpo, voce, vista):
                        stato_precedente = mondo
                        time.sleep(0.1)
                        continue

                    decisione = genera_decisione_anima(mondo, memoria_fisica)
                    decisione = valida_decisione(decisione, mondo)
                    ultima_decisione = decisione

                    ultimo_evento_tempo = time.time()

                    print(u"[STATO]: " + unicode(decisione.get("stato_interno", "neutro")))
                    print(u"[OBIETTIVO]: " + unicode(decisione.get("obiettivo", "")))
                    print(u"[AZIONI]: " + json.dumps(decisione.get("azioni", []), ensure_ascii=False))

                    esegui_decisione(decisione, corpo, voce, vista, sistema)

            if in_pattugliamento and not corpo.sta_camminando():
                azioni_testo = json.dumps(ultima_decisione.get("azioni", []))
                if "cammina" not in azioni_testo and "gira" not in azioni_testo and "fermati" not in azioni_testo:
                    corpo.cammina(0.3, 0.0)

            stato_precedente = mondo
            time.sleep(0.1)

    except KeyboardInterrupt:
        pass

    finally:
        if corpo:
            corpo.fermati()
            corpo.disabilita_motori()


if __name__ == "__main__":
    main()