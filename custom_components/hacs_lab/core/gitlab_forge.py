"""GitLab als Anbieter (REST API v4).

Bewusst ohne feste HTTP-Bibliothek: der :class:`HttpClient` wird
hineingereicht. In Home Assistant ist das die aiohttp-Sitzung, in den
Tests eine Attrappe mit vorbereiteten Antworten.
"""

from __future__ import annotations

from urllib.parse import quote

from .forge import Commit, ForgeFehler, HttpClient, NichtGefunden, Release, RepositoryInfo
from .identity import GITLAB, RepositoryIdentity, strip_suffix

#: Das Topic, mit dem ein Besitzer sagt: dieses Projekt darf gefunden werden.
TOPIC = "hacs"


def _kodiere(pfad: str) -> str:
    """Aus ``gruppe/projekt`` wird ``gruppe%2Fprojekt`` fuer die Projects API."""
    return quote(strip_suffix(pfad).strip("/"), safe="")


def _id_kodiere(anbieter_id: str) -> str:
    """Eine Anbieter-ID als URL-Stueck -- nur Ziffern duerfen es sein.

    Die ID kommt aus der Ablage, nicht vom Menschen. Alles, was nicht
    wie eine GitLab-Projekt-ID aussieht, wird hier abgewiesen, bevor
    es auf dem Weg durch die URL irgendwo Schaden anrichtet.
    """
    gereinigt = str(anbieter_id or "").strip()
    if not gereinigt.isdigit():
        raise ForgeFehler("keine GitLab-Projekt-ID: " + repr(gereinigt))
    return gereinigt


def _zu_info(roh: dict) -> RepositoryInfo:
    web = roh.get("web_url") or ""
    return RepositoryInfo(
        provider_id=str(roh["id"]),
        full_name=roh["path_with_namespace"],
        beschreibung=roh.get("description") or "",
        standardzweig=roh.get("default_branch") or "main",
        topics=tuple(roh.get("topics") or ()),
        sterne=int(roh.get("star_count") or 0),
        offene_tickets=int(roh.get("open_issues_count") or 0),
        archiviert=bool(roh.get("archived")),
        web_url=web,
        # Die Web-Ansichten von Tickets und Releases: GitLab haengt sie
        # an die Projekt-Adresse. Anbieterwissen bleibt hier, nirgendwo sonst.
        tickets_url=(web + "/-/issues") if web else "",
        releases_url=(web + "/-/releases") if web else "",
        avatar_url=str(roh.get("avatar_url") or ""),
    )


class GitLabForge:
    """Umsetzung von :class:`~forge.Forge` fuer GitLab."""

    provider = GITLAB

    def __init__(self, http: HttpClient, host: str) -> None:
        self.http = http
        self.host = host.rstrip("/").removeprefix("https://").removeprefix("http://")
        self.api = "https://" + self.host + "/api/v4"

    # -- Stammdaten ---------------------------------------------------
    async def repository(self, pfad: str) -> RepositoryInfo:
        roh = await self._json(self.api + "/projects/" + _kodiere(pfad))
        if not isinstance(roh, dict) or "id" not in roh:
            raise NichtGefunden("kein Projekt unter " + pfad + " auf " + self.host)
        return _zu_info(roh)

    async def repository_nach_id(self, anbieter_id: str) -> RepositoryInfo:
        """Stammdaten ueber die numerische Projekt-ID (Stufe M8).

        Die Projects-API nimmt IDs genauso an wie Pfade -- dasselbe
        Tor, stabiler Weg. Ein umbenanntes Projekt antwortet hier mit
        seinem neuen ``path_with_namespace``; ein geloeschtes gar
        nicht mehr.
        """
        roh = await self._json(self.api + "/projects/" + _id_kodiere(anbieter_id))
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
            self.api + "/projects/" + _kodiere(pfad) + "/releases",
            {"per_page": "30"},
        )
        ergebnis: list[Release] = []
        for eintrag in roh or []:
            tag = eintrag.get("tag_name")
            if not tag:
                continue
            links = (eintrag.get("assets") or {}).get("links") or []
            anhaenge = {a.get("name", ""): a.get("url", "") for a in links}
            ergebnis.append(
                Release(
                    tag=tag,
                    name=eintrag.get("name") or tag,
                    beschreibung=eintrag.get("description") or "",
                    veroeffentlicht_am=eintrag.get("released_at") or "",
                    vorabversion=bool(eintrag.get("upcoming_release")),
                    anhaenge=anhaenge,
                )
            )
        return ergebnis

    async def tags(self, pfad: str) -> list[str]:
        """Rueckfallebene: Projekte ohne Releases, aber mit Tags."""
        roh = await self._json(
            self.api + "/projects/" + _kodiere(pfad) + "/repository/tags",
            {"per_page": "30"},
        )
        return [t["name"] for t in roh or [] if t.get("name")]

    async def zweig_stand(self, pfad: str, zweig: str) -> Commit:
        """Kopf eines Zweigs ueber die Branches-API (Flug 2101)."""
        roh = await self._json(
            self.api
            + "/projects/"
            + _kodiere(pfad)
            + "/repository/branches/"
            + quote(zweig, safe="")
        )
        kopf = (roh or {}).get("commit") if isinstance(roh, dict) else None
        if not isinstance(kopf, dict) or not kopf.get("id"):
            raise NichtGefunden("kein Zweig " + zweig + " in " + pfad + " auf " + self.host)
        return Commit(
            sha=str(kopf["id"]),
            datum=str(kopf.get("committed_date") or kopf.get("created_at") or ""),
            nachricht=str(kopf.get("title") or kopf.get("message") or "").strip(),
        )

    # -- Inhalte ------------------------------------------------------
    async def datei(self, pfad: str, datei: str, ref: str) -> bytes:
        url = (
            self.api
            + "/projects/"
            + _kodiere(pfad)
            + "/repository/files/"
            + quote(datei, safe="")
            + "/raw?ref="
            + quote(ref, safe="")
        )
        return await self.http.get_bytes(url)

    async def archiv(self, pfad: str, ref: str) -> bytes:
        """Das Quell-Archiv einer Version -- Stufe M5, hinter der Naht."""
        return await self.http.get_bytes(await self.archiv_url(pfad, ref))

    async def anhang(self, url: str) -> bytes:
        """Laedt einen Release-Anhang (Stufe M4b) ueber den HTTP-Zugang.

        Die Adresse stammt aus den Anhaengen eines Releases -- sie ist
        eine Anbieteradresse (Paketregister oder Link), braucht also
        Sitzung und Token wie jeder andere Abruf auch.
        """
        return await self.http.get_bytes(url)

    async def archiv_url(self, pfad: str, ref: str) -> str:
        return (
            self.api
            + "/projects/"
            + _kodiere(pfad)
            + "/repository/archive.zip?sha="
            + quote(ref, safe="")
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
        # Ohne Grenze: volle Seiten, und der HTTP-Zugang blaettert bis
        # zum Ende. Mit Grenze: hoechstens so viele Eintraege, genau
        # eine Seite. Beides muss gesetzt werden -- ein kleineres
        # per_page allein bremst nichts, weil sonst weitergeblaettert
        # wird, bis die Liste zu Ende ist.
        menge = 100 if grenze is None else max(1, grenze)
        params = {"topic": topic, "per_page": str(menge), "archived": "false"}
        if stichwort:
            # GitLab sucht damit in Name und Beschreibung -- das Topic
            # bleibt als eigene Bedingung daneben scharf.
            params["search"] = stichwort
        if gruppe:
            url = self.api + "/groups/" + _kodiere(gruppe) + "/projects"
            if mit_untergruppen:
                params["include_subgroups"] = "true"
        else:
            url = self.api + "/projects"
        roh = await self._json(url, params, seiten=None if grenze is None else 1)
        return [_zu_info(p) for p in roh or [] if "id" in p]

    # -- intern -------------------------------------------------------
    async def _json(
        self,
        url: str,
        params: dict[str, str] | None = None,
        *,
        seiten: int | None = None,
    ):
        antwort = await self.http.get_json(url, params, seiten=seiten)
        if isinstance(antwort, dict) and "message" in antwort and "id" not in antwort:
            meldung = str(antwort["message"])
            if "404" in meldung:
                raise NichtGefunden(meldung)
            raise ForgeFehler(meldung)
        return antwort
