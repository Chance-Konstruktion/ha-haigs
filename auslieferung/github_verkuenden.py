"""Traegt denselben Release auf GitHub ein -- mit dem ZIP daran.

GitHub ist die Ladentheke: HACS kann nur von dort installieren, und es
installiert aus **Releases**, nicht aus dem Zweig. Die Push-Spiegelung
traegt Commits und Tags hinueber, aber ein GitLab-Release ist ein
GitLab-Objekt -- drueben entsteht daraus nichts von allein.

Die Vorlage in ``claude/ci-vorlagen`` legt den Eintrag an, haengt aber
nichts daran. Fuer HAIGS reicht das nicht: beide READMEs schicken die
Leute zu ``haigs-vX.Y.Z.zip``. Ohne Anhang faende dort nur das
automatische Quell-Archiv statt der geprueften, deterministisch gebauten
Lieferform. Darum zwei Aufrufe:

* ``POST`` des Release-Eintrags,
* ``POST`` des ZIP an die Upload-Adresse, die die Antwort selbst nennt.

Reine Standardbibliothek, auf dem Bild, das ohnehin laeuft.

Fehlt ``GITHUB_TOKEN``, bricht das hier **nicht** ab: es sagt im Log, dass
es nichts getan hat, und laesst die Pipeline gruen. Das GitLab-Release
steht dann trotzdem. Gibt es den Release drueben schon, ist das ebenfalls
kein Fehler -- derselbe Tag zweimal veroeffentlicht ist kein Schaden; der
Anhang wird dann nachgereicht, falls er fehlt.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

BESITZER = os.environ.get("GITHUB_OWNER", "Chance-Konstruktion").strip()


class GithubFehler(Exception):
    """Was GitHub abgelehnt hat -- Code und Klartext, ohne urllib.

    Der Transport uebersetzt hier, damit der Pruefstand ohne ein
    Netz-Modul auskommt: ``tests-ohne-netz`` in der Pipeline verbietet
    ``import urllib`` in tests/ -- zu Recht, ein Test, der ein Netz-Modul
    braucht, ist auf dem besten Weg, eines zu benutzen.
    """

    def __init__(self, code: int, koerper: str = ""):
        super().__init__(f"GitHub antwortet {code}: {koerper[:400]}")
        self.code = code
        self.koerper = koerper


def _ruf(
    adresse: str,
    token: str,
    daten: bytes | None = None,
    art: str = "application/json",
    methode: str = "GET",
) -> dict:
    anfrage = urllib.request.Request(
        adresse,
        data=daten,
        method=methode,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": art,
            "User-Agent": "gitlab-ci",
        },
    )
    try:
        with urllib.request.urlopen(anfrage, timeout=120) as antwort:
            koerper = antwort.read()
    except urllib.error.HTTPError as fehler:
        raise GithubFehler(
            fehler.code, fehler.read().decode("utf-8", "replace")
        ) from fehler
    return json.loads(koerper) if koerper else {}


def _vorhandener_release(repo: str, tag: str, token: str, ruf=_ruf) -> dict | None:
    try:
        return ruf(f"https://api.github.com/repos/{repo}/releases/tags/{tag}", token)
    except GithubFehler as fehler:
        if fehler.code == 404:
            return None
        raise


def main(ruf=_ruf) -> int:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    tag = os.environ["CI_COMMIT_TAG"]
    name = os.environ.get("GITHUB_REPO", "").strip() or os.environ["CI_PROJECT_NAME"]
    repo = f"{BESITZER}/{name}"

    if not token:
        print(f"GITHUB_TOKEN ist nicht gesetzt -- kein GitHub-Release fuer {tag}.")
        print("Das ist kein Fehler, aber HACS-Nutzer sehen diesen Stand nicht.")
        return 0

    archive = sorted(Path("dist").glob("*.zip"))
    if len(archive) != 1:
        print(
            f"FEHLER: genau ein ZIP unter dist/ erwartet, gefunden: {archive}",
            file=sys.stderr,
        )
        return 1
    archiv = archive[0]

    text = "\n".join(
        [
            f"Automatisch aus dem Tag `{tag}` erzeugt.",
            "",
            f"Zum Installieren `{archiv.name}` herunterladen und in das",
            "Home-Assistant-Konfigurationsverzeichnis entpacken --",
            "siehe [README.en.md](../../blob/main/README.en.md).",
            "",
            f"Entwickelt wird im GitLab: {os.environ.get('CI_PROJECT_URL', '')}",
            "Dieses Repository ist die Installationsquelle fuer HACS.",
        ]
    )

    eintrag = _vorhandener_release(repo, tag, token, ruf)
    if eintrag:
        print(f"Release {tag} gibt es auf GitHub bereits -- Eintrag bleibt, wie er ist.")
    else:
        nutzlast = json.dumps(
            {
                "tag_name": tag,
                "name": tag,
                "body": text,
                "draft": False,
                "prerelease": False,
            }
        ).encode()
        try:
            eintrag = ruf(
                f"https://api.github.com/repos/{repo}/releases",
                token,
                nutzlast,
                methode="POST",
            )
        except GithubFehler as fehler:
            print(str(fehler), file=sys.stderr)
            return 1
        print(f"GitHub-Release angelegt: {eintrag.get('html_url')}")

    if any(a.get("name") == archiv.name for a in eintrag.get("assets", [])):
        print(f"{archiv.name} haengt schon daran -- nichts nachzureichen.")
        return 0

    # Die Upload-Adresse steht in der Antwort und endet auf "{?name,label}".
    hochladen = eintrag["upload_url"].split("{", 1)[0] + f"?name={archiv.name}"
    try:
        angehaengt = ruf(
            hochladen, token, archiv.read_bytes(), art="application/zip", methode="POST"
        )
    except GithubFehler as fehler:
        print(f"Anhang schlug fehl -- {fehler}", file=sys.stderr)
        return 1
    print(f"Anhang liegt: {angehaengt.get('browser_download_url')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
