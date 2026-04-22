# -*- coding: utf-8 -*-
from naoqi import ALProxy
import vision_definitions
from PIL import Image

class NaoBody:
    def __init__(self, ip, port=9559):
        self.ip = ip
        self.port = port
        self.motion = ALProxy("ALMotion", ip, port)
        self.posture = ALProxy("ALRobotPosture", ip, port)
        self.leds = ALProxy("ALLeds", ip, port)

    def abilita_motori(self):
        self.motion.wakeUp()
        print("--- SISTEMI MOTORI IN TIRO ---")

    def disabilita_motori(self):
        self.motion.rest()
        print("--- MOTORI RILASSATI (Antisurriscaldamento) ---")

    def vai_in_posa(self, posa):
        self.posture.goToPosture(posa, 0.5)

    def esegui_animazione(self, percorso):
        # Induriamo i motori prima dell'animazione
        self.motion.setStiffnesses("Body", 1.0)
        anim_proxy = ALProxy("ALAnimationPlayer", self.ip, self.port)
        anim_proxy.run(percorso)

    def gira(self, velocita):
        """Fa ruotare il robot attivando i motori"""
        self.motion.setStiffnesses("Body", 1.0)
        self.motion.moveToward(0.0, 0.0, velocita)

    def imposta_colore_occhi(self, colore):
        self.leds.fadeRGB("FaceLeds", colore, 0.1)

    def cammina(self, x, gira):
        self.motion.moveToward(x, 0.0, gira)

    def gira(self, angolo):
        """Fa ruotare il robot di un angolo fisso (in radianti) e si FERMA da solo"""
        self.motion.setStiffnesses("Body", 1.0)
        self.motion.moveTo(0.0, 0.0, angolo)

    def sta_camminando(self):
        return self.motion.moveIsActive()

    def fermati(self):
        self.motion.stopMove()

    def guarda(self, x, y):
        """Muove la testa (0,0 è il centro)"""
        try:
            self.motion.setStiffnesses("Head", 1.0)
            self.motion.angleInterpolationWithSpeed("HeadYaw", x, 0.2)
            self.motion.angleInterpolationWithSpeed("HeadPitch", y, 0.2)
        except: pass

    def scatta_foto(self, camera_id=0, nome_file="visione_nao.jpg"):
        name_id = ""
        try:
            cam_proxy = ALProxy("ALVideoDevice", self.ip, self.port)
            try: cam_proxy.setParam(18, camera_id)
            except: pass

            name_id = cam_proxy.subscribeCamera("Anima_Vision", camera_id, 2, 11, 5)
            nao_image = cam_proxy.getImageRemote(name_id)
            if nao_image:
                width = nao_image[0]; height = nao_image[1]; array = nao_image[6]
                im = Image.frombytes("RGB", (width, height), array)
                im.save(nome_file) # Salva con il nome fornito (es. sconosciuto.jpg)
                print("--- FOTO SALVATA: {} ---".format(nome_file))
                return True
            return False
        except Exception as e:
            print("Errore foto: " + str(e))
            return False
        finally:
            if name_id != "":
                cam_proxy.unsubscribe(name_id)