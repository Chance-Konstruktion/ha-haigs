"""Der HACS-Katalog als Schmiede (Flug 2102) -- alles in einem Laden.

Wer HAIGS statt HACS benutzen will, braucht die Repositories, die
HACS kennt. HACS selbst laedt seine Liste aus einem oeffentlichen
Katalog (``data-v2.hacs.xyz``): je Kategorie eine JSON-Datei mit Name,
Beschreibung, Sternen, Downloads, Domain, letzter Version und Datum.
Genau diesen Katalog liest diese Schmiede -- und kommt damit ohne
einzigen Abruf der GitHub-API aus (die erlaubt ohne Token nur 60
Abfragen die Stunde, und ein Token wollen wir niemandem abverlangen):

* Liste, Stammdaten, Versionen  -> der Katalog (ETag-Zwischenspeicher)
* README und ``hacs.json``      -> ``raw.githubusercontent.com``
* Archiv einer Version          -> ``codeload.github.com``
* Release-ZIP (``zip_release``) -> ``github.com/.../releases/download``

Was die Schmiede NICHT kann: den Entwicklermodus (der Kopf eines Zweigs
braucht die API). Er bleibt den eigenen Schmieden vorbehalten.
"""

from __future__ import annotations

import io
import json
import stat
import time
import zipfile
from pathlib import PurePosixPath
from typing import Any

from .entdeckung import Fund
from .forge import Commit, ForgeFehler, HttpClient, NichtGefunden, Release, RepositoryInfo
from .identity import GITHUB, RepositoryIdentity
from .validierung import Befund

#: Der Katalog, aus dem HACS selbst liest.
KATALOG_URL = "https://data-v2.hacs.xyz/{kategorie}/data.json"

#: Die Kategorien des Katalogs -- dieselben Worte wie in HAIGS.
KATALOG_KATEGORIEN = ("integration", "plugin", "theme")

#: Wie lange der Katalog als frisch gilt. HACS selbst erneuert ihn
#: nicht oefter; der ETag macht jeden Abruf danach ohnehin billig.
KATALOG_FRISCH_SEK = 3 * 3600

#: Der Host, unter dem die Katalog-Repositories stehen.
KATALOG_HOST = "github.com"


#: Marke am Ende einer Anhang-Adresse: "diese Einzeldatei in ein ZIP packen".
_EINZELDATEI = "#haigs-einzeldatei"


def _ohne_symlinks(archiv: bytes) -> bytes:
    """Das Quellarchiv ohne Symlinks.

    GitHub-Quellarchive enthalten Symlinks aus dem Repository (etwa
    ``docs/chlog.md``). Der Kern weist solche Eintraege bewusst ab --
    ein Symlink ist ein klassischer Weg aus dem Zielordner heraus.
    Fuer den Katalog fallen sie hier einfach weg: sie sind nie der
    Inhalt, den HACS installiert. Archive ohne Symlink bleiben
    unberuehrt, kaputte Archive ebenfalls (der Kern meldet sie dann).
    """
    try:
        with zipfile.ZipFile(io.BytesIO(archiv)) as quelle:
            infos = quelle.infolist()
            if not any(stat.S_ISLNK(i.external_attr >> 16) for i in infos):
                return archiv
            ziel = io.BytesIO()
            with zipfile.ZipFile(ziel, "w", zipfile.ZIP_DEFLATED) as neu:
                for info in infos:
                    if stat.S_ISLNK(info.external_attr >> 16):
                        continue
                    neu.writestr(info, quelle.read(info.filename))
            return ziel.getvalue()
    except zipfile.BadZipFile:
        return archiv


def _info(repo_id: str, roh: dict[str, Any], kategorie: str) -> RepositoryInfo:
    """Eine Zeile des Katalogs als Stammdaten."""
    voll = str(roh.get("full_name") or "")
    besitzer = voll.split("/", 1)[0]
    domain = str(roh.get("domain") or "")
    # Das Bild: bei Integrationen das Marken-Icon (dasselbe, das HACS
    # zeigt), sonst das Bild des Besitzers auf GitHub.
    bild = (
        f"https://brands.home-assistant.io/_/{domain}/icon.png"
        if kategorie == "integration" and domain
        else f"https://github.com/{besitzer}.png?size=64"
    )
    themen = tuple(str(t) for t in (roh.get("topics") or ()))
    return RepositoryInfo(
        provider_id=str(repo_id),
        full_name=voll,
        beschreibung=str(roh.get("description") or ""),
        # raw.githubusercontent.com versteht HEAD als Standardzweig --
        # der Katalog nennt den Zweig nicht, und nachfragen hiesse API.
        standardzweig="HEAD",
        topics=("hacs", "hacs-" + kategorie, *themen),
        sterne=int(roh.get("stargazers_count") or 0),
        offene_tickets=int(roh.get("open_issues") or 0),
        archiviert=False,
        web_url="https://github.com/" + voll,
        tickets_url="https://github.com/" + voll + "/issues",
        releases_url="https://github.com/" + voll + "/releases",
        avatar_url=bild,
        downloads=int(roh.get("downloads") or 0),
        zuletzt_aktiv=str(roh.get("last_updated") or ""),
    )


class HacsKatalogForge:
    """Umsetzung von :class:`~forge.Forge` ueber den HACS-Katalog."""

    provider = GITHUB

    def __init__(self, http: HttpClient, host: str = KATALOG_HOST) -> None:
        self.http = http
        self.host = KATALOG_HOST
        self._zeilen: dict[str, tuple[dict[str, Any], str]] = {}
        self._nach_name: dict[str, str] = {}
        self._geholt_am = 0.0

    # -- der Katalog --------------------------------------------------
    async def katalog(
        self, frisch: bool = False
    ) -> dict[str, tuple[dict[str, Any], str]]:
        """Alle Zeilen: Repo-ID -> (Rohdaten, Kategorie).

        Scheitert eine Kategorie, bleibt ihr alter Stand stehen; scheitern
        alle beim ersten Mal, ist das ein Fehler der Schmiede.
        """
        if (
            self._zeilen
            and not frisch
            and time.monotonic() - self._geholt_am < KATALOG_FRISCH_SEK
        ):
            return self._zeilen
        neu: dict[str, tuple[dict[str, Any], str]] = {}
        gescheitert: list[str] = []
        for kategorie in KATALOG_KATEGORIEN:
            try:
                roh = await self.http.get_json(KATALOG_URL.format(kategorie=kategorie))
            except Exception as fehler:  # noqa: BLE001 - eine Kategorie darf fehlen
                gescheitert.append(f"{kategorie}: {fehler}")
                neu.update({k: v for k, v in self._zeilen.items() if v[1] == kategorie})
                continue
            if not isinstance(roh, dict):
                gescheitert.append(f"{kategorie}: unerwartete Antwort")
                continue
            for repo_id, zeile in roh.items():
                if isinstance(zeile, dict) and "/" in str(zeile.get("full_name") or ""):
                    neu[str(repo_id)] = (zeile, kategorie)
        if not neu:
            raise ForgeFehler("HACS-Katalog nicht erreichbar: " + "; ".join(gescheitert))
        self._zeilen = neu
        self._nach_name = {
            str(zeile["full_name"]).lower(): repo_id
            for repo_id, (zeile, _) in neu.items()
        }
        self._geholt_am = time.monotonic()
        return self._zeilen

    async def _zeile(self, pfad: str) -> tuple[str, dict[str, Any], str]:
        katalog = await self.katalog()
        repo_id = self._nach_name.get(pfad.strip("/").lower())
        if repo_id is None:
            raise NichtGefunden(pfad + " steht nicht im HACS-Katalog")
        zeile, kategorie = katalog[repo_id]
        return repo_id, zeile, kategorie

    async def kategorie(self, pfad: str) -> str:
        """Die Kategorie, unter der HACS das Repository fuehrt."""
        return (await self._zeile(pfad))[2]

    async def katalog_funde(self, stichwort: str | None = None) -> list:
        """Der ganze Katalog als Funde -- ohne ``hacs.json``-Abruf je Repo.

        HACS hat jedes Repository bei der Aufnahme in den Katalog schon
        geprueft; ein zweiter Abruf je Kandidat waeren ueber 4000
        Anfragen an GitHub bei jedem Lauf.
        """
        nadel = (stichwort or "").strip().lower()
        funde = []
        for repo_id, (zeile, kategorie) in (await self.katalog()).items():
            info = _info(repo_id, zeile, kategorie)
            if nadel and nadel not in (info.full_name + " " + info.beschreibung).lower():
                continue
            identitaet = RepositoryIdentity(
                provider=self.provider,
                host=self.host,
                provider_id=info.provider_id,
                full_name=info.full_name,
            )
            name = str(
                (zeile.get("manifest") or {}).get("name")
                or zeile.get("manifest_name")
                or ""
            )
            funde.append(
                Fund(
                    identitaet,
                    info,
                    Befund(True, kategorie=kategorie, name=name),
                    letzte_version=str(zeile.get("last_version") or ""),
                )
            )
        return funde

    # -- Stammdaten ---------------------------------------------------
    async def repository(self, pfad: str) -> RepositoryInfo:
        repo_id, zeile, kategorie = await self._zeile(pfad)
        return _info(repo_id, zeile, kategorie)

    async def repository_nach_id(self, anbieter_id: str) -> RepositoryInfo:
        katalog = await self.katalog()
        if str(anbieter_id) not in katalog:
            raise NichtGefunden(f"ID {anbieter_id} steht nicht (mehr) im HACS-Katalog")
        zeile, kategorie = katalog[str(anbieter_id)]
        return _info(str(anbieter_id), zeile, kategorie)

    async def identitaet(self, pfad: str) -> RepositoryIdentity:
        info = await self.repository(pfad)
        return RepositoryIdentity(
            provider=self.provider,
            host=self.host,
            provider_id=info.provider_id,
            full_name=info.full_name,
        )

    async def suche_nach_topic(
        self,
        topic: str = "hacs",
        gruppe: str | None = None,
        stichwort: str | None = None,
        mit_untergruppen: bool = True,
        grenze: int | None = None,
    ) -> list[RepositoryInfo]:
        """Der Katalog als Kandidatenliste (fuer Herzschlag und Probe)."""
        nadel = (stichwort or "").strip().lower()
        ergebnis: list[RepositoryInfo] = []
        for repo_id, (zeile, kategorie) in (await self.katalog()).items():
            info = _info(repo_id, zeile, kategorie)
            if gruppe and not info.full_name.lower().startswith(
                gruppe.lower().strip("/") + "/"
            ):
                continue
            if nadel and nadel not in (info.full_name + " " + info.beschreibung).lower():
                continue
            ergebnis.append(info)
            if grenze is not None and len(ergebnis) >= grenze:
                break
        return ergebnis

    # -- Versionen ----------------------------------------------------
    async def _hacs_json(self, pfad: str, ref: str) -> dict[str, Any]:
        try:
            roh = await self.datei(pfad, "hacs.json", ref)
            daten = json.loads(roh.decode("utf-8", errors="replace"))
        except Exception:  # noqa: BLE001 - ohne hacs.json gilt das Quellarchiv
            return {}
        return daten if isinstance(daten, dict) else {}

    async def releases(self, pfad: str) -> list[Release]:
        """Die letzte Version laut Katalog -- mit dem ZIP, wenn HACS eins nimmt.

        Steht in der ``hacs.json`` des Tags ``zip_release`` samt
        ``filename``, laedt HACS dieses ZIP aus dem Release; HAIGS
        tut dasselbe (es ist der Anhang, den die Installation zuerst
        nimmt). Sonst bleibt das Quellarchiv des Tags.
        """
        _, zeile, _ = await self._zeile(pfad)
        tag = str(zeile.get("last_version") or "")
        if not tag:
            return []
        anhaenge: dict[str, str] = {}
        hacs = await self._hacs_json(pfad, tag)
        datei = str(hacs.get("filename") or "")
        adresse = f"https://github.com/{pfad}/releases/download/{tag}/"
        if hacs.get("zip_release") and datei.lower().endswith(".zip"):
            anhaenge[datei] = adresse + datei
        elif datei and not hacs.get("zip_release") and tag:
            # Plugins und Themes: HACS laedt die gebaute Einzeldatei aus
            # dem Release. Sie wird beim Laden in ein kleines ZIP gepackt
            # (siehe anhang), damit die Installation einen Weg kennt.
            anhaenge[datei + ".zip"] = adresse + PurePosixPath(datei).name + _EINZELDATEI
        return [
            Release(
                tag=tag,
                name=tag,
                veroeffentlicht_am=str(zeile.get("last_updated") or ""),
                vorabversion=False,
                anhaenge=anhaenge,
            )
        ]

    async def tags(self, pfad: str) -> list[str]:
        """Der Katalog kennt keine Tags ausser der letzten Version."""
        return []

    async def zweig_stand(self, pfad: str, zweig: str) -> Commit:
        raise ForgeFehler(
            "Den Entwicklermodus gibt es fuer den HACS-Katalog nicht -- "
            "er braeuchte die GitHub-API"
        )

    # -- Inhalte ------------------------------------------------------
    async def datei(self, pfad: str, datei: str, ref: str) -> bytes:
        return await self.http.get_bytes(
            f"https://raw.githubusercontent.com/{pfad}/{ref or 'HEAD'}/{datei}"
        )

    async def archiv_url(self, pfad: str, ref: str) -> str:
        return f"https://codeload.github.com/{pfad}/zip/{ref}"

    async def archiv(self, pfad: str, ref: str) -> bytes:
        return _ohne_symlinks(await self.http.get_bytes(await self.archiv_url(pfad, ref)))

    async def anhang(self, url: str) -> bytes:
        if not url.endswith(_EINZELDATEI):
            return await self.http.get_bytes(url)
        return await self._einzeldatei(url[: -len(_EINZELDATEI)])

    async def _einzeldatei(self, url: str) -> bytes:
        """Eine Release-Datei als ZIP mit der zugehoerigen ``hacs.json``.

        Gibt es sie im Release nicht, sucht die Schmiede wie HACS an den
        ueblichen Stellen des Tags (``dist/`` und Wurzel).
        """
        teile = url.split("/releases/download/")[0].removeprefix("https://github.com/")
        tag = url.split("/releases/download/")[1].split("/", 1)[0]
        name = url.rsplit("/", 1)[1]
        hacs = await self._hacs_json(teile, tag)
        gewuenscht = str(hacs.get("filename") or name)
        inhalt: bytes | None = None
        try:
            inhalt = await self.http.get_bytes(url)
        except NichtGefunden:
            for kandidat in (f"dist/{name}", name):
                try:
                    inhalt = await self.datei(teile, kandidat, tag)
                    break
                except NichtGefunden:
                    continue
        if inhalt is None:
            raise NichtGefunden(f"{name} liegt weder im Release {tag} noch im Tag")
        puffer = io.BytesIO()
        with zipfile.ZipFile(puffer, "w", zipfile.ZIP_DEFLATED) as zip_datei:
            zip_datei.writestr("hacs.json", json.dumps(hacs or {"filename": gewuenscht}))
            zip_datei.writestr(gewuenscht, inhalt)
        return puffer.getvalue()
