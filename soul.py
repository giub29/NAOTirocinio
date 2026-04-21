# -*- coding: utf-8 -*-
import requests, json, time, threading, base64, os
from hardware_control import NaoBody
from sensi import NaoSenses
from voice_interaction import NaoVoice
from vision_perception import NaoVision
from system_manager import NaoSystem

IP_ROBOT = "172.16.165.86"
CHIAVE_PRIVATA = "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"

messaggio_utente = ""
memoria_fisica = {}
gia_salutata = False

def carica_memoria():
    try:
        with open('memoria.json', 'r') as f:
            return json.load(f)
    except:
        return {"nome_utente": "Sconosciuto", "fatti_importanti": {"batteria": 100}}

def analizza_immagine(percorso):
    try:
        with open(percorso, "rb") as f:
            img = base64.b64encode(f.read()).decode('utf-8')
        headers = {"Content-Type": "application/json", "Authorization": "Bearer " + CHIAVE_PRIVATA}
        payload = {"model": "gpt-4o-mini", "messages": [{"role": "user", "content": [
            {"type": "text", "text": "Cosa vedi? Max 10 parole."},
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + img}}]}], "max_tokens": 50}
        res = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=10)
        return res.json()['choices'][0]['message']['content']
    except: return u"un oggetto ignoto"

def genera_codice_anima(contesto, dati_memoria):
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Content-Type": "application/json", "Authorization": "Bearer " + CHIAVE_PRIVATA}

    nome_u = dati_memoria.get("nome_utente", "Sconosciuto")

    prompt = (
        u"Sei l'anima di NAO. Tu SEI il robot\n\n"
        u"STATO ATTUALE: Sei FERMO. Non muovere i motori delle gambe senza ordine.\n\n"
        u"STATO CONOSCENZA: Al momento il tuo utente e' salvato come: {}.\n\n"
        u"REGOLE DI OUTPUT (CRITICHE):\n"
        u"1. Rispondi SOLO con codice Python eseguibile. NIENTE testo libero.\n"
        u"2. Ogni frase detta deve stare in voce.parla('testo');\n"
        u"3. Se riconosci {}, saluta con voce.parla('Ciao {}!') MA fallo una sola volta.\n\n"
        u"REGOLE DI COMPORTAMENTO:\n"
        u"1. SE vedi un 'volto ignoto' e non hai ancora chiesto il nome: voce.parla('Ciao! Non credo di conoscerti. Come ti chiami?');\n"
        u"2. SE l'utente dice 'Sono [Nome]': DEVI chiamare vista.apprendi_volto('[Nome]'); voce.parla('Piacere di conoscerti, ora ti ho memorizzato!');\n"
        u"3. SE riconosci un volto gia' noto (es. Giulia): saluta calorosamente e NON usare vista.apprendi_volto.\n\n"
        u"REGOLE FISICHE:\n"
        u"1. MOVIMENTO: NON usare MAI corpo.cammina() o corpo.gira() a meno che non leggi esattamente 'L'utente dice: cammina' o 'vai'.\n"
        u"2. OSTACOLI: SE vedi un 'Ostacolo' e NON stai camminando: LIMITATI a dirlo a voce (es: voce.parla('C'è un ostacolo');). NON muovere le gambe.\n"
        u"3. BATTITI: 1:voce.parla('Aiuto!'); 2:corpo.vai_in_posa('Stand'); 3:corpo.vai_in_posa('Crouch');\n"
        u"4. CAREZZA: corpo.fermati(); voce.parla('Che bello!'); corpo.esegui_animazione('animations/Stand/Gestures/Hey_1');\n"
        u"5. PIEDE PESTATO: Se 'Piede sinistro pestato', esegui: corpo.fermati(); corpo.imposta_colore_occhi('red'); corpo.gira(-0.5); voce.parla('Ahi! Il mio piede!'); corpo.esegui_animazione('animations/Stand/Emotions/Negative/Humiliated_1');\n"
        u"   Se 'Piede destro pestato', esegui: corpo.fermati(); corpo.imposta_colore_occhi('red'); corpo.gira(0.5); voce.parla('Ahi!'); corpo.esegui_animazione('animations/Stand/Emotions/Negative/Humiliated_1');\n"
        u"6. VISIONE: Se leggi 'Vedo chiaramente: [oggetto]', commentalo con voce.parla().\n\n"
        u"LIMITAZIONE COMANDI: corpo.cammina(x,gira), corpo.gira(v), corpo.fermati(), corpo.guarda(x,y), voce.parla(t), vista.apprendi_volto(n), corpo.esegui_animazione(p).\n"
        u"Se non ci sono novità, scrivi solo 'pass'."
    ).format(nome_u, nome_u, nome_u)

    payload = {"model": "gpt-4o-mini", "messages": [{"role": "system", "content": prompt}, {"role": "user", "content": contesto}], "temperature": 0.0}
    try:
        res = requests.post(url, headers=headers, data=json.dumps(payload), timeout=5)
        codice = res.json()['choices'][0]['message']['content'].strip().replace("```python", "").replace("```", "").strip()
        if codice and not any(cmd in codice for cmd in ["corpo.", "voce.", "vista.", "pass"]):
            return u"voce.parla('{}');".format(codice.replace("'", ""))
        return codice if codice else "pass"
    except: return "pass"

def main():
    global messaggio_utente, memoria_fisica, gia_salutata
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

        while True:
            mondo = sensi.ottieni_report_semantico()

            # Se NAO è fermo, rendiamo gli ostacoli meno "urgenti" per l'Anima
            if not corpo.sta_camminando():
                mondo = mondo.replace(u"Ostacolo frontale molto vicino.", u"Vedo un ostacolo vicino, ma sono fermo.")
                mondo = mondo.replace(u"Ostacolo a sinistra.", u"C'è qualcosa a sinistra.")
                mondo = mondo.replace(u"Ostacolo a destra.", u"C'è qualcosa a destra.")

            if gia_salutata:
                mondo = mondo.replace(u"Riconosco Giulia.", u"Giulia e' presente.")
                mondo = mondo.replace(u"Vedo un volto ignoto.", u"")

            if messaggio_utente:
                mondo += u" L'utente dice: '{}'.".format(messaggio_utente)
                messaggio_utente = ""

            if u"Ostacolo frontale" in mondo and corpo.sta_camminando():
                corpo.fermati()
                if corpo.scatta_foto():
                    mondo += u" Vedo chiaramente: {}.".format(analizza_immagine("visione_nao.jpg"))
                    try: os.remove("visione_nao.jpg")
                    except: pass
                time.sleep(2.0)

            if mondo != stato_precedente and mondo != "REPORT: ":
                print(u"\n[SENSORI]: " + mondo)
                azione = genera_codice_anima(mondo, memoria_fisica)
                if azione != "pass":
                    print(u"[ANIMA]: " + azione)
                    if "Ciao" in azione: gia_salutata = True
                    try: exec (azione, {"corpo": corpo, "voce": voce, "vista": vista, "sistema": sistema, "True": True, "False": False})
                    except Exception as e: print(u"Errore: " + str(e))
                stato_precedente = mondo
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