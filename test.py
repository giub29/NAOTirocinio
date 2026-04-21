# -*- coding: utf-8 -*-
import requests
import json
import time
import threading
from hardware_control import NaoBody
from sensi import NaoSenses
from voice_interaction import NaoVoice
from vision_perception import NaoVision
from system_manager import NaoSystem

IP_ROBOT = "nao.local"
CHIAVE_PRIVATA = "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"

messaggio_utente = ""


def ascolta_tastiera():
    global messaggio_utente
    while True:
        try:
            testo = raw_input()
            if testo.strip():
                messaggio_utente = testo.decode('utf-8')
        except:
            pass


def genera_codice_anima(contesto, dati_memoria):
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Content-Type": "application/json", "Authorization": "Bearer " + CHIAVE_PRIVATA}
    stringa_memoria = json.dumps(dati_memoria, ensure_ascii=False)

    prompt_sistema = (
            u"Sei l'anima di un robot NAO. Tu SEI il robot.\n\n"
            u"MEMORIA: " + stringa_memoria + u"\n\n"
                                             u"GERARCHIA REAZIONI (Eseguine SOLO UNA):\n"
                                             u"1. SE l'utente scrive 'Sono [Nome]': vista.apprendi_volto('[Nome]'); voce.parla('Piacere di conoscerti!')\n"
                                             u"2. BATTITI (PRIORITÀ MASSIMA):\n"
                                             u"   - 1 battito: voce.parla('Ti serve aiuto?'); corpo.guarda(0,0)\n"
                                             u"   - 2 battiti: corpo.abilita_motori(); corpo.vai_in_posa('Stand'); voce.parla('Mi alzo!')\n"
                                             u"   - 3 battiti: corpo.vai_in_posa('Crouch'); voce.parla('Mi riposo.'); corpo.disabilita_motori()\n"
                                             u"3. SE senti 'Piede pestato': voce.parla('Ahi!'); corpo.imposta_colore_occhi('red')\n"
                                             u"4. SE senti 'carezza': voce.parla('Che bello!'); corpo.esegui_animazione('animations/Stand/Gestures/Hey_1')\n"
                                             u"5. SE riconosci 'Giulia': se l'hai GIÀ salutata dall'ultimo avvio o spostamento, scrivi 'pass'.\n"
                                             u"6. SE vedi volto ignoto: se hai già chiesto il nome di recente, scrivi 'pass'.\n\n"
                                             u"REGOLE CRITICHE:\n"
                                             u"- Usa sempre ';' per unire più comandi.\n"
                                             u"- Se il report non contiene NOVITÀ FISICHE (nuovi tocchi o battiti), scrivi 'pass'.\n"
                                             u"- Per la carezza usa il percorso completo: 'animations/Stand/Gestures/Hey_1'."
    )

    payload = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "system", "content": prompt_sistema}, {"role": "user", "content": contesto}],
        "temperature": 0.1
    }

    try:
        res = requests.post(url, headers=headers, data=json.dumps(payload))
        risposta = res.json()
        codice = risposta['choices'][0]['message']['content'].strip()
        # PULIZIA: Rimuoviamo i blocchi markdown ma teniamo TUTTO il codice
        codice = codice.replace("```python", "").replace("```", "").replace("python", "")
        return codice.strip() if codice.strip() else "pass"  # <--- FIX: Restituisce tutto il blocco
    except:
        return "pass"


def main():
    corpo = NaoBody(IP_ROBOT);
    sensi = NaoSenses(IP_ROBOT)
    voce = NaoVoice(IP_ROBOT);
    vista = NaoVision(IP_ROBOT);
    sistema = NaoSystem(IP_ROBOT)

    sistema.set_vita_autonoma(False)
    corpo.abilita_motori()
    corpo.vai_in_posa("Crouch")
    vista.cancella_volti()
    vista.attiva_inseguimento_volto()

    thread_udito = threading.Thread(target=ascolta_tastiera)
    thread_udito.daemon = True
    thread_udito.start()

    print(u"--- ANIMA PRONTA ---")
    voce.parla("Sono pronto.")
    stato_precedente = ""

    while True:
        global messaggio_utente
        mondo = sensi.ottieni_report_semantico()
        if messaggio_utente:
            mondo += u" L'utente dice: '{}'.".format(messaggio_utente)
            messaggio_utente = ""

        if mondo != stato_precedente:
            print(u"\n[SENSORI]: " + mondo)
            codice_azione = genera_codice_anima(mondo, sistema.leggi_memoria())
            if codice_azione != "pass":
                print(u"[ANIMA]: " + codice_azione)
                try:
                    exec (codice_azione,
                          {"corpo": corpo, "voce": voce, "vista": vista, "sistema": sistema, "True": True,
                           "False": False})
                except Exception as e:
                    print(u"Errore: " + str(e))
            stato_precedente = mondo
        time.sleep(0.1)


if __name__ == "__main__":
    main()