"""Saat fuer die Forgen im Job tests-forgen: echte Repos von uns.

Drei oeffentliche HAIGS-taugliche Repos aus dem eigenen GitLab werden
in Gitea und Forgejo migriert (Code samt Tags), bekommen das Topic
``hacs`` und -- wo es Tags gibt -- ein Release auf dem neuesten. Dazu
ein Lockvogel: Topic ``hacs``, aber kein hacs.json. Was HAIGS davon
finden und was es ablehnen muss, prueft tests_forgen/.

Nur Standardbibliothek: der Job soll vor dem pip-Lauf saeen koennen.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import urllib.error
import urllib.request

#: name -> Basisadresse, wie ci/forgen.sh sie gewaehlt hat (HAIGS_FORGEN).
FORGEN = dict(
    paar.split("=", 1) for paar in os.environ.get("HAIGS_FORGEN", "").split(",") if paar
)
QUELLE = os.environ.get("CI_SERVER_URL", "").rstrip("/") + "/chance-konstruktion/"
REPOS = ["ha-powerline", "ha-gaming-assistant", "ha-spatial-matter"]
LOCKVOGEL = "kein-hacs-json"
ANMELDUNG = "Basic " + base64.b64encode(b"haigs:haigs-ci-geheim").decode()


def rufen(basis: str, pfad: str, methode: str = "GET", daten=None):
    anfrage = urllib.request.Request(
        basis + "/api/v1" + pfad,
        method=methode,
        data=json.dumps(daten).encode() if daten is not None else None,
        headers={"Authorization": ANMELDUNG, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(anfrage, timeout=300) as antwort:
        roh = antwort.read()
        return json.loads(roh) if roh else None


def saeen(name: str, basis: str) -> None:
    for repo in REPOS:
        rufen(
            basis,
            "/repos/migrate",
            "POST",
            {
                "clone_addr": QUELLE + repo + ".git",
                "repo_name": repo,
                "repo_owner": "haigs",
                "service": "git",
                "private": False,
            },
        )
        rufen(basis, f"/repos/haigs/{repo}/topics", "PUT", {"topics": ["hacs"]})
        tags = rufen(basis, f"/repos/haigs/{repo}/tags?limit=1") or []
        if tags:
            tag = tags[0]["name"]
            rufen(
                basis,
                f"/repos/haigs/{repo}/releases",
                "POST",
                {"tag_name": tag, "name": tag},
            )
        print(
            f"{name}: {repo} gesaet",
            "mit Release " + tags[0]["name"] if tags else "ohne Tag",
        )
    rufen(basis, "/user/repos", "POST", {"name": LOCKVOGEL, "auto_init": True})
    rufen(basis, f"/repos/haigs/{LOCKVOGEL}/topics", "PUT", {"topics": ["hacs"]})
    print(f"{name}: Lockvogel {LOCKVOGEL} gesaet")


if __name__ == "__main__":
    if not FORGEN:
        sys.exit("HAIGS_FORGEN fehlt -- erst ci/forgen.sh, dann . ./.forgen-env")
    if not os.environ.get("CI_SERVER_URL"):
        sys.exit("CI_SERVER_URL fehlt -- die Saat kommt aus dem eigenen GitLab")
    for name, basis in FORGEN.items():
        try:
            saeen(name, basis)
        except urllib.error.HTTPError as fehler:
            sys.exit(f"{name}: {fehler.code} {fehler.read()[:300]!r}")
