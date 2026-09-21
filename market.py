"""
Récupération des cours (Yahoo Finance via yfinance).
Pour chaque actif : dernier cours, variation vs clôture de la veille, variation sur 2 h,
et plus haut / plus bas de la journée (heure de Paris).
"""
import os
import datetime as dt
import pandas as pd
import pytz
import yfinance as yf
from curl_cffi import requests as curl_requests

from config import ASSETS, DRIVERS

PARIS = pytz.timezone("Europe/Paris")

# SSL Windows local : certificat intermédiaire manquant → on désactive la vérif hors CI.
_SESSION = curl_requests.Session(impersonate="chrome", verify=bool(os.environ.get("CI")))


def _download(tickers: list[str], period: str, interval: str) -> pd.DataFrame:
    return yf.download(tickers, period=period, interval=interval, group_by="ticker",
                       progress=False, auto_adjust=False, threads=True, session=_SESSION)


def fetch_all() -> dict:
    """Retourne {clé: {label, fmt, price, prev_close, chg_pct, chg_2h_pct, day_high, day_low,
    day_open, last_time}} pour tous les ASSETS + DRIVERS. Clé absente si pas de données."""
    universe = {**ASSETS, **DRIVERS}
    tickers = [a["ticker"] for a in universe.values()]
    intraday = _download(tickers, "5d", "15m")
    daily    = _download(tickers, "10d", "1d")

    now_paris = dt.datetime.now(PARIS)
    today = now_paris.date()
    out = {}
    for key, a in universe.items():
        t = a["ticker"]
        try:
            bars  = intraday[t].dropna(subset=["Close"])
            dbars = daily[t].dropna(subset=["Close"])
        except KeyError:
            continue
        if bars.empty:
            continue
        bars = bars.tz_convert(PARIS)
        price = float(bars["Close"].iloc[-1])
        last_time = bars.index[-1]

        # Clôture de référence : dernière bougie journalière d'un jour ANTÉRIEUR
        # au jour de la dernière cotation (gère week-end / jours fériés).
        last_day = last_time.date()
        prev = dbars[dbars.index.date < last_day]
        prev_close = float(prev["Close"].iloc[-1]) if not prev.empty else None

        # Cours il y a ~2 h
        ref_2h = bars[bars.index <= last_time - pd.Timedelta(hours=2)]
        price_2h = float(ref_2h["Close"].iloc[-1]) if not ref_2h.empty else None

        # Journée en cours (heure de Paris)
        day = bars[bars.index.date == today]
        out[key] = {
            "label":      a["label"],
            "fmt":        a["fmt"],
            "price":      price,
            "prev_close": prev_close,
            "chg_pct":    _pct(price, prev_close),
            "chg_2h_pct": _pct(price, price_2h),
            "day_open":   float(day["Open"].iloc[0]) if not day.empty else None,
            "day_high":   float(day["High"].max()) if not day.empty else None,
            "day_low":    float(day["Low"].min()) if not day.empty else None,
            "last_time":  last_time.strftime("%d/%m %H:%M"),
            "stale":      last_time.date() != today,
        }
    return out


def _pct(a, b):
    if a is None or b in (None, 0):
        return None
    return (a / b - 1) * 100
