"""Traegt den Release ins GitLab ein -- ohne fremdes Image.

Stufe M10-Nachklapp (Befund c aus dem Review von !11): die Ver-
kuendung lief bisher auf dem release-cli-Image -- ein fremdes Bild,
das der Runner erst ziehen muss, mit einer eigenen Sprache (der
``release:``-Syntax) und dem Unsicherheitsrest, ob es die Instanz
ueberhaupt kennt. Das Rezept aus dem Review ist reine Standard-
bibliothek auf dem Bild, das ohnehin laeuft. Zwei Aufrufe reichen:

* ``PUT`` des ZIP in die Generic Package Registry des Projekts,
* ``POST`` des Release-Eintrags mit Link auf die Paketadresse.

Beide laufen mit dem ``JOB-TOKEN`` des laufenden Jobs -- er gilt nur
fuer diesen Lauf und dieses Projekt, ist kein Geheimnis, das man
verwahren muesste, und funktioniert auf jedem Runner, der Python
kann. Der Anhang-Link zeigt dadurch auf die Paketadresse statt auf
``/-/jobs/<id>/artifacts/...`` -- die Paketadresse gilt auch noch,
wenn der Job laengst vergangen ist.

Der Bau prueft schon, dass Tag und manifest.json dieselbe Version
nennen; die Verkuendung prueft es noch einmal, bevor sie etwas
eintraegt, was man nicht lautlos zuruecknehmen kann.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from auslieferung.release_bauen import (
    ANZEIGENAME,
    fingerabdruck,
    lies_version,
    normalisiere_version,
)

#: Der Ort, an dem der Bau seinen ZIP ablegt (Artefakt des Baus).
STANDARD_ZIP_VERZEICHNIS = Path("dist")

#: Variablen, ohne die die Verkuendung nicht laufen kann -- alle stellt
#: GitLab CI jedem Job von selbst bereit; wer sie von Hand aufruft,
#: bekommt sie beim Namen genannt.
ERFORDERLICH = ("CI_API_V4_URL", "CI_PROJECT_ID", "CI_JOB_TOKEN", "CI_COMMIT_TAG")

#: Statuscodes, mit denen GitLab ein Hochladen bzw. Anlegen quittiert.
ERFOLGREICH = (200, 201)


class VerkuendigungsFehler(Exception):
    """Die Verkuendung schlug fehl -- der Text ist fuer Menschen."""


def rufe(
    methode: str,
    url: str,
    token: str,
    inhalt: bytes | None = None,
    inhaltstyp: str | None = None,
) -> tuple[int, bytes]:
    """Ein einziger Aufruf ueber die Standardbibliothek.

    Wirft nicht bei HTTP-Fehlern, sondern gibt (Status, Koerper)
    zurueck -- der Aufrufer entscheidet, was ein Fehler ist und wie
    er heisst. Netzwerkfehler ganz ohne Statuscode (Instanz weg,
    DNS tot) fliegen als Ausnahme weiter: dafuer gibt es keine
    ehrliche Zahl.
    """
    anfrage = urllib.request.Request(url, data=inhalt, method=methode)
    anfrage.add_header("JOB-TOKEN", token)
    if inhaltstyp:
        anfrage.add_header("Content-Type", inhaltstyp)
    try:
        with urllib.request.urlopen(anfrage) as antwort:
            return antwort.status, antwort.read()
    except urllib.error.HTTPError as fehler:
        return fehler.code, fehler.read()


def lies_umgebung(env: dict[str, str]) -> dict[str, str]:
    """Sammelt die noetigen CI-Variablen und nennt fehlende beim Namen."""
    fehlen = [name for name in ERFORDERLICH if not (env.get(name) or "").strip()]
    if fehlen:
        raise VerkuendigungsFehler(
            "diese Variablen fehlen (GitLab CI stellt sie von selbst bereit, "
            "von Hand muss man sie setzen): " + ", ".join(fehlen)
        )
    return {name: (env.get(name) or "").strip() for name in ERFORDERLICH}


def verkuendigen(
    wurzel: Path,
    zip_pfad: Path,
    env: dict[str, str],
    transport=rufe,
) -> dict[str, str]:
    """Laedt den ZIP und traegt den Release ein; gibt das Protokoll zurueck.

    ``transport`` ist die einzige Naht zum Netz -- die Tests legen eine
    Attrappe hinein, es geht nie ein echtes Byte auf die Reise.
    """
    variablen = lies_umgebung(env)
    tag = variablen["CI_COMMIT_TAG"]
    version = normalisiere_version(tag)

    manifest_version = lies_version(wurzel)
    if manifest_version != version:
        raise VerkuendigungsFehler(
            f"Tag {tag} und manifest.json ({manifest_version}) nennen "
            "verschiedene Versionen -- ein Release, der im Namen etwas "
            "anderes verspricht als er installiert, wird nicht eingetragen"
        )

    if not zip_pfad.is_file():
        raise VerkuendigungsFehler(
            f"der ZIP fehlt unter {zip_pfad} -- ohne Anhang gibt es nichts "
            "zu verkuenden (der Bau legt ihn unter dist/ ab)"
        )

    zip_name = f"{ANZEIGENAME}-v{version}.zip"
    paket_url = (
        f"{variablen['CI_API_V4_URL']}/projects/{variablen['CI_PROJECT_ID']}"
        f"/packages/generic/{ANZEIGENAME}/{version}/{zip_name}"
    )
    sha = fingerabdruck(zip_pfad)

    status, koerper = transport(
        "PUT",
        paket_url,
        variablen["CI_JOB_TOKEN"],
        inhalt=zip_pfad.read_bytes(),
        inhaltstyp="application/zip",
    )
    if status not in ERFOLGREICH:
        raise VerkuendigungsFehler(
            f"die Paket-Registry nahm den ZIP nicht an (HTTP {status}): "
            f"{koerper.decode('utf-8', 'replace')[:400]}"
        )

    eintrag = {
        "tag_name": tag,
        "name": f"HAIGS {tag}",
        "description": (
            f"Deterministischer Bau aus dem getaggten Stand. SHA-256 des Anhangs: {sha}"
        ),
        "assets": {
            "links": [
                {
                    "name": f"{zip_name} -- Hand-Installation",
                    "url": paket_url,
                }
            ]
        },
    }
    release_url = (
        f"{variablen['CI_API_V4_URL']}/projects/{variablen['CI_PROJECT_ID']}/releases"
    )
    status, koerper = transport(
        "POST",
        release_url,
        variablen["CI_JOB_TOKEN"],
        inhalt=json.dumps(eintrag).encode("utf-8"),
        inhaltstyp="application/json",
    )
    if status not in ERFOLGREICH:
        text = koerper.decode("utf-8", "replace")[:400]
        if "already exists" in text.lower():
            raise VerkuendigungsFehler(
                f"der Release-Eintrag fuer {tag} existiert bereits -- "
                "nichts doppelt eingetragen; der ZIP liegt in der Registry "
                "unter der Adresse oben"
            )
        raise VerkuendigungsFehler(
            f"der Release-Eintrag scheiterte (HTTP {status}): {text}"
        )

    return {"tag": tag, "version": version, "paket": paket_url, "sha": sha}


def haupt(
    argv: list[str] | None = None,
    env: dict[str, str] | None = None,
    transport=rufe,
) -> int:
    """Kommandozeile: ``python -m auslieferung.verkuendigen [zip-datei]``."""
    argv = list(sys.argv[1:] if argv is None else argv)
    env = dict(os.environ) if env is None else dict(env)
    if len(argv) > 1:
        print("FEHLER: hoechstens ein ZIP-Pfad", file=sys.stderr)
        return 2

    wurzel = Path(__file__).resolve().parents[1]
    try:
        variablen = lies_umgebung(env)
        version = normalisiere_version(variablen["CI_COMMIT_TAG"])
        zip_pfad = (
            Path(argv[0])
            if argv
            else STANDARD_ZIP_VERZEICHNIS / f"{ANZEIGENAME}-v{version}.zip"
        )
        protokoll = verkuendigen(wurzel, zip_pfad, env, transport=transport)
    except VerkuendigungsFehler as fehler:
        print(f"FEHLER: {fehler}", file=sys.stderr)
        return 1

    print(f"Paket hochgeladen: {protokoll['paket']}")
    print(f"Release eingetragen: HAIGS {protokoll['tag']}")
    print(f"SHA-256 des Anhangs: {protokoll['sha']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(haupt())
