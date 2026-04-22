from naoqi import ALProxy
IP = "172.16.165.86"
motion = ALProxy("ALMotion", IP, 9559)
motion.rest()
print("Robot a riposo. Motori rilassati.")