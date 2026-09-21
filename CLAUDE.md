# Surveillance Dollar / BTC — guide du projet

Bot de notifications (ntfy) qui applique une lecture macro « le dollar mène la danse »
au Bitcoin. Même stack que `../surveillance` (Higgons) : GitHub Actions + yfinance + ntfy.

## Le principe
- **Dollar vendu** = DXY ↓, EUR/USD ↑, Or ↑ (et BTC ne va pas à contre-sens).
- **Dollar acheté** = l'inverse. Déclencheurs typiques : pétrole ≥ 100 $, taux US 10 ans qui se cabrent.
- **BTC ≥ 82k + dollar vendu** → signal LONG, objectif 87–88k.
- **BTC < 76k + dollar acheté** → signal SHORT (« pas avant »). 76,5k = zone support.
- Sinon NEUTRE : on attend. Niveaux et seuils dans `config.py` (à mettre à jour à la main).

Confirmation = au moins `CONFIRM_MIN` (2) des 3 actifs DXY / EUR-USD / Or bougent (au-delà de
leur `threshold` vs clôture de la veille) dans le même sens, aucun à contre-sens, BTC pas à contre-sens.

## Échelle d'achat / vente de dollars
Variation du DXY vs veille (repli : EUR/USD inversé), seuils `DOLLAR_SCALE` = 0,15 / 0,40 / 0,80 % :
`-3 débandade · -2 fortes ventes · -1 ventes modérées · 0 calme · +1 achats modérés · +2 forts achats · +3 ruée`.
Jauge affichée : `VENTES ▱▱▱◆▰▰▱ ACHATS`. Alerte live quand on atteint ±2 / ±3 pour la 1re fois du jour
(`alerts.pressure` = extrêmes du jour).
**Accélération** : DXY ≥ ±0,25 % sur 2 h → alerte (urgente ≥ 0,5 %), cooldown 2 h par sens (`alerts.accel`).
Plusieurs alertes dans un même check → regroupées en UNE notif (`live_check` → `_live_check`).

## Notifications (heure de Paris)
| Quand | Quoi |
|---|---|
| Toutes les 15 min, 8h–21h | Alerte immédiate **seulement si changement** : zone/signal BTC, dollar confirmé (1×/jour/sens), pétrole ≥ 100 $ (reset < 95 $), taux ≥ +8 pb (1×/jour) |
| 8h, 10h, …, 20h | Point de marché complet (1 par créneau, rattrapé si le cron GitHub est en retard) |
| 21h | Récap de la journée : variations, plus bas/haut, déroulé des points, alertes, plan pour demain |
| Week-end | BTC seul (forex/or/pétrole fermés), pas de LONG/SHORT « confirmé » |

## Fichiers
| Fichier | Rôle |
|---|---|
| `config.py` | Niveaux BTC, tickers, seuils, topic ntfy, horaires |
| `market.py` | `fetch_all()` : cours, var. vs veille, var. 2 h, plus haut/bas du jour |
| `analysis.py` | `dollar_regime`, `drivers`, `btc_signal` (avec hystérésis), textes de plan |
| `dollar_watch.py` | Orchestration : check live / point 2 h / récap 21 h, `state.json` |
| `notifier.py` | Envoi ntfy (`DRY_RUN` pour tester sans envoyer) |
| `state.json` | État persistant commité par la CI (créneaux envoyés, derniers signaux, journal du jour) |

## Lancer
- Test à blanc : `python -X utf8 dollar_watch.py --dry --check --report --recap`
- Notif de test : `python -X utf8 dollar_watch.py --test` (ou `test_notif.bat`)
- CI : cron `*/15 6-20 * * *` UTC ; manuel via Actions → « Run workflow ».

## Pièges
- SSL Windows local : session `curl_cffi` avec `verify=False` hors CI (variable `CI` absente).
- Le cron GitHub peut avoir 5–20 min de retard, voire sauter un run : les créneaux sont rattrapés au run suivant.
- Données Yahoo légèrement différées (DXY/futures ~10–15 min).
