# -*- coding: utf-8 -*-
from naoqi import ALProxy


class NaoVoice:
    def __init__(self, ip, port=9559):
        self.tts = ALProxy("ALTextToSpeech", ip, port)
        self.audio_player = ALProxy("ALAudioPlayer", ip, port)
        self.audio_device = ALProxy("ALAudioDevice", ip, port)

        # Impostazione lingua predefinita
        try:
            self.tts.setLanguage("Italian")
        except:
            self.tts.setLanguage("English")

    def parla(self, messaggio):
        from utils.text_utils import testo_per_voce
        testo = testo_per_voce(messaggio)

        # Python 2 compatibilità
        if isinstance(testo, unicode):
            testo = testo.encode('utf-8')

        print("NAO dice: " + testo)

        try:
            self.tts.say(testo)
        except Exception as e:
            print("[ERRORE VOCE]: {}".format(e))

    def imposta_volume(self, livello):
        """Livello da 0 a 100"""
        self.audio_device.setOutputVolume(livello)

    def riproduci_suono_sistema(self, nome_suono):
        self.audio_player.playSystemSound(nome_suono)