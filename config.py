"""
Configuration — Surveillance Dollar / BTC.
Tout ce qu'on modifie à la main est ici (surtout les NIVEAUX BTC).
"""

# ── Notifications (app ntfy sur le téléphone → s'abonner à ce topic) ────────
NTFY_SERVER = "https://ntfy.sh"
NTFY_TOPIC  = "dollar-macro-hugo-k7q2"   # topic public : garder un suffixe peu devinable

# ── Niveaux BTC (en dollars) — À METTRE À JOUR selon l'analyse du moment ───
BTC_LONG_TRIGGER  = 82_000   # au-dessus + dollar vendu  → chercher un long
BTC_TARGET_LOW    = 87_000   # zone objectif du long (87–88k)
BTC_TARGET_HIGH   = 88_000
BTC_SUPPORT       = 76_500   # zone support : on "chasse" en dessous
BTC_SHORT_TRIGGER = 76_000   # en dessous + dollar acheté → chercher un short ("pas avant")
BTC_HYSTERESIS    = 0.003    # 0,3 % de marge pour ne pas re-notifier à chaque aller-retour sur un niveau

# ── Actifs suivis (tickers Yahoo Finance) ───────────────────────────────────
# usd_sign : +1 si l'actif MONTE quand le dollar se renforce, -1 s'il BAISSE.
# threshold : variation minimale (%) vs clôture précédente pour compter comme un "mouvement".
ASSETS = {
    "DXY":    {"ticker": "DX-Y.NYB", "label": "Dollar (DXY)", "usd_sign": +1, "threshold": 0.15, "fmt": "{:.2f}"},
    "EURUSD": {"ticker": "EURUSD=X", "label": "EUR/USD",      "usd_sign": -1, "threshold": 0.15, "fmt": "{:.4f}"},
    "GOLD":   {"ticker": "GC=F",     "label": "Or",           "usd_sign": -1, "threshold": 0.30, "fmt": "{:,.0f}"},
    "BTC":    {"ticker": "BTC-USD",  "label": "Bitcoin",      "usd_sign": -1, "threshold": 0.75, "fmt": "{:,.0f}"},
}
# Les « déclencheurs » d'un dollar fort (vidéo : pétrole à 100 $, taux qui se cabrent)
DRIVERS = {
    "WTI":   {"ticker": "CL=F", "label": "Pétrole WTI",   "fmt": "{:.1f}"},
    "BRENT": {"ticker": "BZ=F", "label": "Pétrole Brent", "fmt": "{:.1f}"},
    "US10Y": {"ticker": "^TNX", "label": "Taux US 10 ans", "fmt": "{:.2f}%"},
}
OIL_ALERT        = 100.0   # $/baril : le pétrole « flambe »
OIL_WARN         = 95.0
RATES_SPIKE_BP   = 8       # hausse du 10 ans vs veille (points de base) = « les taux se cabrent »

# ── Échelle d'achat / vente de dollars ──────────────────────────────────────
# Basée sur la variation du DXY vs clôture de la veille (repli sur EUR/USD inversé si DXY absent).
# |var| ≥ seuil → niveau 1 (modéré), 2 (fort), 3 (ruée / débandade). Signe + = achats, − = ventes.
DOLLAR_SCALE = [0.15, 0.40, 0.80]   # en %

# Accélération brutale : variation du DXY sur les 2 dernières heures
ACCEL_2H        = 0.25   # % → alerte « le dollar accélère »
ACCEL_2H_URGENT = 0.50   # % → alerte urgente
ACCEL_COOLDOWN_H = 2     # pas de nouvelle alerte dans le même sens avant 2 h

# Confirmation dollar : parmi DXY / EUR/USD / Or (hors BTC, qu'on veut trader),
# combien doivent aller dans le même sens (et aucun dans le sens contraire).
CONFIRM_MIN = 2

# ── Horaires (heure de Paris) ───────────────────────────────────────────────
REPORT_HOURS = [8, 10, 12, 14, 16, 18, 20]   # point toutes les 2 h
RECAP_HOUR   = 21                            # récap complet de la journée
