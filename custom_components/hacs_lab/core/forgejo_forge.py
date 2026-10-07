"""Forgejo als Anbieter (REST API v1) -- Codeberg ist die Referenzinstanz.

Bewusst ohne feste HTTP-Bibliothek: der :class:`HttpClient` wird
hineingereicht, genau wie bei :class:`~gitlab_forge.GitLabForge`.
Dass dieser Anbieter ohne jede Sonderbehandlung im Ablauf auskommt,
ist der Beweis, den Stufe M9 verlangt (siehe ROADMAP.md): ein dritter
Anbieter ist eine weitere Klasse und sonst nichts.

Zwei Eigenheiten der Forgejo-API gegenueber GitLab, beide hier
dokumentiert und eingearbeitet:

* Die Projektsuche kennt kein verlaessliches Thema-Filter-Argument.
  Codeberg ignoriert ``topic=`` schlicht (liefert unsortierte
  Neuerscheinungen), ``q=topic:hacs`` trifft dort niemanden. Themen
  sind aber Teil des Suchindexes -- deshalb: Suche ueber das Stichwort,
  danach **exakte** Filterung auf ``topics`` in dieser Umsetzung.
* Organisationen liegen flach. Es gibt kein Untergruppen-Endpunkt,
  ``mit_untergruppen`` ist deshalb ein akzeptiertes, dokumentiertes
  No-op. Eine Gruppe wird ueber ``/orgs/{g}/repos`` gelistet, und wenn
  das keine Organisation ist (sondern ein Benutzer), ueber
  ``/users/{g}/repos``.
"""

from __future__ import annotations

from urllib.parse import quote

from .forge import Commit, ForgeFehler, HttpClient, NichtGefunden, Release, RepositoryInfo
from .identity import FORGEJO, RepositoryIdentity, strip_suffix

#: Das Topic, mit dem ein Besitzer sagt: dieses Projekt darf gefunden werden.
TOPIC = "hacs"

#: Wie viele Projekte je Anfrage geholt werden. Forgejo nennt es ``limit``.
SEITENGROESSE = 50


def _kodiere(pfad: str) -> str:
    """Aus ``gruppe/projekt`` wird ein URL-sicherer Pfad.

    Forgejo adressiert Projekte als zwei Pfadstuecke im Weg -- nicht als
    eine koderte Einheit wie GitLab. Das Suffix der Anzeige wird vorher
    abgenommen: ``foo/bar*forge`` existiert auf der Instanz nicht.
    """
    return quote(strip_suffix(pfad).strip("/"), safe="/")


def _id_kodiere(anbieter_id: str) -> str:
    """Eine Anbieter-ID als URL-Stueck -- nur Ziffern duerfen es sein.

    Die ID kommt aus der Ablage, nicht vom Menschen; alles andere wird
    hier abgewiesen, bevor es durch die URL reist.
    """
    gereinigt = str(anbieter_id or "").strip()
    if not gereinigt.isdigit():
        raise ForgeFehler("keine Forgejo-Projekt-ID: " + repr(gereinigt))
    return gereinigt


def _zu_info(roh: dict) -> RepositoryInfo:
    """Uebersetzt einen Forgejo-Projektdatensatz in die Kernform.

    Die Feldnamen sind die der API v1: ``stars_count``,
    ``open_issues_count``, ``html_url`` -- alles andere bleibt, wie es
    der Kern erwartet.
    """
    return RepositoryInfo(
        provider_id=str(roh["id"]),
        full_name=roh["full_name"],
        beschreibung=roh.get("description") or "",
        standardzweig=roh.get("default_branch") or "main",
        topics=tuple(roh.get("topics") or ()),
        sterne=int(roh.get("stars_count") or 0),
        offene_tickets=int(roh.get("open_issues_count") or 0),
        archiviert=bool(roh.get("archived")),
        web_url=roh.get("html_url") or "",
        avatar_url=str(roh.get("avatar_url") or ""),
    )


class ForgejoForge:
    """Umsetzung von :class:`~forge.Forge` fuer Forgejo."""

    provider = FORGEJO

    #: Schaltet, ob die Stichwortsuche den Parameter ``topic=true``
    #: mitschickt. Gitea (die Schwester, Flug 2088) ehrt ihn und setzt
    #: ihn; Forgejo ignoriert ihn -- gemessen an codeberg.org, der
    #: Referenzinstanz -- und laesst ihn weg. Die exakte Filterung auf
    #: ``topics`` geschieht in beiden Faellen client-seitig; der
    #: Parameter verschaerft nur die Treffermenge, wo er wirkt.
    SUCHE_MIT_TOPIC_PARAMETER = False

    def __init__(self, http: HttpClient, host: str) -> None:
        self.http = http
        self.host = host.rstrip("/").removeprefix("https://").removeprefix("http://")
        self.api = "https://" + self.host + "/api/v1"

    # -- Stammdaten ---------------------------------------------------
    async def repository(self, pfad: str) -> RepositoryInfo:
        roh = await self._json(self.api + "/repos/" + _kodiere(pfad))
        if not isinstance(roh, dict) or "id" not in roh:
            raise NichtGefunden("kein Projekt unter " + pfad + " auf " + self.host)
        return _zu_info(roh)

    async def repository_nach_id(self, anbieter_id: str) -> RepositoryInfo:
        """Stammdaten ueber die numerische Repository-ID (Stufe M8).

        Forgejo hat dafuer ein eigenes Tor: ``/repositories/{id}`` --
        unabhaengig vom Pfad. Ein umbenanntes Projekt meldet hier
        seinen neuen ``full_name``.
        """
        roh = await self._json(self.api + "/repositories/" + _id_kodiere(anbieter_id))
        if not isinstance(roh, dict) or "id" not in roh:
            raise NichtGefunden(
                "kein Projekt unter der ID " + str(anbieter_id) + " auf " + self.host
            )
        return _zu_info(roh)

    async def identitaet(self, pfad: str) -> RepositoryIdentity:
        info = await self.repository(pfad)
        return RepositoryIdentity(
            provider=self.provider,
            host=self.host,
            provider_id=info.provider_id,
            full_name=info.full_name,
        )

    # -- Versionen ----------------------------------------------------
    async def releases(self, pfad: str) -> list[Release]:
        roh = await self._json(
            self.api + "/repos/" + _kodiere(pfad) + "/releases",
            {"limit": str(SEITENGROESSE)},
        )
        ergebnis: list[Release] = []
        for eintrag in roh or []:
            if eintrag.get("draft"):
                # Entwuerfe sind nur mit Schreibrechten sichtbar; liefert
                # eine Instanz sie dennoch, zaehlen sie nicht als
                # veroeffentlichte Version.
                continue
            tag = eintrag.get("tag_name")
            if not tag:
                continue
            anhaenge = {
                a.get("name", ""): a.get("browser_download_url", "")
                for a in eintrag.get("assets") or []
            }
            ergebnis.append(
                Release(
                    tag=tag,
                    name=eintrag.get("name") or tag,
                    veroeffentlicht_am=eintrag.get("published_at") or "",
                    vorabversion=bool(eintrag.get("prerelease")),
                    anhaenge=anhaenge,
                )
            )
        return ergebnis

    async def tags(self, pfad: str) -> list[str]:
        """Rueckfallebene: Projekte ohne Releases, aber mit Tags."""
        roh = await self._json(
            self.api + "/repos/" + _kodiere(pfad) + "/tags",
            {"limit": str(SEITENGROESSE)},
        )
        return [t["name"] for t in roh or [] if t.get("name")]

    async def zweig_stand(self, pfad: str, zweig: str) -> Commit:
        """Kopf eines Zweigs ueber ``/repos/{pfad}/branches/{zweig}`` (Flug 2101)."""
        roh = await self._json(
            self.api + "/repos/" + _kodiere(pfad) + "/branches/" + quote(zweig, safe="")
        )
        kopf = (roh or {}).get("commit") if isinstance(roh, dict) else None
        if not isinstance(kopf, dict) or not kopf.get("id"):
            raise NichtGefunden("kein Zweig " + zweig + " in " + pfad + " auf " + self.host)
        nachricht = (str(kopf.get("message") or "").strip().splitlines() or [""])[0]
        return Commit(
            sha=str(kopf["id"]),
            datum=str(kopf.get("timestamp") or ""),
            nachricht=nachricht,
        )

    # -- Inhalte ------------------------------------------------------
    async def datei(self, pfad: str, datei: str, ref: str) -> bytes:
        url = (
            self.api
            + "/repos/"
            + _kodiere(pfad)
            + "/raw/"
            + quote(datei, safe="/")
            + "?ref="
            + quote(ref, safe="")
        )
        return await self.http.get_bytes(url)

    async def archiv(self, pfad: str, ref: str) -> bytes:
        """Das Quell-Archiv einer Version (Stufe M4b-Nachtrag).

        Fehlte hier bislang -- die Naht verlangte sie, die zweite
        Anbindung lieferte sie nicht. Wer heute aus einem Forgejo-Projekt
        installiert, bekam einen AttributeError statt einer Version.
        """
        return await self.http.get_bytes(await self.archiv_url(pfad, ref))

    async def anhang(self, url: str) -> bytes:
        """Laedt einen Release-Anhang (Stufe M4b) ueber den HTTP-Zugang.

        Die Adresse stammt aus ``browser_download_url`` eines Release-
        Assets -- eine Anbieteradresse, also Sitzung und Token wie bei
        jedem anderen Abruf.
        """
        return await self.http.get_bytes(url)

    async def archiv_url(self, pfad: str, ref: str) -> str:
        return (
            self.api
            + "/repos/"
            + _kodiere(pfad)
            + "/archive/"
            + quote(ref, safe="")
            + ".zip"
        )

    # -- Entdeckung ---------------------------------------------------
    async def suche_nach_topic(
        self,
        topic: str = TOPIC,
        gruppe: str | None = None,
        stichwort: str | None = None,
        mit_untergruppen: bool = True,
        grenze: int | None = None,
    ) -> list[RepositoryInfo]:
        """Alle Projekte, deren Besitzer sie mit ``topic`` gekennzeichnet hat.

        Ohne Gruppe: Stichwort-Suche ueber die Instanz (Themen sind Teil
        des Suchindexes) und danach **exakte** Filterung auf ``topics`` --
        der ``topic``-Parameter der Such-API ist auf Instanzen wie
        Codeberg wirkungslos, darauf ist kein Verlass. Ein
        ``stichwort`` tritt als Suchwort an die Stelle des Themennamens;
        die Themen-Filterung bleibt davon unberuehrt scharf.

        Mit Gruppe: Auflistung der Organisation, Rueckfallebene der
        Benutzer-Listung (404 heisst: das ist keine Organisation). Ein
        ``stichwort`` filtert die Liste hier von Hand -- Name und
        Beschreibung muessen es tragen. ``mit_untergruppen`` wird
        angenommen, ist aber ein No-op -- Forgejo-Organisationen liegen
        flach, ein Untergruppen-Endpunkt existiert nicht.
        """
        menge = SEITENGROESSE if grenze is None else max(1, grenze)
        nur_eine = None if grenze is None else 1
        if gruppe:
            kodiert = quote(strip_suffix(gruppe).strip("/"), safe="")
            try:
                roh = await self._json(
                    self.api + "/orgs/" + kodiert + "/repos",
                    {"limit": str(menge)},
                    seiten=nur_eine,
                )
            except NichtGefunden:
                roh = await self._json(
                    self.api + "/users/" + kodiert + "/repos",
                    {"limit": str(menge)},
                    seiten=nur_eine,
                )
            kandidaten = roh if isinstance(roh, list) else []
            if stichwort:
                nadel = stichwort.lower()
                kandidaten = [
                    p
                    for p in kandidaten
                    if nadel
                    in (
                        str(p.get("full_name") or p.get("name") or "")
                        + " "
                        + str(p.get("description") or "")
                    ).lower()
                ]
        else:
            suchparameter = {
                "q": stichwort if stichwort else topic,
                "limit": str(menge),
            }
            if self.SUCHE_MIT_TOPIC_PARAMETER:
                # Gitea ehrt den Parameter; Forgejo ignoriert ihn. Wo er
                # wirkt, sucht die Instanz Themen statt Namen -- die
                # exakte Filterung unten bleibt trotzdem scharf.
                suchparameter["topic"] = "true"
            antwort = await self._json(
                self.api + "/repos/search",
                suchparameter,
                seiten=nur_eine,
            )
            if isinstance(antwort, dict):
                kandidaten = antwort.get("data") or []
            else:
                # Selten: Instanzen, die die Treffer direkt auflisten.
                kandidaten = antwort or []
        return [
            _zu_info(p)
            for p in kandidaten
            if isinstance(p, dict) and "id" in p and topic in (p.get("topics") or ())
        ]

    # -- intern -------------------------------------------------------
    async def _json(
        self,
        url: str,
        params: dict[str, str] | None = None,
        *,
        seiten: int | None = None,
    ):
        """Wie :meth:`~gitlab_forge.GitLabForge._json`.

        Forgejo meldet Fehler als ``{"message": ...}`` ohne Kennung --
        echte 404 wirft der HTTP-Zugang bereits als
        :class:`NichtGefunden`, diese Stelle deckt Attrappen und Instanzen
        ab, die es doch als Koerper liefern.
        """
        antwort = await self.http.get_json(url, params, seiten=seiten)
        if (
            isinstance(antwort, dict)
            and "message" in antwort
            and "id" not in antwort
            and "data" not in antwort
        ):
            meldung = str(antwort["message"])
            if "404" in meldung:
                raise NichtGefunden(meldung)
            raise ForgeFehler(meldung)
        return antwort
