# -*- coding: utf-8 -*-
from naoqi import ALProxy


class NaoVoice:
    def __init__(self, ip, port=9559):
        self.tts = ALProxy("ALTextToSpeech", ip, port)
        self.audio_player = ALProxy("ALAudioPlayer", ip, port)
        self.audio_device = ALProxy("ALAudioDevice", ip, port)

        self.speech = None
        self.memory = None
        self.ascolto_attivo = False

        try:
            self.tts.setLanguage("Italian")
        except:
            self.tts.setLanguage("English")

        try:
            self.memory = ALProxy("ALMemory", ip, port)
            self.speech = ALProxy("ALSpeechRecognition", ip, port)

            try:
                self.speech.pause(True)
            except:
                pass

            try:
                self.speech.setLanguage("Italian")
            except:
                self.speech.setLanguage("English")

            parole = [
                "vai",
                "cammina",
                "fermati",
                "stop",
                "stato"
            ]

            self.speech.setVocabulary(parole, False)

        except Exception as e:
            print("[VOCE] Riconoscimento vocale non disponibile: {}".format(e))
            self.speech = None
            self.memory = None

    def parla(self, messaggio):
        from utils.text_utils import testo_per_voce
        from soul import utente_sta_scrivendo

        if utente_sta_scrivendo:
            return

        testo = testo_per_voce(messaggio)

        if isinstance(testo, unicode):
            testo = testo.encode('utf-8')

        print("NAO dice: " + testo)

        try:
            self.tts.say(testo)
        except Exception as e:
            print("[ERRORE VOCE]: {}".format(e))

    def imposta_volume(self, livello):
        self.audio_device.setOutputVolume(livello)

    def riproduci_suono_sistema(self, nome_suono):
        self.audio_player.playSystemSound(nome_suono)

    def avvia_ascolto_comandi(self):
        if not self.speech:
            return False

        if self.ascolto_attivo:
            return True

        try:
            self.speech.pause(True)

            try:
                self.speech.unsubscribe("NaoVoiceCommand")
            except:
                pass

            self.speech.subscribe("NaoVoiceCommand")
            self.speech.pause(False)

            self.ascolto_attivo = True
            print("[VOCE] Ascolto comandi vocali attivo")
            return True

        except Exception as e:
            print("[VOCE] Errore avvio ascolto: {}".format(e))
            self.ascolto_attivo = False
            return False

    def ferma_ascolto_comandi(self):
        if not self.speech:
            return

        try:
            self.speech.pause(True)
            self.speech.unsubscribe("NaoVoiceCommand")
        except:
            pass

        self.ascolto_attivo = False

    def leggi_comando_vocale(self, soglia=0.30):
        if not self.memory:
            return ""

        try:
            dato = self.memory.getData("WordRecognized")
            print("[VOCE DEBUG] WordRecognized: {}".format(dato))
        except:
            return ""

        if not dato or len(dato) < 2:
            return ""

        parola = dato[0]
        confidenza = dato[1]

        try:
            parola = parola.lower().strip()
        except:
            return ""

        if confidenza < soglia:
            return ""

        if parola in ["vai", "cammina"]:
            return "vai"

        if parola in ["fermati", "stop"]:
            return "stop"

        if parola == "stato":
            return "status"

        return ""