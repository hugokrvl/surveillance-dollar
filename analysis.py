"""
Logique de la vidéo :
  • Dollar VENDU  = DXY ↓, EUR/USD ↑, Or ↑ (et BTC ↑) en même temps.
  • Dollar ACHETÉ = l'inverse, souvent déclenché par pétrole ~100 $ et taux US qui se cabrent.
  • BTC ≥ 82k + dollar vendu  → chercher un LONG, objectif 87–88k.
  • BTC < 76k + dollar acheté → chercher un SHORT (« pas avant »).
  • Entre les deux → NEUTRE, on attend le signal.
"""
from config import (ASSETS, CONFIRM_MIN, OIL_ALERT, OIL_WARN, RATES_SPIKE_BP,
                    BTC_LONG_TRIGGER, BTC_TARGET_LOW, BTC_TARGET_HIGH,
                    BTC_SUPPORT, BTC_SHORT_TRIGGER, BTC_HYSTERESIS)

# Libellés des zones BTC
SIGNALS = {
    "LONG":           "🟢 SIGNAL LONG",
    "OBJECTIF":       "🎯 OBJECTIF 87–88k ATTEINT",
    "HAUT_NON_CONF":  "🟡 Au-dessus de 82k SANS confirmation dollar",
    "SHORT":          "🔴 SIGNAL SHORT",
    "BAS_NON_CONF":   "🟡 Sous 76k SANS confirmation dollar",
    "SUPPORT":        "🟠 Support 76,5k attaqué",
    "NEUTRE":         "⚪ NEUTRE — range, on attend",
}


def usd_direction(m: dict, key: str) -> int:
    """+1 si le mouvement de l'actif indique un dollar FORT, -1 dollar FAIBLE, 0 pas de mouvement net."""
    a = m.get(key)
    if not a or a["chg_pct"] is None or a.get("stale"):
        return 0
    chg = a["chg_pct"]
    if abs(chg) < ASSETS[key]["threshold"]:
        return 0
    return ASSETS[key]["usd_sign"] * (1 if chg > 0 else -1)


def dollar_regime(m: dict) -> dict:
    dirs = {k: usd_direction(m, k) for k in ASSETS}
    score = sum(dirs.values())                     # -4 (dollar très vendu) … +4 (très acheté)
    confirm = [dirs[k] for k in ("DXY", "EURUSD", "GOLD")]
    # …et le BTC ne doit pas aller franchement à contre-sens (vidéo : « tout pique du nez en même temps »)
    strong = confirm.count(+1) >= CONFIRM_MIN and -1 not in confirm and dirs["BTC"] != -1
    weak   = confirm.count(-1) >= CONFIRM_MIN and +1 not in confirm and dirs["BTC"] != +1
    if weak:
        label = "💵⬇️ DOLLAR VENDU"
    elif strong:
        label = "💵⬆️ DOLLAR ACHETÉ"
    elif score <= -2:
        label = "💵↘️ dollar plutôt faible (non confirmé)"
    elif score >= 2:
        label = "💵↗️ dollar plutôt fort (non confirmé)"
    else:
        label = "💵➡️ dollar neutre / signaux mélangés"
    return {"dirs": dirs, "score": score, "weak": weak, "strong": strong, "label": label}


def drivers(m: dict) -> dict:
    """Pétrole et taux : les déclencheurs d'un rachat de dollar."""
    oil_max, oil_name = None, None
    for k in ("BRENT", "WTI"):
        if m.get(k):
            if oil_max is None or m[k]["price"] > oil_max:
                oil_max, oil_name = m[k]["price"], m[k]["label"]
    rates_bp = None
    r = m.get("US10Y")
    if r and r["prev_close"] is not None:
        rates_bp = (r["price"] - r["prev_close"]) * 100
    return {
        "oil_max": oil_max, "oil_name": oil_name,
        "oil_alert": oil_max is not None and oil_max >= OIL_ALERT,
        "oil_warn":  oil_max is not None and oil_max >= OIL_WARN,
        "rates_bp": rates_bp,
        "rates_spike": rates_bp is not None and rates_bp >= RATES_SPIKE_BP,
    }


def btc_signal(m: dict, reg: dict, prev: str | None, weekend: bool) -> str:
    """Zone / signal BTC. `prev` = signal précédent (hystérésis pour éviter le spam)."""
    btc = m.get("BTC")
    if not btc:
        return "NEUTRE"
    p = btc["price"]
    h = BTC_HYSTERESIS
    # Tolérance : si on était déjà au-dessus / en dessous, on garde tant qu'on ne repasse pas franchement
    above_long  = p >= BTC_LONG_TRIGGER  * ((1 - h) if prev in ("LONG", "HAUT_NON_CONF", "OBJECTIF") else 1)
    above_tgt   = p >= BTC_TARGET_LOW    * ((1 - h) if prev == "OBJECTIF" else 1)
    below_short = p <  BTC_SHORT_TRIGGER * ((1 + h) if prev in ("SHORT", "BAS_NON_CONF") else 1)
    below_supp  = p <  BTC_SUPPORT       * ((1 + h) if prev == "SUPPORT" else 1)

    if above_tgt:
        return "OBJECTIF"
    if above_long:
        return "LONG" if (reg["weak"] and not weekend) else "HAUT_NON_CONF"
    if below_short:
        return "SHORT" if (reg["strong"] and not weekend) else "BAS_NON_CONF"
    if below_supp:
        return "SUPPORT"
    return "NEUTRE"


def plan_text(sig: str, weekend: bool) -> str:
    k = lambda v: f"{v/1000:g}k"
    if sig == "LONG":
        return f"Dollar vendu + BTC > {k(BTC_LONG_TRIGGER)} : chercher un long, objectif {k(BTC_TARGET_LOW)}–{k(BTC_TARGET_HIGH)}."
    if sig == "OBJECTIF":
        return f"Zone objectif {k(BTC_TARGET_LOW)}–{k(BTC_TARGET_HIGH)} : prise de profit si long. Mettre à jour les niveaux."
    if sig == "HAUT_NON_CONF":
        why = "marchés $ fermés le week-end" if weekend else "DXY/EUR-USD/Or ne confirment pas"
        return f"BTC > {k(BTC_LONG_TRIGGER)} mais {why} : prudence, attendre la confirmation."
    if sig == "SHORT":
        return f"Dollar acheté + BTC < {k(BTC_SHORT_TRIGGER)} : chercher un short (pas avant)."
    if sig == "BAS_NON_CONF":
        why = "marchés $ fermés le week-end" if weekend else "le dollar ne se renforce pas"
        return f"BTC < {k(BTC_SHORT_TRIGGER)} mais {why} : pas de short confirmé."
    if sig == "SUPPORT":
        return f"Chasse sous {k(BTC_SUPPORT)} : surveiller le dollar, short seulement sous {k(BTC_SHORT_TRIGGER)} si $ fort."
    return (f"Ni long ni short. Long si > {k(BTC_LONG_TRIGGER)} avec $ vendu ; "
            f"short si < {k(BTC_SHORT_TRIGGER)} avec $ acheté.")


def distance_text(m: dict) -> str:
    btc = m.get("BTC")
    if not btc:
        return ""
    p = btc["price"]
    parts = []
    for lvl, name in ((BTC_TARGET_LOW, "objectif"), (BTC_LONG_TRIGGER, "long"),
                      (BTC_SUPPORT, "support"), (BTC_SHORT_TRIGGER, "short")):
        d = (p / lvl - 1) * 100
        parts.append(f"{name} {lvl/1000:g}k {d:+.1f}%")
    return " · ".join(parts)
