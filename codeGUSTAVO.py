from machine import ADC, Pin, RTC
from time import sleep_ms, ticks_ms, ticks_diff
from math import log
import json
from LCD import CharLCD

S1 = Pin(13, Pin.IN, Pin.PULL_UP)   
S2 = Pin(14, Pin.IN, Pin.PULL_UP)  
S3 = Pin(15, Pin.IN, Pin.PULL_UP)                    

lcd = CharLCD(rs=2, en=4, d4=7, d5=8, d6=9, d7=10, cols=16, rows=2)
adc = ADC(Pin(27))                  # sonde CTN

# Variables globales 
VCC = 3.3
R1 = 1000                           
RREF = 2200                        
A1 = 3.354016e-3
B1 = 2.569850e-4
C1 = 2.620131e-6
D1 = 6.383091e-8
HEURES = 0
MINUTES = 0


# ----------------------------------------------------------------------
# Juste des trucs pour que je me dépe=éche dans le code
# Je fesais ça en C++ avec l'API d'arduino au lieu de faire des test plus longs et écrire plusieurs trucs
# ----------------------------------------------------------------------
def flecheLCD(col, ligne):
    lcd.set_cursor(col, ligne)
    lcd.message("->")
    sleep_ms(150)
    lcd.set_cursor(col, ligne)
    lcd.message("  ")
    sleep_ms(150)

def pressed(pin):
    """ça renvoie un true/false dépédamment de l'état du pin
    j'utilisais ça en C++ avec l'api d'arduino donc je me suis dit que je pouvais sauver des lignes et du temps avec ce truc"""
    return pin.value() == 0



# Les fonctions voilà normales qui font partie du code
def choixLangage() {
        if pressed(S1):
            print("Choisis le français comme langue")
        elif pressed(S3):
            print("anglais")
        else 
            print("français comme défault")
}

def choixHoraire():
    heure = 0
    minute = 0

    # --- Heures : S1 augmente, S3 valide ---
    lcd.clear()
    lcd.message("Heure :")
    while not pressed(S3):
        lcd.set_cursor(0, 1)
        # lcd.message("{:02d}".format(heure)) nous permet d'ajouter un 0 devant le chifre s'il est < 10
        # https://stackoverflow.com/questions/3377688/what-do-these-symbolic-strings-mean-02d-01d
        lcd.message("{:02d}".format(heure))
        if pressed(S1):
            heure += 1
            if heure == 24:
                heure = 0
            sleep_ms(200)
    sleep(3)                    # j'utilise un sleep de 3 secondes comme ça on a le temps de relacher le button

   # ici ducoup S1 += 1, s3 = valider (mode heure)
    # et donc on rajoute S2 -= 1 pour les minutes et les autres buttons gardent la meme chose 
    lcd.clear()
    lcd.message("Minutes :")
    while not pressed(S3):
        lcd.set_cursor(0, 1)
        # lcd.message("{:02d}".format(heure)) nous permet d'ajouter un 0 devant le chifre s'il est < 10
        # https://stackoverflow.com/questions/3377688/what-do-these-symbolic-strings-mean-02d-01d
        lcd.message("{:02d}".format(minute))
        if pressed(S1):
            minute += 1
            if minute == 60:
                minute = 0
            sleep_ms(200)
        if pressed(S2):
            minute -= 1
            if minute < 0:
                minute = 59
            sleep_ms(200)
    sleep_ms(300)

    RTC().datetime((2026, 1, 1, 0, heure, minute, 0, 0))
    lcd.clear()


# ----------------------------------------------------------------------
# Les menus suivants sont ducoup les menus des techniciens
# ----------------------------------------------------------------------
def modeSAV():
    offset = config["offset"]
    print("MODE SAV")

    def show():
        lcd.set_cursor(0, 0)
        lcd.message("{:<16}".format("{:+.1f}".format(offset)))

    lcd.clear()
    show()
    lcd.set_cursor(0, 1)
    lcd.message("+")
    lcd.set_cursor(8, 1)
    lcd.message("-")
    lcd.set_cursor(14, 1)
    lcd.message("OK")

    dernier_s3 = -10000

    while True:
        if pressed(S1):
            offset = round(offset + 0.1, 1)
            show()
            sleep_ms(200)

        if pressed(S2):
            offset = round(offset - 0.1, 1)
            show()
            sleep_ms(200)

        if pressed(S3):
            maintenant = ticks_ms()
            # 2 appuis sur S3 en moins d'1 seconde = on valide
            if ticks_diff(maintenant, dernier_s3) < 1000:
                sauvegarde({"offset": offset})
                print(offset)
                lcd.clear()
                return
            dernier_s3 = maintenant
            sleep_ms(250)

        sleep_ms(50)


def modeInstallation():
    # S1 = chauffage, S2 = clim, S3 = séchoir, puis S3 deux fois pour confirmer
    lcd.clear()
    lcd.set_cursor(3, 0)
    lcd.message("Chauffage")
    lcd.set_cursor(2, 1)
    lcd.message("Clim")
    lcd.set_cursor(9, 1)
    lcd.message("sechoir")

    choix = None
    while choix is None:
        if pressed(S1):
            choix = "chauffage"
            col, ligne = 1, 0
        elif pressed(S2):
            choix = "clim"
            col, ligne = 0, 1
        elif pressed(S3):
            choix = "sechoir"
            col, ligne = 7, 1
        sleep_ms(20)
    sleep_ms(400)                       # le temps de relâcher le bouton

    dernier_s3 = -10000
    while True:
        flecheLCD(col, ligne)           # la flèche clignote sur le mode choisi
        if pressed(S3):
            maintenant = ticks_ms()
            if ticks_diff(maintenant, dernier_s3) < 1000:
                sauvegarde({"mode": choix})
                lcd.clear()
                return choix
            dernier_s3 = maintenant
            sleep_ms(250)

# ----------------------------------------------------------------------
# PROGRAMME PRINCIPAL
# ----------------------------------------------------------------------
lecture()
mini, maxi = PLAGES_CONSIGNE[config["mode"]]
config["consigne"] = borner(config["consigne"], mini, maxi)

sleep_ms(300)                           # laisse le temps de lire les boutons au démarrage
if pressed(S1) and pressed(S2) and pressed(S3):
    modeSAV()
elif pressed(S1) and pressed(S2):
    modeInstallation()

lcd.clear()
temperature = None
etat_commande = False
derniere_mesure = -10000
consigne_modifiee = False
dernier_appui = 0

"""Au cas où l'utilisateur voudrait changer la langue (version rapide, pas optimale)"""
lcd.clear()
lcd.set_cursor(0, 0)
lcd.message("Langue : tenir")
lcd.set_cursor(0, 1)
lcd.message("S3 pendant 5 s")
sleep_ms(2000)                  # le temps de lire

if pressed(S3):
    sleep_ms(5000)
    if pressed(S3):
        choixLangue()
        while pressed(S3):      # attend le relâchement
            sleep_ms(10)

while True:
    maintenant = ticks_ms()

    # --- Réglage de la consigne par l'utilisateur ---
    pas = 0
    if pressed(S2):
        pas = PAS_CONSIGNE
    elif pressed(S1):
        pas = -PAS_CONSIGNE
    if pas != 0:
        mini, maxi = PLAGES_CONSIGNE[config["mode"]]
        config["consigne"] = borner(config["consigne"] + pas, mini, maxi)
        consigne_modifiee = True
        dernier_appui = maintenant
        afficher(temperature, etat_commande)
        sleep_ms(200)                   # anti-rebond et répétition

    # --- Sauvegarde unique, 3 s après le dernier appui (ménage la flash) ---
    if consigne_modifiee and ticks_diff(maintenant, dernier_appui) > DELAI_SAUVEGARDE_MS:
        sauvegarde({"consigne": config["consigne"]})
        consigne_modifiee = False

    # --- Mesure et régulation, une fois par seconde ---
    if ticks_diff(maintenant, derniere_mesure) >= 1000:
        derniere_mesure = maintenant
        temperature = lire_temperature()
        if temperature is None:
            etat_commande = False       # sécurité : on coupe la commande
        else:
            etat_commande = regule(temperature, config["consigne"],
                                   config["hysteresis"], etat_commande, config["mode"])
        commande.value(1 if etat_commande else 0)
        afficher(temperature, etat_commande)

    sleep_ms(20)
