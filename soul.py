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


def carica_memoria():
    try:
        with open('memoria.json', 'r') as f:
            return json.load(f)
    except:
        return {"nome_utente": "Sconosciuto", "fatti_importanti": {"batteria": 100}}


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
        u"STATO ATTUALE: Sei FERMO sulla scrivania. Non camminare MAI di tua iniziativa.\n\n"
        u"REGOLE DI OUTPUT: Rispondi SOLO con codice Python eseguibile. Usa i DOPPI APICI.\n\n"
        u"REGOLA DI SICUREZZA ASSOLUTA (DESK MODE):\n"
        u"1. Se il report contiene 'SONO FERMO', NON USARE MAI corpo.cammina o corpo.gira, anche se leggi di oggetti o ostacoli.\n"
        u"2. Se vedi 'C'è qualcosa' o 'Vedo qualcosa', limitati a guardare l'oggetto con corpo.guarda(x,y) o a commentarlo a voce.\n\n"
        u"REGOLE DI NAVIGAZIONE (SOLO SE 'STO CAMMINANDO'):\n"
        u"1. EMERGENZA: SE 'stop' o 'fermati', esegui: corpo.fermati(); corpo.vai_in_posa(\"Crouch\"); voce.parla(\"Mi fermo.\");\n"
        u"2. PARTENZA: SE 'vai', esegui: corpo.vai_in_posa(\"Stand\"); corpo.cammina(0.3, 0.0); voce.parla(\"Inizio il pattugliamento!\");\n"
        u"3. OSTACOLI: Se cammini e vedi ostacoli, usa corpo.cammina(0.3, +/-0.1) per schivare dolcemente.\n\n"
        u"REAZIONI FISICHE:\n"
        u"- CADUTA: corpo.fermati(); corpo.vai_in_posa(\"Crouch\"); voce.parla(\"Allarme aderenza!\");\n"
        u"- CAREZZA: corpo.imposta_colore_occhi(\"white\"); voce.parla(\"Che bella carezza!\");\n\n"
        u"REGOLE SOCIALI:\n"
        u"1. VOLTI: Saluta chi riconosci (occhi green) e fotografa gli ignoti (occhi red).\n\n"
        u"MODALITÀ INIZIATIVA AUTONOMA (AGENTIVITÀ PROATTIVA):\n"
        u"Se il report contiene 'PRENDI L'INIZIATIVA', sei annoiato e curioso. DEVI:\n"
        u"1. Occhi YELLOW: corpo.imposta_colore_occhi(\"yellow\");\n"
        u"2. STRETCHING: corpo.esegui_animazione(\"animations/Stand/Gestures/Stretch_1\");\n"
        u"3. DEDUZIONE CONTESTUALE: Non limitarti a elencare gli oggetti nella descrizione. Prova a capire cosa succede (es: se vedi libri, deduci che si studia). Formula un'ipotesi interessante.\n"
        u"4. COINVOLGIMENTO: Proponi un'azione coerente e finisci SEMPRE con: 'Cosa faresti tu?'.\n"
        u"Esempio: voce.parla(\"Vedo molti appunti, qualcuno sta lavorando sodo. Mi sgranchisco un po' e resto a osservare. Cosa faresti tu?\");\n"
        u"NON USARE MAI corpo.cammina o corpo.gira in questa modalità.\n\n"
        u"LIMITAZIONE COMANDI: corpo.cammina(x,g), corpo.gira(v), corpo.fermati(), corpo.guarda(x,y), voce.parla(t), vista.apprendi_volto(n), corpo.esegui_animazione(p), corpo.imposta_colore_occhi(c), corpo.scatta_foto(cam, file)."
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
    global messaggio_utente, memoria_fisica, volti_salutati, timeout_volto_ignoto, direzione_recente, tempo_direzione
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
                t = raw_input()
                if t: messaggio_utente = t.decode('utf-8')

        threading.Thread(target=loop_input).start()
        print(u"--- ANIMA POTENZIATA PRONTA ---")
        voce.parla(u"Sistemi pronti. Ciao {}, io sono NAO.".format(memoria_fisica["nome_utente"]))
        stato_precedente = ""

        while True:
            mondo = sensi.ottieni_report_semantico()

            # --- 1. PROTEZIONE SCRIVANIA (ANTI-CAMMINATA SPONTANEA) ---
            # Se il robot è fermo, rinominiamo gli 'Ostacoli' in modo che l'IA non attivi i riflessi di schivata
            if not corpo.sta_camminando():
                mondo = mondo.replace(u"Ostacolo frontale molto vicino", u"Vedo qualcosa vicino")
                mondo = mondo.replace(u"Ostacolo a sinistra", u"C'è qualcosa a sinistra")
                mondo = mondo.replace(u"Ostacolo a destra", u"C'è qualcosa a destra")

            # --- 2. GESTIONE BATTERIA INTELLIGENTE ---
            # Cerchiamo il livello della batteria nel report dei sensori
            match_bat = re.search(r'batteria è al (\d+)%', mondo)
            if match_bat:
                livello = int(match_bat.group(1))
                # Parla della batteria solo all'inizio, se cala del 5% o se è sotto il 20%
                if (ultima_batteria_letta - livello >= 5) or (livello <= 20):
                    ultima_batteria_letta = livello
                else:
                    # Rimuoviamo l'info batteria dal report per non ossessionare l'IA e non resettare il timer
                    mondo = re.sub(r'La mia batteria è al \d+%\.', u'', mondo)

            # --- 3. LOGICA DEL TIMER DI INIZIATIVA (FILTRATA) ---
            # Il timer si resetta solo per interazioni umane o fisiche reali, ignorando i sonar
            interazione_reale = messaggio_utente != "" or u"Riconosco" in mondo or u"Vedo un volto ignoto" in mondo or u"carezza" in mondo or u"URTO" in mondo

            if interazione_reale:
                ultimo_evento_tempo = time.time()  # Reset se succede qualcosa di importante
            else:
                tempo_di_inerzia = time.time() - ultimo_evento_tempo
                # Se è fermo da 30 secondi e non stiamo scrivendo, scatta la noia
                if not corpo.sta_camminando() and messaggio_utente == "" and tempo_di_inerzia > 30:
                    print(u"\n[INIZIATIVA]: NAO analizza la scena per prendere l'iniziativa...")
                    corpo.imposta_colore_occhi("yellow")  # Segnale visivo di autonomia
                    corpo.guarda(0.0, -0.2)
                    time.sleep(1)
                    # Scatta una foto per nutrire la deduzione contestuale dell'IA
                    img_b64 = corpo.scatta_foto(camera_id=0, nome_file="curiosita.jpg")
                    desc = analizza_immagine(img_b64, contesto="stanza") if img_b64 else "una stanza tranquilla"

                    # Stimolo proattivo inviato all'anima
                    mondo += u" PRENDI L'INIZIATIVA. Vedi: {}. Fai stretching e chiedi 'Cosa faresti tu?'.".format(desc)
                    ultimo_evento_tempo = time.time()  # Reset per non loopare l'iniziativa

            # --- 4. GESTIONE SOCIALE E STATO ---
            if u"Riconosco" in mondo:
                timeout_volto_ignoto = time.time()

            for nome in volti_salutati:
                mondo = re.sub(ur"Riconosco {}\.".format(nome), u"", mondo, flags=re.IGNORECASE)

            mondo = mondo.replace(u"  ", u" ").strip()
            mondo += u" STO CAMMINANDO." if corpo.sta_camminando() else u" SONO FERMO."

            if messaggio_utente:
                mondo += u" L'utente dice: '{}'.".format(messaggio_utente)
                messaggio_utente = ""

            # --- 5. ESECUZIONE CERVELLO IA ---
            if mondo != stato_precedente and mondo.strip() != "REPORT:":
                print(u"\n[SENSORI]: " + mondo)
                azione = genera_codice_anima(mondo, memoria_fisica)
                if azione != "pass":
                    print(u"[ANIMA]: " + azione)

                    # Se saluta qualcuno o identifica uno sconosciuto, lo memorizziamo
                    if "Ciao" in azione:
                        m = re.search(r'Ciao (.*?)!', azione)
                        if m: volti_salutati.append(m.group(1))

                    if "Sconosciuto identificato" in azione:
                        volti_salutati.append("Sconosciuto")

                    try:
                        exec (azione, {"corpo": corpo, "voce": voce, "vista": vista, "sistema": sistema, "True": True,
                                       "False": False})
                    except Exception as e:
                        print(u"Errore: " + str(e))

            stato_precedente = mondo
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        if corpo: corpo.fermati(); corpo.disabilita_motori()


if __name__ == "__main__": main()