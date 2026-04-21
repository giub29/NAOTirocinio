# -*- coding: utf-8 -*-
from naoqi import ALProxy

class NaoVision:
    def __init__(self, ip, port=9559):
        self.video = ALProxy("ALVideoDevice", ip, port)
        self.face_det = ALProxy("ALFaceDetection", ip, port)
        self.tracker = ALProxy("ALTracker", ip, port)
        self.recognition = ALProxy("ALVisionRecognition", ip, port)

    def attiva_inseguimento_volto(self):
        """Il robot segue il volto con la testa"""
        self.tracker.registerTarget("Face", 0.1)
        self.tracker.track("Face")
        print("--- TRACKING VOLTO ATTIVO ---")

    def disattiva_inseguimento(self):
        self.tracker.stopTracker()
        self.tracker.unregisterAllTargets()

    def imposta_parametri_camera(self, camera_id, risoluzione, fps):
        """Camera 0 (sopra), Camera 1 (sotto)"""
        self.video.setParam(camera_id, risoluzione, fps)

    def apprendi_volto(self, nome):
        """
        Tenta di memorizzare il volto aspettando che la testa sia ferma,
        con tentativi multipli in caso di foto mossa.
        """
        import time  # Aggiungilo qui se non c'è all'inizio del file

        print(u"--- INIZIO PROCEDURA APPRENDIMENTO PER: {} ---".format(nome))

        # 1. PAUSA STRATEGICA: Diamo al Tracker 1.5 secondi per inquadrare bene il viso e fermare il collo
        time.sleep(1.5)

        # 2. TENTATIVI MULTIPLI: Proviamo a scattare per 4 volte
        for tentativo in range(4):
            try:
                risultato = self.face_det.learnFace(nome)
                if risultato:
                    print(u"--- VOLTO DI {} MEMORIZZATO CON SUCCESSO! ---".format(nome))
                    return True
                else:
                    print(u"Tentativo {}/4 fallito: Viso non nitido. Riprovo...".format(tentativo + 1))
                    time.sleep(1)  # Aspetta un secondo prima della prossima foto
            except Exception as e:
                print(u"Errore API Fotocamera: " + str(e))
                return False

        print(u"--- ERRORE DEFINITIVO: Impossibile memorizzare il volto. Riavvicinati e riprova. ---")
        return False

    def cancella_volti(self):
        """Pulisce il database dei volti memorizzati (opzionale)"""
        self.face_det.clearDatabase()