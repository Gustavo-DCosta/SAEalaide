from machine import ADC, Pin, RTC
from time import sleep_ms, ticks_ms, ticks_diff
from math import log
import json
from LCD import CharLCD

S1 = Pin(13, Pin.IN, Pin.PULL_UP)   
S2 = Pin(14, Pin.IN, Pin.PULL_UP)  
S3 = Pin(15, Pin.IN, Pin.PULL_UP)   
PIN_COMMANDE = 22                   

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
# ----------------------------------------------------------------------
# CONFIGURATION (sauvegardée en flash dans config.json)
# ----------------------------------------------------------------------
config = {
    "mode": "chauffage",            # "chauffage" | "clim" | "sechoir"
    "langue": "francais",           # "francais" | "anglais"
    "offset": 0.0,                  # étalonnage en °C, ex : -2.5 à +2.5
    "hysteresis": 0.4,              # °C, 0.0 à 2.0
    "consigne": 20.0,               # °C, dépend du mode
}


def lecture():
    """Recharge la config depuis la flash. Garde les valeurs par défaut sinon."""
    try:
        with open("config.json") as f:
            config.update(json.load(f))
    except (OSError, ValueError):
        print("Pas de sauvegarde, valeurs par défaut")


def sauvegarde(changement):
    """
    Un seul argument : un dictionnaire avec la rubrique et sa valeur.
    Exemples : sauvegarde({"offset": 0.3})
               sauvegarde({"langue": "anglais"})
    """
    for cle in changement:
        if cle not in config:
            print("Rubrique inconnue :", cle)
            return
    config.update(changement)
    with open("config.json", "w") as f:
        json.dump(config, f)


# ----------------------------------------------------------------------
# OUTILS
# ----------------------------------------------------------------------
def pressed(pin):
    """ça renvoie un true/false dépédamment de l'état du pin
    j'utilisais ça en C++ avec l'api d'arduino donc je me suis dit que je pouvais sauver des lignes et du temps avec ce truc"""
    return pin.value() == 0


def borner(valeur, mini, maxi):
    """Force valeur à rester entre mini et maxi."""
    return max(mini, min(maxi, valeur))

def choixLangage() {
        if pressed(S1):
            print("Choisis le français comme langue")
        elif pressed(S3):
            print("anglais")
        else 
            print("français comme défault")
}

def lire_temperature():
    """Température en °C (offset inclus), ou None si le capteur est en défaut."""
    total = 0
    for _ in range(NB_MOYENNES):
        total += adc.read_u16()
    v = (total / NB_MOYENNES) * VCC / 65535
    if v <= 0.01 or v >= VCC - 0.01:    # capteur débranché ou court-circuité
        return None
    r = R1 * (VCC - v) / v              # résistance de la CTN (pont diviseur)
    l = log(r / RREF)
    tk = 1 / (A1 + B1 * l + C1 * l * l + D1 * l * l * l)   # Steinhart-Hart
    return tk - 273.15 + config["offset"]


def regule(temp, consigne, hysteresis, etat, mode):
    """
    Retourne True si la commande doit être active.
    Dans la zone morte (consigne +/- hysteresis/2), on garde l'état précédent.
    """
    demi = hysteresis / 2
    if mode == "clim":                  # la clim refroidit : logique inversée
        if temp > consigne + demi:
            return True
        if temp < consigne - demi:
            return False
    else:                               # chauffage ou séchoir
        if temp < consigne - demi:
            return True
        if temp > consigne + demi:
            return False
    return etat


def regler_heure(heure, minute):
    """À appeler une fois depuis Thonny, ex : regler_heure(14, 5)."""
    RTC().datetime((2026, 1, 1, 0, heure, minute, 0, 0))


def afficher(temp, etat):
    """Écran principal : température réelle, heure, consigne, état de la commande."""
    h, m = RTC().datetime()[4:6]
    lcd.set_cursor(0, 0)
    if temp is None:
        lcd.message("{:<16}".format("Err capteur"))
    else:
        lcd.message("Temp {:4.1f}C {:02d}:{:02d}".format(temp, h, m))
    lcd.set_cursor(0, 1)
    lcd.message("Cons {:4.1f}C {:>5}".format(config["consigne"], "ON" if etat else "OFF"))


# ----------------------------------------------------------------------
# MENUS TECHNICIENS (à reprendre à l'étape suivante)
# ----------------------------------------------------------------------
def modeSAV():
    print("TODO : menu SAV (étalonnage)")


def modeInstallation():
    print("TODO : menu installation (mode + hystérésis)")


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
