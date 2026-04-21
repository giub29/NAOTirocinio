# -*- coding: utf-8 -*-
import requests, json, time, threading, base64
from hardware_control import NaoBody
from sensi import NaoSenses
from voice_interaction import NaoVoice
from vision_perception import NaoVision
from system_manager import NaoSystem

IP_ROBOT = "172.16.165.86"
CHIAVE_PRIVATA = "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"

messaggio_utente = ""

def ascolta_tastiera():
    global messaggio_utente
    while True:
        try:
            testo = raw_input()
            if testo.strip(): messaggio_utente = testo.decode('utf-8')
        except: pass

def analizza_immagine(percorso):
    try:
        with open(percorso, "rb") as f: img = base64.b64encode(f.read()).decode('utf-8')
        headers = {"Content-Type": "application/json", "Authorization": "Bearer " + CHIAVE_PRIVATA}
        payload = {"model": "gpt-4o-mini", "messages": [{"role": "user", "content": [{"type": "text", "text": "Cosa vedi? Max 10 parole."}, {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + img}}]}], "max_tokens": 50}
        res = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=10)
        return res.json()['choices'][0]['message']['content']
    except: return u"un oggetto ignoto"

def genera_codice_anima(contesto, memoria):
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Content-Type": "application/json", "Authorization": "Bearer " + CHIAVE_PRIVATA}
    prompt = (
        u"Sei l'anima di un robot NAO. Tu SEI il robot.\n\n"
        u"REGOLE CRITICHE:\n"
        u"1. SE l'utente dice 'Sono [Nome]', DEVI chiamare: vista.apprendi_volto('[Nome]'); voce.parla('Piacere di conoscerti!');\n"
        u"2. SE senti 'Piede pestato', DEVI fare: corpo.fermati(); voce.parla('Ahi!'); corpo.esegui_animazione('animations/Stand/Emotions/Negative/Humiliated_1');\n"
        u"3. SE SEI SEDUTO: Ignora ostacoli. Segui i volti con corpo.guarda(0,0). Rispondi a carezze.\n"
        u"4. SE IN MOVIMENTO: Se ostacolo frontale, fermati. Se a lato, usa corpo.gira(0.5) o corpo.gira(-0.5).\n"
        u"COMANDI: corpo.cammina(x,gira), corpo.gira(v), corpo.fermati(), corpo.guarda(x,y), voce.parla(t), vista.apprendi_volto(n).\n"
        u"Se non ci sono novità, scrivi 'pass'."
    )
    payload = {"model": "gpt-4o-mini", "messages": [{"role": "system", "content": prompt}, {"role": "user", "content": contesto}], "temperature": 0.0}
    try:
        res = requests.post(url, headers=headers, data=json.dumps(payload), timeout=5)
        codice = res.json()['choices'][0]['message']['content'].strip().replace("```python", "").replace("```", "").strip()
        return codice if codice else "pass"
    except: return "pass"

def main():
    corpo = None
    try:
        corpo = NaoBody(IP_ROBOT); sensi = NaoSenses(IP_ROBOT); voce = NaoVoice(IP_ROBOT)
        vista = NaoVision(IP_ROBOT); sistema = NaoSystem(IP_ROBOT)
        sistema.set_vita_autonoma(False); corpo.abilita_motori(); corpo.vai_in_posa("Crouch"); corpo.disabilita_motori()
        vista.cancella_volti(); vista.attiva_inseguimento_volto()
        threading.Thread(target=ascolta_tastiera).start()
        print(u"--- ANIMA PRONTA ---"); voce.parla("Sistemi pronti."); stato_precedente = ""

        while True:
            global messaggio_utente
            mondo = sensi.ottieni_report_semantico()
            if messaggio_utente: mondo += u" L'utente dice: '{}'.".format(messaggio_utente); messaggio_utente = ""

            if u"Ostacolo frontale" in mondo and corpo.sta_camminando():
                corpo.fermati()
                if corpo.scatta_foto(): mondo += u" Vedo chiaramente: {}.".format(analizza_immagine("visione_nao.jpg"))
                time.sleep(3.0)

            if mondo != stato_precedente and mondo != "REPORT: ":
                print(u"\n[SENSORI]: " + mondo)
                azione = genera_codice_anima(mondo, "")
                if azione != "pass":
                    print(u"[ANIMA]: " + azione)
                    try: exec (azione, {"corpo": corpo, "voce": voce, "vista": vista, "sistema": sistema, "True": True, "False": False})
                    except Exception as e: print(u"Errore: " + str(e))
                stato_precedente = mondo
            time.sleep(0.1)
    except: pass
    finally:
        if corpo: corpo.disabilita_motori()

if __name__ == "__main__": main()