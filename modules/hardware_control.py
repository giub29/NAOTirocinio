# -*- coding: utf-8 -*-
from naoqi import ALProxy
import os
import io
import base64
from PIL import Image

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOTO_DIR = os.path.join(PROJECT_ROOT, "foto")


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
        try:
            self.posture.goToPosture(str(posa), 0.5)
        except Exception as e:
            print("--- ERRORE POSA: {} ---".format(e))

    def esegui_animazione(self, percorso):
        try:
            self.motion.setStiffnesses("Body", 1.0)
            anim_proxy = ALProxy("ALAnimationPlayer", self.ip, self.port)
            anim_proxy.run(str(percorso))
        except Exception as e:
            print("--- ERRORE ANIMAZIONE: {} ---".format(e))

    def cammina(self, x, gira):
        try:
            self.motion.setStiffnesses("Body", 1.0)
            self.motion.moveToward(float(x), 0.0, float(gira))
        except Exception as e:
            print("--- ERRORE CAMMINO: {} ---".format(e))

    def gira(self, angolo):
        try:
            self.motion.setStiffnesses("Body", 1.0)
            self.motion.moveTo(0.0, 0.0, float(angolo))
        except Exception as e:
            print("--- ERRORE ROTAZIONE: {} ---".format(e))

    def sta_camminando(self):
        try:
            return self.motion.moveIsActive()
        except:
            return False

    def fermati(self):
        try:
            self.motion.stopMove()
        except Exception as e:
            print("--- ERRORE STOP: {} ---".format(e))

    def guarda(self, x, y):
        try:
            self.motion.setStiffnesses("Head", 1.0)
            if y > -0.15:
                y = -0.15
            if y < -0.55:
                y = -0.55

            self.motion.angleInterpolationWithSpeed("HeadYaw", float(x), 0.2)
            self.motion.angleInterpolationWithSpeed("HeadPitch", float(y), 0.2)
        except Exception as e:
            print("--- ERRORE TESTA: {} ---".format(e))

    def imposta_colore_occhi(self, colore):
        colori = {
            "white": 0xFFFFFF,
            "red": 0xFF0000,
            "green": 0x00FF00,
            "blue": 0x0000FF,
            "yellow": 0xFFFF00,
            "purple": 0x800080,
            "cyan": 0x00FFFF
        }

        valore = colori.get(str(colore), 0xFFFFFF)

        try:
            self.leds.fadeRGB("FaceLeds", valore, 0.3)
        except Exception as e:
            print("--- ERRORE LED OCCHI: {} ---".format(e))

    def scatta_foto(self, camera_id=0, nome_file=None):
        name_id = ""
        cam_proxy = None

        try:
            cam_proxy = ALProxy("ALVideoDevice", self.ip, self.port)

            try:
                cam_proxy.setParam(18, camera_id)
            except:
                pass

            name_id = cam_proxy.subscribeCamera("Anima_Vision", camera_id, 2, 11, 5)
            nao_image = cam_proxy.getImageRemote(name_id)

            if nao_image:
                width = nao_image[0]
                height = nao_image[1]
                array = nao_image[6]

                im = Image.frombytes("RGB", (width, height), array)

                buffer = io.BytesIO()
                im.save(buffer, format="JPEG")
                img_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

                if nome_file:
                    cartella = FOTO_DIR

                    if not os.path.exists(cartella):
                        os.makedirs(cartella)

                    percorso_completo = os.path.join(cartella, nome_file)
                    im.save(percorso_completo)

                    print(
                        "--- FOTO ARCHIVIATA IN: {} ---".format(
                            percorso_completo
                        )
                    )

                return img_b64

            return None

        except Exception as e:
            print("Errore foto: " + str(e))
            return None

        finally:
            try:
                if cam_proxy and name_id != "":
                    cam_proxy.unsubscribe(name_id)
            except:
                pass
