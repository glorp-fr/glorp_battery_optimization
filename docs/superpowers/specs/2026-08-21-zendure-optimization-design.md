# Glorp's Battery Optimization — Design

## Contexte

`battery_smartflow_ai` (l'intégration tierce utilisée jusqu'ici pour piloter une batterie
Zendure AC1600 depuis Home Assistant) s'est révélée câblée pour un modèle d'entités qui
n'existe plus dans `zendure_ha` : elle pilote un mode select "input/output" et deux limites
séparées, alors que la version actuelle de `zendure_ha` expose un unique nombre signé au
niveau "manager" (`number.<device>_manual_power`, positif = décharge, négatif = charge, actif
en mode `manual`).

Investigation en direct (session du 2026-08-21) : même corrigé (pont de traduction, MQTT,
mode de connexion), le chemin "manager" ne traduit jamais la décision interne
(`Charge => setpoint -800W` bien logué) en commande réelle vers l'appareil — vérifié y compris
après réinstallation complète de `zendure_ha` depuis zéro. En revanche, écrire **directement**
sur les entités **device** (`select.<device>_ac_mode` avec options `input`/`output`,
`number.<device>_input_limit`, `number.<device>_output_limit`, toutes deux non signées)
fonctionne de façon fiable et immédiate — confirmé par une charge réelle mesurée
(~498 W pour une consigne de 500 W).

Décision : construire notre propre intégration d'optimisation, qui pilote **directement** ces
entités device de `zendure_ha` (déjà installé et qui lui, fonctionne pour la lecture ET pour
ces entités précises), plutôt que de continuer à réparer/contourner la couche manager.

## Périmètre

- **Couche d'optimisation par-dessus `zendure_ha`**, pas un pilote qui reparle lui-même en
  MQTT/cloud à l'appareil. `zendure_ha` reste responsable de la communication avec le
  matériel ; cette intégration se contente de lire/écrire ses entités device.
- **Générique multi-modèle / multi-appareil Zendure** : les références d'entités (mode AC,
  limites, SOC) sont sélectionnées par l'utilisateur via le config flow, pas câblées en dur.
  Les caractéristiques de l'appareil (puissance max charge/décharge, capacité) sont saisies
  manuellement — pas de base de profils par modèle à maintenir.
- **Un appareil Zendure par entrée de configuration** (comme `battery_smartflow_ai`). Pas de
  coordination multi-appareils dans cette v1.
- Pensée pour publication **HACS** dès le départ (structure de repo, `hacs.json`, manifest
  correct) même si l'usage immédiat reste personnel.
- Code et clés en **anglais** (convention HA/HACS), traduction `fr` fournie.

## Stratégies v1

Évaluées dans cet ordre de priorité à chaque cycle (la première qui s'applique gagne) :

1. **Sécurité SOC** — SOC ≤ `soc_min` → force l'arrêt de toute décharge. SOC ≥ `soc_max` →
   force l'arrêt de toute charge. Prioritaire sur tout le reste, non désactivable.
2. **Charge nocturne (heures creuses)** — si l'heure courante est dans la fenêtre configurée
   (`off_peak_start`/`off_peak_end`) ET SOC < `night_charge_soc_threshold` → charge à
   `night_charge_power` (une puissance douce, configurable, pas forcément la puissance max).
   *v1 : fenêtre horaire fixe, pas de dépendance à une prévision solaire ni à un flux de prix
   dynamique — amélioration possible plus tard via le format de points horaires générique
   décrit ci-dessous.*
3. **Absorption solaire** — si le capteur réseau indique de l'export (puissance négative) →
   charge à hauteur de l'excédent, plafonnée à `max_charge_w`.
4. **Décharge zéro-injection** — sinon, si le capteur réseau indique de l'import (puissance
   positive) → décharge à hauteur de la conso, plafonnée à `max_discharge_w`.
5. Sinon → idle (aucune commande, ou remise à 0 si un ordre précédent était actif).

Chaque stratégie (2, 3, 4) est désactivable indépendamment via un `switch` ; la sécurité SOC
(1) ne l'est pas.

**Anti-rebond** : la commande n'est réécrite que si elle diffère de plus de `deadband_w`
(configurable, défaut 20 W) de la dernière commande envoyée avec succès — évite de spammer
l'appareil sur un capteur réseau bruité.

## Format de prix (réservé pour une évolution future)

Pour une charge nocturne réellement pilotée par un tarif dynamique (au lieu d'une fenêtre
horaire fixe), le format d'entrée attendu sera une entité `sensor` dont un attribut expose une
liste de points `{start_time, end_time, price}` — le même format générique que celui construit
et validé aujourd'hui pour alimenter `battery_smartflow_ai` (`price_export_entity`). Non
implémenté en v1.

## Architecture

Pas de `DataUpdateCoordinator` classique (pas de polling). Un listener s'abonne aux
changements d'état du capteur réseau (`async_track_state_change_event`) ; chaque changement
déclenche un cycle : lecture des entrées → fonction de décision pure → anti-rebond → écriture
des entités device.

```
ConfigEntry (1 par appareil Zendure)
 ├─ data: entity_id du mode AC, des deux limites, du SOC, du capteur réseau
 │        (l'absorption solaire se détecte via l'export réseau — pas besoin d'un capteur PV
 │        séparé en v1)
 └─ options: soc_min, soc_max, night_charge_soc_threshold, night_charge_power,
             off_peak_start, off_peak_end, max_charge_w, max_discharge_w, deadband_w

Listener (event, capteur réseau) ──▶ decide(inputs, config) ──▶ Writer (debounce)
                                      [fonction pure,                │
                                       testable sans HA]             ▼
                                                          select.<device>_ac_mode
                                                          number.<device>_input_limit
                                                          number.<device>_output_limit
```

La fonction `decide()` est le seul endroit contenant la logique métier ; elle prend un dict
d'entrées (soc, grid_power, now, config) et retourne soit `None` (rien à faire) soit
`{"mode": "input"|"output", "power_w": int, "reason": str}`. Elle ne touche à aucune entité
HA — c'est le Writer qui s'en charge, après application de l'anti-rebond.

## Entités exposées

- `sensor.<entry>_active_mode` — mode actuellement décidé (`idle`/`charging`/`discharging`).
- `sensor.<entry>_decision_reason` — raison lisible de la dernière décision (ex.
  `night_charge`, `solar_surplus`, `zero_export`, `soc_min_protect`, `idle`).
- `number.<entry>_soc_min`, `soc_max`, `night_charge_soc_threshold`, `night_charge_power`,
  `max_charge_w`, `max_discharge_w`, `deadband_w` — tous éditables en direct depuis l'UI.
- `switch.<entry>_enable_night_charge`, `enable_solar_charge`, `enable_zero_export` — activer/
  désactiver indépendamment chaque stratégie non critique.
- `switch.<entry>_master_enable` — coupe tout pilotage (utile pour rendre la main à l'appli
  Zendure ou à un contrôle manuel sans désinstaller l'intégration).

## Gestion d'erreurs

Si une entité référencée en config est `unknown`/`unavailable`/absente au moment du cycle : on
n'écrit rien ce cycle-là (jamais de valeur par défaut dangereuse comme "0 = sûr" appliquée à
l'aveugle), et `sensor.<entry>_decision_reason` prend la valeur `entity_unavailable:<entity_id>`.
Le `master_enable` à `off` coupe tout cycle sans désinstaller l'intégration.

## Tests

`decide()` étant une fonction pure (dict → dict | None), elle est testable avec `pytest` sans
dépendance à Home Assistant. Cas couverts : chaque priorité isolée, priorité SOC qui l'emporte
sur les autres, valeurs de SOC exactement aux seuils, capteurs indisponibles, anti-rebond
(commande inchangée si écart < deadband).

## Hors périmètre v1

- Prévision solaire du lendemain (Forecast.Solar) pour moduler la charge nocturne.
- Prix dynamique / format générique de points horaires (réservé, voir section dédiée).
- Coordination de plusieurs appareils Zendure dans une même entrée.
- Base de profils par modèle d'appareil.
