# -*- coding: utf-8 -*-
import requests, json, time, threading, base64, os, re
from hardware_control import NaoBody
from sensi import NaoSenses
from voice_interaction import NaoVoice
from vision_perception import NaoVision
from system_manager import NaoSystem

IP_ROBOT = "172.16.165.86"
CHIAVE_PRIVATA = "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"

messaggio_utente = ""
memoria_fisica = {}
volti_salutati = []        # Lista dinamica di chi ha già salutato
timeout_volto_ignoto = 0   # Timer per non impazzire con i volti nuovi

def carica_memoria():
    try:
        with open('memoria.json', 'r') as f:
            return json.load(f)
    except:
        return {"nome_utente": "Sconosciuto", "fatti_importanti": {"batteria": 100}}


def analizza_immagine(percorso, contesto="ostacolo"):
    try:
        with open(percorso, "rb") as f:
            img = base64.b64encode(f.read()).decode('utf-8')
        headers = {"Content-Type": "application/json", "Authorization": "Bearer " + CHIAVE_PRIVATA}

        # Decide the prompt based on context
        if contesto == "stanza":
            testo_prompt = "Descrivi l'ambiente che vedi davanti a te in una frase breve e naturale."
            max_tok = 80
        else:
            testo_prompt = "Cosa vedi? Max 10 parole."
            max_tok = 50

        payload = {"model": "gpt-4o-mini", "messages": [{"role": "user", "content": [
            {"type": "text", "text": testo_prompt},
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + img}}]}], "max_tokens": max_tok}
        res = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=10)
        return res.json()['choices'][0]['message']['content']
    except:
        return u"un oggetto ignoto"

def genera_codice_anima(contesto, dati_memoria):
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Content-Type": "application/json", "Authorization": "Bearer " + CHIAVE_PRIVATA}

    prompt = (
        u"Sei l'anima di NAO. Tu SEI il robot.\n"
        u"STATO ATTUALE: Sei FERMO. Non camminare di tua iniziativa.\n\n"
        u"REGOLE DI OUTPUT E SINTASSI (CRITICHE):\n"
        u"1. Rispondi SOLO con codice Python eseguibile. NIENTE testo libero.\n"
        u"2. Usa i DOPPI APICI per il testo, es: voce.parla(\"Testo\").\n\n"
        u"REGOLE SOCIALI:\n"
        u"1. SALUTO: Se 'Riconosco [Nome]', saluta con voce.parla(\"Ciao [Nome]!\") restando FERMO. Non muovere le gambe mentre parli.\n"
        u"2. Se leggi 'e\\' presente', NON salutare più. Ignora il volto.\n"
        u"3. Se 'volto ignoto', chiedi chi è. Se l'utente dice 'Sono [Nome]', esegui: vista.apprendi_volto(\"[Nome]\");\n\n"
        u"REGOLE DI SCHIVATA E NAVIGAZIONE (GERARCHIA RIGIDA):\n"
        u"1. EMERGENZA UTENTE: SE leggi 'stop', 'fermati' o simili, IGNORA TUTTO: corpo.fermati(); corpo.guarda(0.0, 0.0); corpo.vai_in_posa(\"Crouch\"); voce.parla(\"Mi fermo.\");\n"
        u"2. PARTENZA: SE l'utente dice 'vai' o 'cammina', DEVI eseguire: corpo.vai_in_posa(\"Stand\"); corpo.cammina(0.3, 0.0); voce.parla(\"Inizio l'esplorazione!\");\n"
        u"3. SCHIVATA LATERALE: SE stai camminando e leggi:\n"
        u"   - 'Ostacolo a sinistra': DEVI curvare a destra con corpo.cammina(0.2, -0.4);\n"
        u"   - 'Ostacolo a destra': DEVI curvare a sinistra con corpo.cammina(0.2, 0.4);\n"
        u"4. FINE OSTACOLO: SE E SOLO SE stavi già camminando in avanti e il report torna pulito, rimetterti dritto: corpo.cammina(0.3, 0.0). SE ERI FERMO, NON CAMMINARE.\n"
        u"5. OSTACOLO FRONTALE: SE leggi 'Vedo chiaramente: [oggetto]', esegui: corpo.gira(1.5); corpo.cammina(0.3, 0.0); voce.parla(\"Ostacolo evitato, riprendo la marcia.\");\n\n"
        u"REAZIONI FISICHE (ASSOLUTE):\n"
        u"- CAREZZA: corpo.fermati(); corpo.guarda(0.0, 0.0); voce.parla(\"Che bello!\"); corpo.esegui_animazione(\"animations/Stand/Gestures/Hey_1\");\n"
        u"- URTO TATTILE: corpo.fermati(); corpo.gira(1.5); corpo.cammina(0.3, 0.0); voce.parla(\"Ostacolo invisibile colpito! Cambio direzione.\");\n\n"
        u"LIMITAZIONE COMANDI: corpo.cammina(x,gira), corpo.gira(v), corpo.fermati(), corpo.guarda(x,y), voce.parla(t), vista.apprendi_volto(n), corpo.esegui_animazione(p).\n"
        u"Se non hai azioni urgenti, scrivi: pass"
    )

    payload = {"model": "gpt-4o-mini",
               "messages": [{"role": "system", "content": prompt}, {"role": "user", "content": contesto}],
               "temperature": 0.0}
    try:
        res = requests.post(url, headers=headers, data=json.dumps(payload), timeout=5)
        codice = res.json()['choices'][0]['message']['content'].strip()
        codice = codice.replace("```python", "").replace("```", "").replace("python", "").strip()
        codice = codice.replace("\\'", "'").replace('\\"', '"')

        if codice and not any(cmd in codice for cmd in ["corpo.", "voce.", "vista.", "pass"]):
            return u"voce.parla(\"{}\");".format(codice.replace('"', ' '))
        return codice if codice else "pass"
    except:
        return "pass"

def main():
    global messaggio_utente, memoria_fisica, volti_salutati, timeout_volto_ignoto
    memoria_fisica = carica_memoria()
    corpo = None; vista = None
    try:
        corpo = NaoBody(IP_ROBOT); sensi = NaoSenses(IP_ROBOT); voce = NaoVoice(IP_ROBOT)
        vista = NaoVision(IP_ROBOT); sistema = NaoSystem(IP_ROBOT)

        sistema.set_vita_autonoma(False); corpo.abilita_motori(); corpo.vai_in_posa("Crouch"); corpo.disabilita_motori()
        vista.attiva_inseguimento_volto()

        def loop_input():
            global messaggio_utente
            while True:
                t = raw_input()
                if t: messaggio_utente = t.decode('utf-8')
        threading.Thread(target=loop_input).start()

        print(u"--- ANIMA POTENZIATA PRONTA ---")
        voce.parla(u"Sistemi pronti. Ciao {}, io sono NAO e sono ai tuoi ordini.".format(memoria_fisica["nome_utente"]))
        stato_precedente = ""

        tempo_ultima_foto = 0
        while True:
            mondo = sensi.ottieni_report_semantico()

            # Se NAO è fermo, rendiamo gli ostacoli meno "urgenti" per l'Anima
            if not corpo.sta_camminando():
                mondo = mondo.replace(u"Ostacolo frontale molto vicino.", u"Vedo un ostacolo vicino, ma sono fermo.")
                mondo = mondo.replace(u"Ostacolo a sinistra.", u"C'è qualcosa a sinistra.")
                mondo = mondo.replace(u"Ostacolo a destra.", u"C'è qualcosa a destra.")

            # --- SISTEMA SOCIALE MULTI-VOLTO ---
            # 1. Nascondiamo solo le persone che ha già salutato (ignorando maiuscole/minuscole)
            for nome in volti_salutati:
                mondo = re.sub(ur"Riconosco {}\.".format(nome), u"", mondo, flags=re.IGNORECASE)

            if u"Vedo un volto ignoto." in mondo:
                if time.time() - timeout_volto_ignoto < 30:
                    mondo = mondo.replace(u"Vedo un volto ignoto.", u"")
                else:
                    timeout_volto_ignoto = time.time()  # Resetta il timer e lascia passare il report

            mondo = mondo.replace(u"  ", u" ").strip()

            if messaggio_utente:
                cmd = messaggio_utente.lower().strip()
                if cmd in ["cosa vedi", "descrivi la stanza", "cosa vedi?"]:
                    # 1. MEMORIZZA LO STATO: Stava camminando prima che glielo chiedessi?
                    stava_camminando = corpo.sta_camminando()

                    print(u"\n[Comando Esplorazione Ricevuto]")
                    corpo.fermati()
                    corpo.guarda(0.0, -0.3)  # Guarda leggermente in alto
                    voce.parla("Un momento, guardo cosa c'è intorno a me.")
                    time.sleep(1)  # Aspetta che la testa si fermi

                    if corpo.scatta_foto(camera_id=0):  # Usa la Camera Top
                        descrizione = analizza_immagine("visione_nao.jpg", contesto="stanza")
                        voce.parla(u"Vedo: " + descrizione)
                        try:
                            #os.remove("visione_nao.jpg")
                            pass
                        except:
                            pass
                    else:
                        voce.parla("Scusa, ho un problema con i sensori visivi.")

                    corpo.guarda(0.0, 0.0)  # Rimette la testa dritta
                    messaggio_utente = ""
                    mondo = "REPORT: "

                    # 2. RIPARTENZA AUTONOMA: Se camminava prima, riparte ora!
                    if stava_camminando:
                        voce.parla("Riprendo l'esplorazione.")
                        corpo.cammina(0.3, 0.0)
                else:
                    mondo += u" L'utente dice: '{}'.".format(messaggio_utente)
                    messaggio_utente = ""

            if u"Ostacolo frontale" in mondo and corpo.sta_camminando() and (time.time() - tempo_ultima_foto > 15):
                corpo.fermati()
                tempo_ultima_foto = time.time()
                if corpo.scatta_foto(camera_id=1):
                    mondo += u" Vedo chiaramente: {}.".format(analizza_immagine("visione_nao.jpg", contesto="ostacolo"))
                    try:
                        # os.remove("visione_nao.jpg")
                        pass
                    except:
                        pass
            if mondo != stato_precedente and mondo.strip() != "REPORT:":
                print(u"\n[SENSORI]: " + mondo)
                azione = genera_codice_anima(mondo, memoria_fisica)
                if azione != "pass":
                    print(u"[ANIMA]: " + azione)
                    if "Ciao" in azione:
                        match = re.search(r'Ciao (.*?)!', azione)
                        if match:
                            volti_salutati.append(match.group(1))
                    try:
                        exec (azione, {"corpo": corpo, "voce": voce, "vista": vista, "sistema": sistema, "True": True,
                                       "False": False})
                    except Exception as e:
                        print(u"Errore: " + str(e))
            time.sleep(0.1)
    except KeyboardInterrupt: pass
    finally:
        if vista:
            try:
                from naoqi import ALProxy
                t = ALProxy("ALTracker", IP_ROBOT, 9559)
                t.stopTracker(); t.unregisterAllTargets()
            except: pass
        if corpo:
            try:
                corpo.fermati()
                corpo.disabilita_motori()
            except:
                pass

if __name__ == "__main__": main()