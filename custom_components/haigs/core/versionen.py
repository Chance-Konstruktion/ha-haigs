"""Versionsvergleich und Update-Erkennung.

Absichtlich ohne ``packaging``: die Erweiterung soll in Home Assistant
ohne zusaetzliche Abhaengigkeit laufen. Verglichen wird nach Zahlen,
alles Uebrige bleibt Text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .forge import Release

#: Der Zahlenkopf einer Version: 1, 1.2, 1.2.3 ...
_KOPF = re.compile(r"^\d+(?:\.\d+)*")


def normalisiere(version: str) -> str:
    """Nimmt fuehrende ``v`` und Leerzeichen weg."""
    v = (version or "").strip()
    if v[:1] in ("v", "V") and v[1:2].isdigit():
        v = v[1:]
    return v


def ist_vorabversion(version: str) -> bool:
    """Erkennt ``1.2.0-rc1``, ``2.0b3`` und Verwandte.

    Geprueft wird nur, was hinter dem Zahlenkopf steht -- ``1.0.0+build``
    ist damit keine Vorabversion, ``1.0.0-beta`` schon.
    """
    rest = _KOPF.sub("", normalisiere(version).lower()).lstrip("-._+")
    if not rest:
        return False
    if re.match(r"^(alpha|beta|rc|dev|pre)", rest):
        return True
    return bool(re.match(r"^[ab]\d*$", rest))


#: Wie viele Glieder einer Version in den Sortierschluessel ziehen.
#: Vier reichen fuer den Normalfall, aber echte Tags tragen mitunter
#: fuenf und mehr (``1.2.3.4.10``) -- und der fruhere String-Rueckhalt
#: haette ``.10`` vor ``.9`` sortiert, weil "1" < "9" als Text gilt.
#: Acht Stellen decken alles ab, was je im Freien rumlief.
_SCHLUESSEL_TIEFE = 8


def _schluessel(version: str) -> tuple:
    """Sortierschluessel: Zahlenkopf zuerst, Vorabversion danach kleiner.

    Die Zahlen kommen ausschliesslich aus dem Kopf. Sonst wuerde die
    ``1`` aus ``1.0.0-rc1`` mitzaehlen und die Vorabversion vor die
    fertige Fassung schieben.

    Der letzte Teil ordnet nur noch den NACHTRAG hinter dem Kopf --
    Build-Metadaten (hinter ``+``) sind dabei abgeschnitten, wie es
    SemVer verlangt: ``1.0.0+build1`` ist dieselbe Version wie
    ``1.0.0``. Und weil ungleiche Schreibtiefe im Kopf durch die
    Nullen im Zahlenteil schon gleichsteht, ist ``1.2 == 1.2.0`` --
    ein Re-Tag mit angehaengter Null darf kein Update-Badge wecken.
    """
    v = normalisiere(version)
    kopf = _KOPF.match(v)
    zahlen = (
        tuple(int(z) for z in kopf.group(0).split(".")[:_SCHLUESSEL_TIEFE])
        if kopf
        else ()
    )
    zahlen = zahlen + (0,) * (_SCHLUESSEL_TIEFE - len(zahlen))
    nachtrag = _KOPF.sub("", v).split("+", 1)[0]
    return (zahlen, 0 if ist_vorabversion(v) else 1, nachtrag)


def vergleiche(links: str, rechts: str) -> int:
    """-1, 0 oder 1 -- wie ein Dreiwegevergleich."""
    a, b = _schluessel(links), _schluessel(rechts)
    return (a > b) - (a < b)


def neuer_als(kandidat: str, installiert: str) -> bool:
    """Ist ``kandidat`` eine echte Aktualisierung gegenueber ``installiert``?"""
    if not installiert:
        return bool(kandidat)
    return vergleiche(kandidat, installiert) > 0


@dataclass(frozen=True)
class Aktualisierung:
    """Was ein Update-Lauf herausgefunden hat."""

    verfuegbar: bool
    installiert: str
    neueste: str
    tag: str = ""

    def __bool__(self) -> bool:
        return self.verfuegbar


def waehle_version(
    releases: list[Release],
    installiert: str = "",
    mit_vorabversionen: bool = False,
) -> Aktualisierung:
    """Sucht die hoechste passende Version aus einer Release-Liste."""
    kandidaten = [
        r
        for r in releases
        if mit_vorabversionen or not (r.vorabversion or ist_vorabversion(r.tag))
    ]
    if not kandidaten:
        return Aktualisierung(False, installiert, normalisiere(installiert))

    beste = max(kandidaten, key=lambda r: _schluessel(r.tag))
    neueste = normalisiere(beste.tag)
    return Aktualisierung(
        verfuegbar=neuer_als(neueste, normalisiere(installiert)),
        installiert=normalisiere(installiert),
        neueste=neueste,
        tag=beste.tag,
    )
