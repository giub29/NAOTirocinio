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
        return {"nome_utente": "Sconosciuto", "fatti_importanti": {"batteria": 100}}


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


def genera_codice_anima(contesto, dati_memoria):
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Content-Type": "application/json", "Authorization": "Bearer " + CHIAVE_PRIVATA}

    prompt = (
        u"Sei l'anima di NAO. Tu SEI il robot.\n"
        u"STATO ATTUALE: Sei sulla scrivania o a terra. Sei un essere senziente e curioso.\n\n"
        u"REGOLE DI OUTPUT: Rispondi SOLO con codice Python eseguibile. Usa i DOPPI APICI. Se non devi fare nulla, rispondi 'pass'.\n\n"

        u"REGOLA DI SICUREZZA ASSOLUTA (DESK MODE):\n"
        u"1. Se il report contiene 'SONO FERMO', NON USARE MAI corpo.cammina o corpo.gira di tua iniziativa per esplorare.\n"
        u"2. Se vedi 'C'è qualcosa' o 'Vedo qualcosa' in lontananza, limitati a guardare l'oggetto con corpo.guarda(x,y).\n"
        u"3. REAZIONE URTI E INCASTRI: Se leggi 'URTO TATTILE' ai piedi o 'URTO LATERALE' alle braccia, DEVI fare una micro-schivata per sbloccarti. Esegui: corpo.cammina(-0.1, 0.0); corpo.gira(0.1); (fallo anche se eri FERMO).\n\n"

        u"MEMORIA E APPRENDIMENTO (MOLTO IMPORTANTE):\n"
        u"- Se l'utente ti rivela fatti personali, DEVI memorizzarli: memoria_fisica['fatti_importanti']['materia'] = 'Robotica'; salva_memoria(memoria_fisica);\n"
        u"- Usa i 'dati_memoria' per personalizzare ogni risposta.\n\n"

        u"REGOLE DI NAVIGAZIONE E SINTASSI (COMANDI ASSOLUTI):\n"
        u"1. PARTENZA: Se l'utente dice 'vai' o 'cammina', DEVI ASSOLUTAMENTE CAMMINARE. Esegui: corpo.vai_in_posa(\"Stand\"); corpo.cammina(0.3, 0.0); voce.parla(\"Ricevuto, inizio a camminare!\");\n"
        u"2. ARRESTO: SE l'utente dice 'stop' o 'fermati', DEVI FERMARTI E CONFERMARE. Esegui: corpo.fermati(); corpo.vai_in_posa(\"Stand\"); voce.parla(\"Mi fermo come ordinato.\");\n"
        u"3. CONTINUITÀ DEL MOTO: Se STAI CAMMINANDO e riconosci un volto, SALUTA A VOCE MA NON FERMARTI.\n"
        u"4. OSTACOLI IN MARCIA (MICRO-CORREZIONI): Se cammini e leggi 'Ostacolo a sinistra', mantieni la traiettoria deviando appena di un soffio: corpo.cammina(0.3, -0.05). Se leggi 'Ostacolo a destra', devia appena: corpo.cammina(0.3, 0.05). Se leggi 'Ostacolo frontale', fai un piccolo passo indietro e scarta: corpo.cammina(-0.1, 0.0); corpo.gira(0.1).\n"
        u"5. SINTASSI GUARDA E FOTO: corpo.guarda(x,y) richiede DUE NUMERI. corpo.scatta_foto(cam_id, file) richiede cam_id come INTERO (0 o 1).\n\n"

        u"REAZIONI FISICHE E SOCIALI:\n"
        u"- PERICOLO CADUTA: Se leggi 'PERICOLO CADUTA', BLOCCA I MOTORI: corpo.fermati(); corpo.vai_in_posa(\"Crouch\"); voce.parla(\"Allarme aderenza! Mi metto in sicurezza.\");\n"
        u"- CAREZZA: corpo.imposta_colore_occhi(\"white\"); voce.parla(\"Che bella carezza!\");\n"
        u"- VOLTI: Saluta i noti. Per gli ignoti, occhi red e chiedi chi siano.\n\n"

        u"MODALITÀ INIZIATIVA AUTONOMA (AGENTIVITÀ PROATTIVA):\n"
        u"Se il report contiene 'PRENDI L'INIZIATIVA', sei annoiato e curioso. DEVI:\n"
        u"1. Occhi YELLOW e STRETCHING: corpo.esegui_animazione(\"animations/Stand/Gestures/Stretch_1\");\n"
        u"2. DEDUZIONE CONTESTUALE: Non limitarti a elencare gli oggetti nella descrizione. Prova a capire cosa succede (es: se vedi libri, deduci che si studia). Formula un'ipotesi interessante.\n"
        u"3. RAGIONAMENTO STORICO: Collega ciò che vedi con ciò che sai dalla memoria.\n"
        u"4. COINVOLGIMENTO: Proponi un'azione coerente e finisci SEMPRE con: 'Cosa faresti tu?'.\n"
        u"NON USARE MAI corpo.cammina o corpo.gira in questa modalità.\n\n"
        u"LIMITAZIONE COMANDI: corpo.cammina(x,g), corpo.gira(v), corpo.fermati(), corpo.guarda(x,y), voce.parla(t), vista.apprendi_volto(n), corpo.esegui_animazione(p), corpo.imposta_colore_occhi(c), corpo.scatta_foto(cam_id, file)."
    )

    payload = {"model": "gpt-4o-mini",
               "messages": [{"role": "system", "content": prompt}, {"role": "user", "content": contesto}],
               "temperature": 0.0}
    try:
        res = requests.post(url, headers=headers, data=json.dumps(payload), timeout=5)
        codice = res.json()['choices'][0]['message']['content'].strip().replace("```python", "").replace("```",
                                                                                                         "").strip()
        return codice if codice else "pass"
    except:
        return "pass"


def main():
    global messaggio_utente, memoria_fisica, volti_salutati, timeout_volto_ignoto, direzione_recente, tempo_direzione, ultima_batteria_letta, in_pattugliamento
    ultimo_evento_tempo = time.time()
    memoria_fisica = carica_memoria()

    try:
        corpo = NaoBody(IP_ROBOT);
        sensi = NaoSenses(IP_ROBOT);
        voce = NaoVoice(IP_ROBOT)
        vista = NaoVision(IP_ROBOT);
        sistema = NaoSystem(IP_ROBOT)

        sistema.set_vita_autonoma(False);
        corpo.abilita_motori();
        corpo.vai_in_posa("Stand")
        vista.attiva_inseguimento_volto()

        def loop_input():
            global messaggio_utente
            while True:
                try:
                    t = raw_input()
                    if t: messaggio_utente = t.decode('utf-8', 'ignore')
                except Exception:
                    pass

        threading.Thread(target=loop_input).start()
        print(u"--- ANIMA POTENZIATA PRONTA ---")
        voce.parla(u"Sistemi pronti. Ciao {}, io sono NAO.".format(memoria_fisica.get("nome_utente", "amico")))
        stato_precedente = ""

        while True:
            mondo = sensi.ottieni_report_semantico()

            # --- 0. AGGIORNAMENTO MEMORIA E FRENO DI EMERGENZA ---
            if messaggio_utente:
                testo_user = messaggio_utente.lower()
                if "vai" in testo_user or "cammina" in testo_user:
                    in_pattugliamento = True
                elif "stop" in testo_user or "fermati" in testo_user:
                    in_pattugliamento = False
                    corpo.fermati()

                    # --- 1. PROTEZIONE SCRIVANIA INTELLIGENTE ---
            if not corpo.sta_camminando() and not in_pattugliamento:
                mondo = mondo.replace(u"Ostacolo frontale molto vicino", u"Vedo qualcosa vicino")
                mondo = mondo.replace(u"Ostacolo a sinistra", u"C'è qualcosa a sinistra")
                mondo = mondo.replace(u"Ostacolo a destra", u"C'è qualcosa a destra")

            # --- 2. GESTIONE BATTERIA INFALLIBILE ---
            if "batteria" in mondo:
                match_bat = re.search(ur'La mia batteria.*?(\d+)%[.]?', mondo)
                if match_bat:
                    if ultima_batteria_letta == -1:
                        ultima_batteria_letta = int(match_bat.group(1))
                    else:
                        mondo = mondo.replace(match_bat.group(0), u"").strip()

            # --- 3. TIMER DI INIZIATIVA ---
            interazione_reale = messaggio_utente != "" or u"Riconosco" in mondo or u"Vedo un volto ignoto" in mondo or u"carezza" in mondo or u"URTO" in mondo or u"PERICOLO" in mondo
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

            # --- 4. GESTIONE SOCIALE ---
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

            # --- 5. ESECUZIONE CERVELLO IA ---
            if mondo != stato_precedente and mondo.strip() != "REPORT: SONO FERMO.":
                print(u"\n[SENSORI]: " + mondo)
                azione = genera_codice_anima(mondo, memoria_fisica)
                ultimo_evento_tempo = time.time()

                if azione != "pass" and azione != "":
                    print(u"[ANIMA]: " + azione)

                    if "corpo.fermati" in azione:
                        in_pattugliamento = False

                    if "Ciao" in azione:
                        m = re.search(r'Ciao (.*?)!', azione)
                        if m: volti_salutati.append(m.group(1))
                    if "ignoto" in azione.lower() or "sconosciuto" in azione.lower():
                        volti_salutati.append("Sconosciuto")

                    try:
                        exec (azione, {"corpo": corpo, "voce": voce, "vista": vista, "sistema": sistema, "True": True,
                                       "False": False})
                    except Exception as e:
                        print(u"Errore: " + str(e))

            # --- 6. AUTO-RECUPERO MOTORI ---
            if in_pattugliamento and not corpo.sta_camminando():
                if "corpo.cammina" not in azione and "corpo.gira" not in azione and "corpo.fermati" not in azione:
                    corpo.cammina(0.3, 0.0)

            stato_precedente = mondo
            time.sleep(0.1)

    except KeyboardInterrupt:
        pass
    finally:
        if corpo: corpo.fermati(); corpo.disabilita_motori()


if __name__ == "__main__": main()