
Conversation avec Gemini
ma zendure ac1600 n'obéit pas aux ordre d'ahome assistant, l'hems est désactivé et le mqqt fonctionne

C'est un classique du comportement de l'Ace 1500 / AIO 2400 avec l'intégration Home Assistant via MQTT. Le fait de lire les données remonte bien, mais les consignes de charge ou de puissance de sortie ne s'appliquent pas.  
YouTube

Voici les points de blocage spécifiques à contrôler :

1. Mode de fonctionnement dans l'application Zendure  
YouTube

Mode Manuel obligatoire : Dans l'app Zendure, assure-toi que le système est configuré en Mode Manuel (Custom/Manual Mode). Si l'appareil est resté configuré sur un mode planifié (ex: Heures Creuses / Heures Pleines) ou Automatique, le firmware interne rejette ou écrase instantanément les ordres reçus par MQTT.

2. Verrouillage du cluster et mode Local/Cloud

Attribution du Cluster : Dans les entités de l'intégration Zendure sur HA, vérifie que le paramètre Device Cluster est bien sélectionné et configuré. Sans cette attribution, le broker local refuse les commandes d'écriture.

Option de communication dans l'app Zendure : Va dans l'application mobile > Paramètres de l'appareil > MQTT Local. Vérifie que le commutateur est bien activé et que la bascule est configurée sur le bon mode de transmission.  
YouTube

3. Droits d'écriture MQTT et réitération des commandes

Identifiants du Broker : Assure-toi que l'utilisateur HA créé pour le Broker MQTT a les droits d'écriture complets et n'est pas bridé en lecture seule.

Délai de traitement du Firmware : Le microcontrôleur des systèmes SolarFlow met parfois du temps à appliquer les états MQTT basculés. Tente d'envoyer la commande de puissance, puis bascule un switch binaire secondaire (ex: activer/désactiver le bouton de charge AC) pour forcer le contrôleur à appliquer la consigne.

4. Redémarrage propre

Coupe l'alimentation de l'Ace 1500 (éteins la batterie complètement via le bouton physique) pendant 30 secondes.

Redémarre le module complémentaire Mosquitto Broker dans Home Assistant.

Rallume l'Ace 1500.

Quelle méthode ou quelle intégration HACS tu utilises actuellement pour remonter ton système (FireSon/Zendure-HA ou l'intégration officielle API) ?

comment optimiser la charge decharge de la batterie ? j'ai un abonnement heures creuses des panneaux solaire et un captuer de consommation globale de la maison shekky pro

Pour optimiser la charge et la décharge de ta batterie Zendure Ace 1600 avec un compteur Shelly Pro (EM / 3EM) et un tarif Heures Creuses (HC), la logique repose sur trois règles prioritaires automatisables dans Home Assistant :

1. La stratégie d'automatisation
Priorité 1 — Couvrir le talon de consommation (En heures pleines)

Comportement : La batterie injecte exactement la puissance consommée par la maison lue en temps réel sur le Shelly Pro.

Consigne : Si Puissance Shelly > 0 W, alors Consigne Zendure = Puissance Shelly (dans la limite de la puissance max de l'Ace 1600, soit 800 W ou 1200 W selon ton contrat/onduleur).

But : Annuler la facture d'électricité aux heures où le kWh est cher.

Priorité 2 — Charger sur l'excédent Solaire (Journée)

Comportement : Dès que le Shelly détecte une réinjection vers le réseau (puissance négative), la batterie absorbe le surplus.

Consigne : Si Puissance Shelly < -50 W, augmenter la charge AC/DC du Zendure de cette valeur.

Priorité 3 — Recharger sur le secteur (En heures creuses la nuit, en hiver)

Comportement : En hiver ou lors des journées grises, la batterie se charge sur le réseau pendant tes Heures Creuses nocturnes pour restituering cette énergie le matin pendant les Heures Pleines.

Condition : Automatiser la charge AC nocturne uniquement si les prévisions solaires du lendemain (via l'intégration Forecast.Solar dans HA) sont faibles. Si le soleil est prévu le lendemain, on laisse la batterie vide pour absorber le photovoltaïque.

2. Comment le mettre en place dans Home Assistant ?
Deux méthodes s'offrent à toi selon ton niveau sur Home Assistant :

Option A : L'intégration dédiée "Solar Optimizer" ou "PV PC" (La plus simple)
En passant par HACS, tu peux installer Solar Optimizer ou Power Flow Card / EMHASS.

Tu déclares ton Shelly Pro comme capteur de réseau (Grid Power).

Tu définis la batterie Zendure comme charge ajustable.

L'intégration calcule seule la consigne à envoyer toutes les X secondes à l'Ace 1600.

Option B : Automatisation YAML avec boucle de régulation (Zero Grid)
Si tu gères toi-même les automatismes, crée une automatisation déclenchée sur chaque changement de valeur du Shelly Pro :

YAML
triggers:
  - trigger: state
    entity_id: sensor.shelly_pro_power
conditions: []
actions:
  - action: number.set_value
    target:
      entity_id: number.zendure_output_limit # Nom de ton entité MQTT Zendure
    data:
      value: >
        {% set current_grid = states('sensor.shelly_pro_power') | float(0) %}
        {% set current_output = states('number.zendure_output_limit') | float(0) %}
        {% set target = current_output + current_grid %}
        {{ [ [target, 0] | max, 800 ] | min }}
3. Les seuils de préservation de la batterie
Pour prolonger la durée de vie des cellules LiFePO4 de ton Ace 1600 :

Plage de fonctionnement recommandée : Conserve une décharge minimale à 10 % (SOC min) et une charge maximale à 95 % ou 100 % (avec un équilibrage des cellules une fois par mois).

Puissance de charge nocturne : Ne charge pas à la puissance maximale la nuit sur le réseau ; une charge lente (ex: 400 W à 600 W) réduit l'échauffement et améliore le rendement global.

As-tu déjà configuré les entités Heures Creuses / Heures Pleines dans le tableau de bord Énergie de ton Home Assistant ?

heures creuses: 22h30 - 06h30, sensor shelly: sensor.shelly_consommation01_power

Voici la configuration exacte adaptée à ton installation, à copier directement dans Home Assistant pour piloter ton Zendure Ace 1600 en fonction de ton Shelly Pro (sensor.shelly_consommation01_power) et de ta plage 22h30 - 06h30.

1. Déclarer le capteur d'Heures Creuses (dans configuration.yaml)
Ajoute un capteur binaire dans ton fichier configuration.yaml pour identifier précisément la période Heures Creuses :

YAML
binary_sensor:
  - platform: tod
    name: "Heures Creuses"
    after: "22:30"
    before: "06:30"
(Après sauvegarde, recharge la configuration YAML ou redémarre Home Assistant).

2. Automatisation 1 : Gestion de la décharge (Zero Injection) en Heures Pleines
Pendant les Heures Pleines (06h30 - 22h30), la batterie s'ajuste en temps réel pour annuler la consommation de la maison mesurée par le Shelly.

YAML
alias: "Zendure - Régulation Décharge (Heures Pleines)"
description: "Ajuste la puissance de sortie du Zendure pour couvrir la consommation de la maison"
trigger:
  - trigger: state
    entity_id: sensor.shelly_consommation01_power
condition:
  - condition: state
    entity_id: binary_sensor.heures_creuses
    state: "off" # Actif uniquement en Heures Pleines
  - condition: numeric_state
    entity_id: sensor.zendure_battery_soc # Remplace par ton entité de batterie %
    above: 10 # Ne décharge pas sous 10%
action:
  - action: number.set_value
    target:
      entity_id: number.zendure_output_limit # Remplace par ton entité MQTT de consigne de sortie
    data:
      value: >
        {% set grid = states('sensor.shelly_consommation01_power') | float(0) %}
        {% set current_out = states('number.zendure_output_limit') | float(0) %}
        {% set target = current_out + grid %}
        {# Borne la puissance entre 0W et 800W max #}
        {{ [ [target, 0] | max, 800 ] | min | int }}
3. Automatisation 2 : Charge intelligente la nuit (Heures Creuses)
À 22h30, si la batterie est faible et que peu de soleil est prévu le lendemain, l'Ace 1600 se charge sur le réseau pour être prêt au réveil.

Prérequis conseillé : Activer l'intégration gratuite Forecast.Solar dans Home Assistant pour obtenir l'entité sensor.power_production_tomorrow.

YAML
alias: "Zendure - Charge Nocturne en Heures Creuses"
description: "Charge la batterie à 22h30 si le soleil du lendemain ne suffira pas"
trigger:
  - trigger: time
    at: "22:31:00"
condition:
  - condition: numeric_state
    entity_id: sensor.zendure_battery_soc # Remplace par ton entité de % batterie
    below: 50 # Charge la nuit uniquement si la batterie est à moins de 50%
  - condition: numeric_state
    entity_id: sensor.power_production_tomorrow # Prévision solaire du lendemain (en kWh)
    below: 6 # Ajuste selon la puissance totale de tes panneaux
action:
  # Activer la charge AC du Zendure
  - action: switch.turn_on
    target:
      entity_id: switch.zendure_ac_charge # Remplace par ton entité d'activation de charge AC
  # Régler une puissance de charge douce (ex: 500W pour préserver les cellules)
  - action: number.set_value
    target:
      entity_id: number.zendure_ac_charge_power
    data:
      value: 500
4. Automatisation 3 : Arrêt de la charge secteur au matin
À 06h30, la batterie arrête la charge AC pour repasser en mode décharge / absorption solaire.

YAML
alias: "Zendure - Fin Heures Creuses (Stop Charge AC)"
description: "Coupe la charge secteur à 06h30"
trigger:
  - trigger: time
    at: "06:30:00"
action:
  - action: switch.turn_off
    target:
      entity_id: switch.zendure_ac_charge
  - action: number.set_value
    target:
      entity_id: number.zendure_output_limit
    data:
      value: 0
Noms d'entités à vérifier
Avant d'enregistrer ces automatismes, vérifie dans Outils de développement > États le nom exact des entités fournies par ton intégration Zendure :

L'entité du pourcentage de batterie (sensor.zendure_..._soc ou battery_level).

L'entité pour définir la puissance de sortie (number.zendure_..._output_limit ou output_pack_power).

Le switch pour autoriser/couper la charge réseau (switch.zendure_..._ac_charge).

fait moi une intergration avecune interface de parametrage en GUI

Pour créer une interface de paramétrage complète et modifiable directement dans l'interface graphique (GUI) de Home Assistant sans retoucher au code YAML, nous allons utiliser les Entités Helper (Entrées) et un Dashboard Lovelace dédié.

Cette méthode te permettra d'ajuster dynamiquement à la volée le seuil de batterie minimale, la puissance max d'injection ou la prévision solaire déclenchante.

Étape 1 : Créer les paramètres dans l'interface (Entrées / Helpers)
Va dans Paramètres > Appareils et services > Entrées et clique sur + Créer une entrée pour ajouter les 4 champs suivants :

Seuil Batterie Min (Décharge)

Type : Nombre (Input Number)

Nom : Paramètre Zendure - SOC Min

Icône : mdi:battery-arrow-down

Min / Max / Pas : 5 / 30 / 5 (Unité: %)

Entité générée : input_number.parametre_zendure_soc_min

Puissance Décharge Max

Type : Nombre (Input Number)

Nom : Paramètre Zendure - Puissance Max Décharge

Icône : mdi:flash

Min / Max / Pas : 100 / 1200 / 50 (Unité: W)

Entité générée : input_number.parametre_zendure_puissance_max_decharge

Seuil Solaire Prévisionnel (Charge Nocturne)

Type : Nombre (Input Number)

Nom : Paramètre Zendure - Seuil Solaire Demain

Icône : mdi:weather-sunny

Min / Max / Pas : 1 / 20 / 1 (Unité: kWh)

Entité générée : input_number.parametre_zendure_seuil_solaire_demain

Interrupteur Général de Régulation Auto

Type : Interrupteur (Input Boolean)

Nom : Paramètre Zendure - Régulation Auto

Icône : mdi:robot

Entité générée : input_boolean.parametre_zendure_regulation_auto

Étape 2 : Créer le Tableau de Bord (GUI Dashboard)
Dans ton tableau de bord Lovelace, bascule en mode édition (3 petits points en haut à droite > Éditer le tableau de bord), clique sur + Ajouter une carte et choisis Manuel. Colle ce code YAML :

YAML
type: vertical-stack
cards:
  - type: entities
    title: ⚙️ Paramètres Zendure Ace 1600
    show_header_toggle: false
    entities:
      - entity: input_boolean.parametre_zendure_regulation_auto
        name: Activer la régulation automatique
      - entity: input_number.parametre_zendure_soc_min
        name: Seuil arrêt décharge (SOC Min)
      - entity: input_number.parametre_zendure_puissance_max_decharge
        name: Puissance max d'injection
      - entity: input_number.parametre_zendure_seuil_solaire_demain
        name: Seuil charge nocturne si solaire prévu <

  - type: glance
    title: 📊 État en direct
    entities:
      - entity: sensor.shelly_consommation01_power
        name: Reseau Maison
      - entity: binary_sensor.heures_creuses
        name: Heures Creuses
Étape 3 : Automatisation dynamique lisant les variables GUI
Crée une nouvelle automatisation dans Paramètres > Automatisations et scènes > Créer une automatisation (en mode YAML) :

YAML
alias: "Zendure - Régulation Auto (GUI Paramétrable)"
description: "Règle la décharge du Zendure d'après le Shelly et les seuils définis dans l'IHM"
trigger:
  - trigger: state
    entity_id: sensor.shelly_consommation01_power
condition:
  # Vérifie que la régulation est activée dans la GUI
  - condition: state
    entity_id: input_boolean.parametre_zendure_regulation_auto
    state: "on"
  # Uniquement en Heures Pleines
  - condition: state
    entity_id: binary_sensor.heures_creuses
    state: "off"
  # Vérifie que le SOC batterie est supérieur au seuil configuré dans l'IHM
  - condition: template
    value_template: >
      {{ states('sensor.zendure_battery_soc') | float(0) > states('input_number.parametre_zendure_soc_min') | float(0) }}
action:
  - action: number.set_value
    target:
      entity_id: number.zendure_output_limit
    data:
      value: >
        {% set grid = states('sensor.shelly_consommation01_power') | float(0) %}
        {% set current_out = states('number.zendure_output_limit') | float(0) %}
        {% set p_max = states('input_number.parametre_zendure_puissance_max_decharge') | float(800) %}
        
        {% set target = current_out + grid %}
        
        {# Ajustement dynamique entre 0 W et la limite réglée via la GUI #}
        {{ [ [target, 0] | max, p_max ] | min | int }}
met tout cela en .md et je ferai déployer par claude code

Note : Après l'ajout, rechargez les entités Time Option Digital (TOD) ou redémarrez Home Assistant.

3. Création des Entrées (Helpers GUI)
Pour permettre un réglage dynamique depuis l'interface sans modifier le code, créez les 4 entrées (Helpers) suivantes via Paramètres > Appareils et services > Entrées :

Type	Nom	Identifiant (Entity ID)	Min / Max / Pas	Unité / Valeur par défaut
Nombre	Paramètre Zendure - SOC Min	input_number.parametre_zendure_soc_min	5 / 30 / 5	% (Défaut: 10)
Nombre	Paramètre Zendure - Puissance Max Décharge	input_number.parametre_zendure_puissance_max_decharge	100 / 1200 / 50	W (Défaut: 800)
Nombre	Paramètre Zendure - Seuil Solaire Demain	input_number.parametre_zendure_seuil_solaire_demain	1 / 20 / 1	kWh (Défaut: 6)
Interrupteur	Paramètre Zendure - Régulation Auto	input_boolean.parametre_zendure_regulation_auto	-	on
4. Interface Graphique (Dashboard Lovelace)
Ajoutez une carte Manuel dans votre tableau de bord Lovelace :

YAML
type: vertical-stack
cards:
  - type: entities
    title: "⚙️ Paramètres Zendure Ace 1600"
    show_header_toggle: false
    entities:
      - entity: input_boolean.parametre_zendure_regulation_auto
        name: Activer la régulation automatique
      - entity: input_number.parametre_zendure_soc_min
        name: Seuil arrêt décharge (SOC Min)
      - entity: input_number.parametre_zendure_puissance_max_decharge
        name: Puissance max d'injection
      - entity: input_number.parametre_zendure_seuil_solaire_demain
        name: Seuil charge nocturne si solaire prévu <

  - type: glance
    title: "📊 État en direct"
    entities:
      - entity: sensor.shelly_consommation01_power
        name: Réseau Maison
      - entity: binary_sensor.heures_creuses
        name: Heures Creuses
      - entity: sensor.zendure_battery_soc
        name: Batterie Zendure
5. Automatisations Home Assistant (YAML)
Copiez ces trois automatisations dans votre fichier automations.yaml ou importez-les via l'IHM en mode YAML.

5.1. Régulation Dynamique (Zero Grid) en Heures Pleines
YAML
- id: zendure_regulation_dynamique_hp
  alias: "Zendure - Régulation Auto (GUI Paramétrable)"
  description: "Ajuste l'injection du Zendure selon le Shelly et les seuils configurés"
  trigger:
    - trigger: state
      entity_id: sensor.shelly_consommation01_power
  condition:
    - condition: state
      entity_id: input_boolean.parametre_zendure_regulation_auto
      state: "on"
    - condition: state
      entity_id: binary_sensor.heures_creuses
      state: "off"
    - condition: template
      value_template: >
        {{ states('sensor.zendure_battery_soc') | float(0) > states('input_number.parametre_zendure_soc_min') | float(0) }}
  action:
    - action: number.set_value
      target:
        entity_id: number.zendure_output_limit
      data:
        value: >
          {% set grid = states('sensor.shelly_consommation01_power') | float(0) %}
          {% set current_out = states('number.zendure_output_limit') | float(0) %}
          {% set p_max = states('input_number.parametre_zendure_puissance_max_decharge') | float(800) %}
          {% set target = current_out + grid %}
          {{ [ [target, 0] | max, p_max ] | min | int }}
5.2. Charge Secteur Nocturne (Heures Creuses)
YAML
- id: zendure_charge_nocturne_hc
  alias: "Zendure - Charge Nocturne en Heures Creuses"
  description: "Charge la batterie la nuit si le niveau est faible et le solaire de demain suffisant peu"
  trigger:
    - trigger: time
      at: "22:31:00"
  condition:
    - condition: state
      entity_id: input_boolean.parametre_zendure_regulation_auto
      state: "on"
    - condition: numeric_state
      entity_id: sensor.zendure_battery_soc
      below: 50
    - condition: template
      value_template: >
        {{ states('sensor.power_production_tomorrow') | float(0) < states('input_number.parametre_zendure_seuil_solaire_demain') | float(6) }}
  action:
    - action: switch.turn_on
      target:
        entity_id: switch.zendure_ac_charge
    - action: number.set_value
      target:
        entity_id: number.zendure_ac_charge_power
      data:
        value: 500
5.3. Fin des Heures Creuses (Arrêt Charge AC)
YAML
- id: zendure_stop_charge_hc
  alias: "Zendure - Fin Heures Creuses (Stop Charge AC)"
  description: "Coupe la charge réseau à 06h30"
  trigger:
    - trigger: time
      at: "06:30:00"
  action:
    - action: switch.turn_off
      target:
        entity_id: switch.zendure_ac_charge
    - action: number.set_value
      target:
        entity_id: number.zendure_output_limit
      data:
        value: 0
6. Résolution des Problèmes & Dépannage
Si l'Ace 1600 n'obéit pas aux ordres MQTT transmis par Home Assistant :

Mode de fonctionnement app Zendure : S'assurer que le mode Manuel (Custom Mode) est activé. Les modes "Smart/Schedule" écrasent la consigne MQTT.

Device Cluster : Dans Home Assistant, vérifiez que l'entité Device Cluster de l'intégration Zendure est bien configurée.

Droits d'écriture MQTT : Vérifiez que l'utilisateur Mosquitto a les privilèges d'écriture sur le topic Zendure.

Reboot matériel :

Éteindre complètement l'Ace 1600 via le bouton physique pendant 30 secondes.

Redémarrer l'add-on Mosquitto Broker dans Home Assistant.

Rallumer l'Ace 1600.
"""

with open("zendure_ha_optimization.md", "w", encoding="utf-8") as f:
f.write(markdown_content)

print("File generated: zendure_ha_optimization.md")


```text?code_stdout&code_event_index=1
File generated: zendure_ha_optimization.md

Votre fichier Markdown est prêt.

Icône MD
zendure_ha_optimization
 MD 
Ouvert
Le fichier zendure_ha_optimization.md rassemble l'ensemble de la procédure, structuré pour être facilement déployé par Claude Code ou tout autre outil CLI :

Ce que contient le fichier Markdown :
Prérequis & Dépannage matériel (Mode Manuel Zendure, Cluster MQTT Local).

Capteur TOD (Time Of Day) pour gérer automatiquement la plage d'Heures Creuses (22h30 - 06h30).

Déclaration des 4 Helpers / Entrées GUI (input_number et input_boolean) avec leurs plages et identifiants exacts.

Code Lovelace YAML pour le tableau de bord interactif.

Les 3 Automatisations YAML intégrant la régulation en temps réel basée sur le Shelly (sensor.shelly_consommation01_power), les seuils dynamiques de l'IHM et la gestion de la charge nocturne contextuelle selon la météo solaire.




Gemini est une IA et peut se tromper, y compris sur des personnes. Votre confidentialité et GeminiS'ouvre dans une nouvelle fenêtre

Analyse…
# Guide d'Intégration & Optimisation Zendure Ace 1600 + Shelly Pro + Home Assistant

Ce document regroupe la procédure complète pour configurer, réguler et paramétrer l'optimisation de charge/décharge de la batterie **Zendure Ace 1600** avec un compteur **Shelly Pro** (`sensor.shelly_consommation01_power`) et un tarif **Heures Creuses (22h30 - 06h30)** dans **Home Assistant**.

---

## 📋 Table des Matières
1. [Prérequis & Préparation](#1-prérequis--préparation)
2. [Déclaration du Capteur Heures Creuses](#2-déclaration-du-capteur-heures-creuses)
3. [Création des Entrées (Helpers GUI)](#3-création-des-entrées-helpers-gui)
4. [Interface Graphique (Dashboard Lovelace)](#4-interface-graphique-dashboard-lovelace)
5. [Automatisations Home Assistant (YAML)](#5-automatisations-home-assistant-yaml)
6. [Résolution des Problèmes & Dépannage](#6-résolution-des-problèmes--dépannage)

---

## 1. Prérequis & Préparation

### Vérification du Matériel et des Intégrations
* **Zendure Ace 1600** : Connecté via MQTT Local (Broker Mosquitto) ou l'intégration HACS dédiée.
* **Shelly Pro** : Capteur de puissance globale disponible sous l'entité `sensor.shelly_consommation01_power`.
* **Application Zendure** :
  * Définir le mode de fonctionnement sur **Mode Manuel / Custom Mode** (*impératif pour que les consignes MQTT ne soient pas écrasées*).
  * Activer l'option **MQTT Local** dans les paramètres de l'appareil.

---

## 2. Déclaration du Capteur Heures Creuses

Ajoutez la configuration suivante dans votre fichier `configuration.yaml` pour identifier la plage d'Heures Creuses (22h30 - 06h30) :

```yaml
binary_sensor:
  - platform: tod
    name: "Heures Creuses"
    after: "22:30"
    before: "06:30"
```

> **Note :** Après l'ajout, rechargez les entités *Time Option Digital (TOD)* ou redémarrez Home Assistant.

---

## 3. Création des Entrées (Helpers GUI)

Pour permettre un réglage dynamique depuis l'interface sans modifier le code, créez les 4 entrées (*Helpers*) suivantes via **Paramètres > Appareils et services > Entrées** :

| Type | Nom | Identifiant (Entity ID) | Min / Max / Pas | Unité / Valeur par défaut |
| :--- | :--- | :--- | :--- | :--- |
| **Nombre** | Paramètre Zendure - SOC Min | `input_number.parametre_zendure_soc_min` | 5 / 30 / 5 | `%` (Défaut: 10) |
| **Nombre** | Paramètre Zendure - Puissance Max Décharge | `input_number.parametre_zendure_puissance_max_decharge` | 100 / 1200 / 50 | `W` (Défaut: 800) |
| **Nombre** | Paramètre Zendure - Seuil Solaire Demain | `input_number.parametre_zendure_seuil_solaire_demain` | 1 / 20 / 1 | `kWh` (Défaut: 6) |
| **Interrupteur** | Paramètre Zendure - Régulation Auto | `input_boolean.parametre_zendure_regulation_auto` | - | `on` |

---

## 4. Interface Graphique (Dashboard Lovelace)

Ajoutez une carte **Manuel** dans votre tableau de bord Lovelace :

```yaml
type: vertical-stack
cards:
  - type: entities
    title: "⚙️ Paramètres Zendure Ace 1600"
    show_header_toggle: false
    entities:
      - entity: input_boolean.parametre_zendure_regulation_auto
        name: Activer la régulation automatique
      - entity: input_number.parametre_zendure_soc_min
        name: Seuil arrêt décharge (SOC Min)
      - entity: input_number.parametre_zendure_puissance_max_decharge
        name: Puissance max d'injection
      - entity: input_number.parametre_zendure_seuil_solaire_demain
        name: Seuil charge nocturne si solaire prévu <

  - type: glance
    title: "📊 État en direct"
    entities:
      - entity: sensor.shelly_consommation01_power
        name: Réseau Maison
      - entity: binary_sensor.heures_creuses
        name: Heures Creuses
      - entity: sensor.zendure_battery_soc
        name: Batterie Zendure
```

---

## 5. Automatisations Home Assistant (YAML)

Copiez ces trois automatisations dans votre fichier `automations.yaml` ou importez-les via l'IHM en mode YAML.

### 5.1. Régulation Dynamique (Zero Grid) en Heures Pleines

```yaml
- id: zendure_regulation_dynamique_hp
  alias: "Zendure - Régulation Auto (GUI Paramétrable)"
  description: "Ajuste l'injection du Zendure selon le Shelly et les seuils configurés"
  trigger:
    - trigger: state
      entity_id: sensor.shelly_consommation01_power
  condition:
    - condition: state
      entity_id: input_boolean.parametre_zendure_regulation_auto
      state: "on"
    - condition: state
      entity_id: binary_sensor.heures_creuses
      state: "off"
    - condition: template
      value_template: >
        {{ states('sensor.zendure_battery_soc') | float(0) > states('input_number.parametre_zendure_soc_min') | float(0) }}
  action:
    - action: number.set_value
      target:
        entity_id: number.zendure_output_limit
      data:
        value: >
          {% set grid = states('sensor.shelly_consommation01_power') | float(0) %}
          {% set current_out = states('number.zendure_output_limit') | float(0) %}
          {% set p_max = states('input_number.parametre_zendure_puissance_max_decharge') | float(800) %}
          {% set target = current_out + grid %}
          {{ [ [target, 0] | max, p_max ] | min | int }}
```

### 5.2. Charge Secteur Nocturne (Heures Creuses)

```yaml
- id: zendure_charge_nocturne_hc
  alias: "Zendure - Charge Nocturne en Heures Creuses"
  description: "Charge la batterie la nuit si le niveau est faible et le solaire de demain suffisant peu"
  trigger:
    - trigger: time
      at: "22:31:00"
  condition:
    - condition: state
      entity_id: input_boolean.parametre_zendure_regulation_auto
      state: "on"
    - condition: numeric_state
      entity_id: sensor.zendure_battery_soc
      below: 50
    - condition: template
      value_template: >
        {{ states('sensor.power_production_tomorrow') | float(0) < states('input_number.parametre_zendure_seuil_solaire_demain') | float(6) }}
  action:
    - action: switch.turn_on
      target:
        entity_id: switch.zendure_ac_charge
    - action: number.set_value
      target:
        entity_id: number.zendure_ac_charge_power
      data:
        value: 500
```

### 5.3. Fin des Heures Creuses (Arrêt Charge AC)

```yaml
- id: zendure_stop_charge_hc
  alias: "Zendure - Fin Heures Creuses (Stop Charge AC)"
  description: "Coupe la charge réseau à 06h30"
  trigger:
    - trigger: time
      at: "06:30:00"
  action:
    - action: switch.turn_off
      target:
        entity_id: switch.zendure_ac_charge
    - action: number.set_value
      target:
        entity_id: number.zendure_output_limit
      data:
        value: 0
```

---

## 6. Résolution des Problèmes & Dépannage

Si l'Ace 1600 n'obéit pas aux ordres MQTT transmis par Home Assistant :

1. **Mode de fonctionnement app Zendure** : S'assurer que le mode Manuel (*Custom Mode*) est activé. Les modes "Smart/Schedule" écrasent la consigne MQTT.
2. **Device Cluster** : Dans Home Assistant, vérifiez que l'entité `Device Cluster` de l'intégration Zendure est bien configurée.
3. **Droits d'écriture MQTT** : Vérifiez que l'utilisateur Mosquitto a les privilèges d'écriture sur le topic Zendure.
4. **Reboot matériel** :
   * Éteindre complètement l'Ace 1600 via le bouton physique pendant 30 secondes.
   * Redémarrer l'add-on **Mosquitto Broker** dans Home Assistant.
   * Rallumer l'Ace 1600.
zendure_ha_optimization.md
Affichage de zendure_ha_optimization.md.
