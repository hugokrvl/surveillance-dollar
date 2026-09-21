"""Notifications push via ntfy.sh (même principe que surveillance-higon)."""
import os
import requests
import urllib3

from config import NTFY_SERVER, NTFY_TOPIC

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DRY_RUN = False   # activé par --dry : affiche au lieu d'envoyer


def send(title: str, body: str, priority: str = "default", tags: list[str] | None = None) -> bool:
    if DRY_RUN:
        print(f"\n┌── [DRY] {title}  (priorité={priority}, tags={tags})")
        for line in body.splitlines():
            print(f"│ {line}")
        print("└──")
        return True
    headers = {"Title": title.encode("utf-8"), "Priority": priority}
    if tags:
        headers["Tags"] = ",".join(tags)
    try:
        r = requests.post(f"{NTFY_SERVER}/{NTFY_TOPIC}", data=body.encode("utf-8"),
                          headers=headers, timeout=15, verify=bool(os.environ.get("CI")))
        r.raise_for_status()
        print(f"[NOTIF] {title}")
        return True
    except Exception as e:
        print(f"[NOTIF ERREUR] {e}")
        return False
