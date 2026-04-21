# -*- coding: utf-8 -*-
from naoqi import ALProxy
import time

class NaoSenses:
    def __init__(self, ip, port=9559):
        self.memory = ALProxy("ALMemory", ip, port)
        self.ultimo_timestamp_audio = 0
        self.contatore_battiti = 0
        self.ultimo_battito_rilevato = 0
        self.finestra_ascolto = 2.0
        try:
            self.sonar = ALProxy("ALSonar", ip, port)
            self.sonar.subscribe("SensiAnima")
        except: pass

    def ottieni_report_semantico(self):
        eventi = []
        tempo_attuale = time.time()
        dati_volto = self.memory.getData("FaceDetected")
        nome_riconosciuto = "Sconosciuto"
        if dati_volto and len(dati_volto) > 1:
            for volto in dati_volto[1]:
                if len(volto) > 1 and len(volto[1]) >= 2:
                    if volto[1][2] != "": nome_riconosciuto = volto[1][2]
            if nome_riconosciuto != "Sconosciuto": eventi.append(u"Riconosco {}.".format(nome_riconosciuto))
            else: eventi.append(u"Vedo un volto ignoto.")

        dist_l = self.memory.getData("Device/SubDeviceList/US/Left/Sensor/Value")
        dist_r = self.memory.getData("Device/SubDeviceList/US/Right/Sensor/Value")
        if dist_l < 0.6 and dist_r < 0.6: eventi.append(u"Ostacolo frontale molto vicino.")
        elif dist_l < 0.6: eventi.append(u"Ostacolo a sinistra.")
        elif dist_r < 0.6: eventi.append(u"Ostacolo a destra.")

        if self.memory.getData("Device/SubDeviceList/Head/Touch/Middle/Sensor/Value") > 0:
            eventi.append(u"Sento una carezza sulla testa.")
        if self.memory.getData("Device/SubDeviceList/LFoot/Bumper/Left/Sensor/Value") > 0 or \
           self.memory.getData("Device/SubDeviceList/RFoot/Bumper/Right/Sensor/Value") > 0:
            eventi.append(u"Ahi! Piede pestato!")

        return u"REPORT: " + u" ".join(eventi)