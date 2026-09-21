#!/usr/bin/env python3
"""
Surveillance Dollar / BTC — lancé toutes les 15 min par GitHub Actions.

Mode auto (sans argument) — selon l'heure de Paris :
  • 08:00–21:00 : check « live » → notif immédiate si un signal CHANGE (long/short/objectif,
                  pétrole ≥ 100 $, taux qui se cabrent, confirmation dollar).
  • 8h,10h,…,20h : point de marché complet (1 notif par créneau, même si le cron est en retard).
  • 21h          : récap complet de la journée.
  • Week-end     : BTC seul (forex/or/pétrole fermés).
L'état (créneaux envoyés, derniers signaux, journal du jour) est dans state.json (commité par la CI).

Options : --report / --recap / --check (forcer), --test (notif de test), --dry (afficher sans envoyer).
"""
import sys
import json
import datetime as dt
from pathlib import Path

import pytz

import notifier
from notifier import send
from config import (ASSETS, DRIVERS, REPORT_HOURS, RECAP_HOUR, OIL_ALERT, OIL_WARN,
                    RATES_SPIKE_BP, NTFY_TOPIC, BTC_LONG_TRIGGER, BTC_SHORT_TRIGGER,
                    BTC_TARGET_LOW, BTC_TARGET_HIGH, BTC_SUPPORT)
from market import fetch_all
from analysis import (SIGNALS, dollar_regime, drivers, btc_signal, plan_text, distance_text)

PARIS = pytz.timezone("Europe/Paris")
STATE_FILE = Path(__file__).parent / "state.json"
ARROW = {1: "↑", -1: "↓", 0: "→"}


# ── État persistant ──────────────────────────────────────────────────────────
def load_state(today: str) -> dict:
    st = {}
    if STATE_FILE.exists():
        try:
            st = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            st = {}
    st.setdefault("alerts", {})           # persiste d'un jour à l'autre (anti-spam)
    if st.get("date") != today:           # nouveau jour → on remet le journal à zéro
        st.update({"date": today, "reports_sent": [], "recap_sent": False,
                   "snapshots": [], "events": []})
    return st


def save_state(st: dict):
    STATE_FILE.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Mise en forme ────────────────────────────────────────────────────────────
def fmt_price(a: dict) -> str:
    return a["fmt"].format(a["price"]).replace(",", " ")


def fmt_chg(v, suffix="%"):
    return "n/d" if v is None else f"{v:+.2f}{suffix}"


def asset_line(m: dict, key: str, direction: int | None = None) -> str | None:
    a = m.get(key)
    if not a:
        return None
    if key == "US10Y":
        bp = None if a["prev_close"] is None else (a["price"] - a["prev_close"]) * 100
        chg = "n/d" if bp is None else f"{bp:+.0f} pb"
    else:
        chg = fmt_chg(a["chg_pct"])
    line = f"{a['label']}: {fmt_price(a)} ({chg})"
    if direction is not None:
        line += f" {ARROW[direction]}$" if direction else ""
    if a.get("stale"):
        line += " [fermé]"
    return line


def market_block(m: dict, reg: dict | None, weekend: bool) -> list[str]:
    lines = []
    keys = ["BTC"] if weekend else ["DXY", "EURUSD", "GOLD", "BTC"]
    for k in keys:
        l = asset_line(m, k, None if weekend else reg["dirs"][k])
        if l:
            lines.append(l)
    if not weekend:
        for k in DRIVERS:
            l = asset_line(m, k)
            if l:
                lines.append(l)
    return lines


def analyse(m: dict, st: dict, weekend: bool):
    reg = dollar_regime(m)
    drv = drivers(m)
    prev_sig = st["alerts"].get("signal")
    sig = btc_signal(m, reg, prev_sig, weekend)
    return reg, drv, sig


# ── 1) Check live : notif immédiate seulement si quelque chose CHANGE ─────────
def live_check(m: dict, st: dict, weekend: bool, now: dt.datetime):
    reg, drv, sig = analyse(m, st, weekend)
    al = st["alerts"]
    hhmm = now.strftime("%H:%M")
    btc = m.get("BTC")
    btc_txt = fmt_price(btc) + " $" if btc else "n/d"

    def event(text):
        st["events"].append({"h": hhmm, "text": text})

    # Signal BTC
    prev = al.get("signal")
    if prev is not None and sig != prev:
        prio = {"LONG": "urgent", "SHORT": "urgent", "OBJECTIF": "high"}.get(sig, "default")
        tags = {"LONG": ["green_circle", "chart_with_upwards_trend"],
                "SHORT": ["red_circle", "chart_with_downwards_trend"],
                "OBJECTIF": ["dart"]}.get(sig, ["warning"])
        body = [f"BTC {btc_txt}", reg["label"] if not weekend else "Week-end : pas de confirmation $",
                *market_block(m, reg, weekend), "", plan_text(sig, weekend)]
        send(f"{SIGNALS[sig]} — BTC {btc_txt}", "\n".join(body), prio, tags)
        event(f"{SIGNALS[sig]} (BTC {btc_txt}, avant : {SIGNALS[prev]})")
    al["signal"] = sig

    if weekend:
        return

    # Confirmation dollar (vendu / acheté) : 1 fois par jour et par sens
    for flag, key, txt, tag in ((reg["weak"], "weak", "Dollar VENDU confirmé", "chart_with_upwards_trend"),
                                (reg["strong"], "strong", "Dollar ACHETÉ confirmé", "chart_with_downwards_trend")):
        if flag and al.get(f"reg_{key}") != st["date"]:
            body = [*market_block(m, reg, weekend), "", plan_text(sig, weekend), distance_text(m)]
            send(f"💵 {txt} — BTC {btc_txt}", "\n".join(body), "high", [tag])
            event(f"{txt} (BTC {btc_txt})")
            al[f"reg_{key}"] = st["date"]

    # Pétrole ≥ 100 $ (notif au franchissement, reset sous 95 $)
    if drv["oil_alert"] and not al.get("oil"):
        send(f"🛢️ Pétrole ≥ {OIL_ALERT:.0f} $ ({drv['oil_name']} {drv['oil_max']:.1f})",
             "Le pétrole flambe → risque de rachat du dollar.\nSi DXY monte et BTC/Or/EUR-USD piquent : "
             f"short seulement sous {BTC_SHORT_TRIGGER/1000:g}k.", "high", ["oil_drum", "warning"])
        event(f"Pétrole ≥ {OIL_ALERT:.0f} $ ({drv['oil_name']} {drv['oil_max']:.1f})")
        al["oil"] = True
    elif drv["oil_max"] is not None and drv["oil_max"] < OIL_WARN:
        al["oil"] = False

    # Taux US 10 ans qui se cabrent (1 fois par jour)
    if drv["rates_spike"] and al.get("rates") != st["date"]:
        send(f"📈 Taux US 10 ans se cabrent ({drv['rates_bp']:+.0f} pb)",
             f"{asset_line(m, 'US10Y')}\nRisque de rachat du dollar → surveiller BTC sous {BTC_SUPPORT/1000:g}k.",
             "high", ["chart_with_upwards_trend", "warning"])
        event(f"Taux 10 ans {drv['rates_bp']:+.0f} pb")
        al["rates"] = st["date"]


# ── 2) Point toutes les 2 h ──────────────────────────────────────────────────
def report(m: dict, st: dict, weekend: bool, now: dt.datetime):
    reg, drv, sig = analyse(m, st, weekend)
    btc = m.get("BTC")
    btc_txt = fmt_price(btc) + " $" if btc else "n/d"
    lines = []
    if not weekend:
        lines.append(f"{reg['label']} (score {reg['score']:+d}/4)")
    else:
        lines.append("Week-end : BTC seul (marchés $ fermés)")
    lines += market_block(m, reg, weekend)
    if btc and btc["chg_2h_pct"] is not None:
        lines.append(f"BTC sur 2 h : {btc['chg_2h_pct']:+.2f}%")
    if not weekend:
        warn = []
        if drv["oil_warn"]:
            warn.append(f"pétrole {drv['oil_max']:.0f} $")
        if drv["rates_spike"]:
            warn.append(f"taux {drv['rates_bp']:+.0f} pb")
        if warn:
            lines.append("⚠️ Pression dollar : " + ", ".join(warn))
    lines += ["", SIGNALS[sig], plan_text(sig, weekend), distance_text(m)]

    regime_short = ("$ vendu" if reg["weak"] else "$ acheté" if reg["strong"] else f"$ {reg['score']:+d}/4")
    title = f"{now.strftime('%Hh')} · BTC {btc_txt} · " + ("week-end" if weekend else regime_short)
    send(title, "\n".join(lines), "default", ["bar_chart"])
    st["snapshots"].append({"h": now.strftime("%H:%M"), "btc": btc["price"] if btc else None,
                            "score": reg["score"], "regime": reg["label"], "signal": sig})
    st["alerts"]["signal"] = sig


# ── 3) Récap 21 h ────────────────────────────────────────────────────────────
def recap(m: dict, st: dict, weekend: bool, now: dt.datetime):
    reg, drv, sig = analyse(m, st, weekend)
    lines = ["📊 JOURNÉE (vs clôture veille · plus bas → plus haut)"]
    keys = ["BTC"] if weekend else [*ASSETS, *DRIVERS]
    for k in keys:
        a = m.get(k)
        if not a:
            continue
        rng = ""
        if a["day_low"] is not None:
            f = lambda v: a["fmt"].format(v).replace(",", " ")
            rng = f" · {f(a['day_low'])} → {f(a['day_high'])}"
        chg = fmt_chg(a["chg_pct"])
        if k == "US10Y" and a["prev_close"] is not None:
            chg = f"{(a['price'] - a['prev_close']) * 100:+.0f} pb"
        lines.append(f"{a['label']}: {fmt_price(a)} ({chg}){rng}")

    if not weekend:
        lines += ["", f"💵 Bilan dollar : {reg['label']} (score {reg['score']:+d}/4)"]
    if st["snapshots"]:
        lines += ["", "🕐 Au fil de la journée :"]
        for s in st["snapshots"]:
            btc = f"{s['btc']:,.0f}".replace(",", " ") if s["btc"] else "n/d"
            reg_s = "" if weekend else f" · $ {s['score']:+d}"
            lines.append(f"{s['h']} BTC {btc}{reg_s} · {SIGNALS[s['signal']].split(' ', 1)[1]}")
    lines += ["", "🔔 Alertes du jour :"]
    lines += [f"{e['h']} {e['text']}" for e in st["events"]] or ["Aucune — marché latéral."]

    k = lambda v: f"{v/1000:g}k"
    lines += ["", f"📌 Pour demain : {SIGNALS[sig]}", plan_text(sig, weekend),
              f"Niveaux : long > {k(BTC_LONG_TRIGGER)} (obj. {k(BTC_TARGET_LOW)}–{k(BTC_TARGET_HIGH)}) · "
              f"support {k(BTC_SUPPORT)} · short < {k(BTC_SHORT_TRIGGER)}"]
    if not weekend:
        lines.append(f"Déclencheurs $ fort : pétrole ≥ {OIL_ALERT:.0f} $, taux +{RATES_SPIKE_BP} pb.")

    btc = m.get("BTC")
    title = f"🌙 Récap du {now.strftime('%d/%m')} · BTC {fmt_price(btc) if btc else 'n/d'} $ ({fmt_chg(btc['chg_pct'] if btc else None)})"
    send(title, "\n".join(lines), "default", ["crescent_moon", "bar_chart"])
    st["alerts"]["signal"] = sig


# ── Orchestration ────────────────────────────────────────────────────────────
def main(argv: list[str]):
    if "--dry" in argv:
        notifier.DRY_RUN = True
    if "--test" in argv:
        ok = send("✅ Surveillance Dollar/BTC — connexion OK",
                  f"Topic : {NTFY_TOPIC}\nPoints à {', '.join(f'{h}h' for h in REPORT_HOURS)} + récap {RECAP_HOUR}h.",
                  tags=["white_check_mark"])
        sys.exit(0 if ok else 1)

    now = dt.datetime.now(PARIS)
    today = now.strftime("%Y-%m-%d")
    weekend = now.weekday() >= 5
    st = load_state(today)

    force = {a for a in ("--report", "--recap", "--check") if a in argv}
    in_window = 8 <= now.hour < RECAP_HOUR + 2
    if not force and not in_window:
        print(f"[{now:%H:%M}] Hors plage 08h–{RECAP_HOUR}h, rien à faire.")
        return

    print(f"[{now:%d/%m %H:%M}] Récupération des cours…")
    m = fetch_all()
    if "BTC" not in m:
        print("[ERREUR] Pas de données BTC, abandon.")
        return
    for k, a in m.items():
        print(f"  {k:7} {a['price']:>12.4f}  jour {fmt_chg(a['chg_pct']):>8}  2h {fmt_chg(a['chg_2h_pct']):>8}  ({a['last_time']}{' fermé' if a['stale'] else ''})")

    if force:
        if "--check" in force:
            live_check(m, st, weekend, now)
        if "--report" in force:
            report(m, st, weekend, now)
        if "--recap" in force:
            recap(m, st, weekend, now)
    else:
        if now.hour < RECAP_HOUR:
            live_check(m, st, weekend, now)
            slot = max(h for h in REPORT_HOURS if h <= now.hour)
            if slot not in st["reports_sent"]:
                report(m, st, weekend, now)
                st["reports_sent"].append(slot)
        elif not st["recap_sent"]:
            recap(m, st, weekend, now)
            st["recap_sent"] = True

    if not notifier.DRY_RUN:
        save_state(st)


if __name__ == "__main__":
    main(sys.argv[1:])
