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

    prompt = (
        u"Sei l'anima di NAO. Tu SEI il robot.\n"
        u"STATO ATTUALE: Sei FERMO. Non camminare di tua iniziativa.\n\n"
        u"REGOLE DI OUTPUT E SINTASSI (CRITICHE):\n"
        u"1. Rispondi SOLO con codice Python eseguibile. NIENTE testo libero.\n"
        u"2. Usa i DOPPI APICI per il testo, es: voce.parla(\"Testo\").\n\n"
        u"REGOLE SOCIALI:\n"
        u"1. Se 'Riconosco [Nome]', saluta con voce.parla(\"Ciao [Nome]!\"). Se leggi 'e\\' presente', NON salutare più.\n"
        u"2. Se 'volto ignoto', chiedi chi è. Se l'utente dice 'Sono [Nome]', esegui: vista.apprendi_volto(\"[Nome]\");\n\n"
        u"REGOLE DI SCHIVATA E NAVIGAZIONE (AUTONOMA):\n"
        u"1. PARTENZA: SE l'utente dice 'vai' o 'cammina', DEVI eseguire: corpo.vai_in_posa(\"Stand\"); corpo.cammina(0.3, 0.0); voce.parla(\"Inizio l'esplorazione!\");\n"
        u"2. STOP: SE l'utente dice 'stop' o 'fermati', DEVI eseguire: corpo.fermati(); corpo.vai_in_posa(\"Crouch\"); voce.parla(\"Mi fermo e mi riposo.\");\n"
        u"3. SCHIVATA LATERALE: SE stai camminando e leggi:\n"
        u"   - 'Ostacolo a sinistra': DEVI curvare a destra con corpo.cammina(0.2, -0.4); voce.parla(\"Devio a destra.\");\n"
        u"   - 'Ostacolo a destra': DEVI curvare a sinistra con corpo.cammina(0.2, 0.4); voce.parla(\"Devio a sinistra.\");\n"
        u"4. FINE OSTACOLO: SE stavi curvando e il report NON mostra più ostacoli, DEVI rimetterti dritto: corpo.cammina(0.3, 0.0);\n"
        u"5. OSTACOLO FRONTALE: SE leggi 'Vedo chiaramente: [oggetto]', significa che ti sei fermato davanti a un muro/oggetto. DEVI aggirarlo ripartendo così: corpo.gira(1.0); corpo.cammina(0.3, 0.0); voce.parla(\"Cerco di aggirare questo ostacolo.\");\n"
        u"6. SICUREZZA: Se sei FERMO, NON muovere mai le gambe per schivare ostacoli.\n\n"
        u"REAZIONI FISICHE:\n"
        u"- CAREZZA: esegui corpo.fermati(); voce.parla(\"Che bello!\"); corpo.esegui_animazione(\"animations/Stand/Gestures/Hey_1\");\n"
        u"- PIEDE SINISTRO: corpo.fermati(); corpo.imposta_colore_occhi(\"red\"); corpo.gira(-0.5); voce.parla(\"Ahi!\");\n"
        u"- PIEDE DESTRO: corpo.gira(0.5) con il resto uguale.\n\n"
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