"""Identitaet eines Repositories.

Der Kern der Unterscheidung: ein Repository wird nicht ueber seinen
Namen identifiziert, sondern ueber Anbieter + Host + Anbieter-ID. Der
Name ist nur Anzeige. Damit koennen ``foo/bar`` von GitHub und
``foo/bar`` aus einem GitLab nebeneinander bestehen, ohne sich zu
verdraengen.

Das Suffix ``*lab`` erzeugt ausschliesslich diese Erweiterung. Im GitLab
selbst wird nichts umbenannt -- die echte Adresse bleibt
``https://gitlab.example.net/foo/bar``.
"""

from __future__ import annotations

from dataclasses import dataclass

GITHUB = "github"
GITLAB = "gitlab"
FORGEJO = "forgejo"
GITEA = "gitea"

#: Anzeige-Suffix je Anbieter. GitHub bleibt ohne Suffix, damit
#: bestehende HACS-Anzeigen unveraendert aussehen. Forgejo traegt
#: ``*forge`` -- vom Anbieternamen abgeleitet, in der Liste ebenso
#: lesbar wie ``*lab`` und von ihm unterscheidbar. Gitea traegt
#: ``*gitea``: Schwester der Forgejo-Familie in der API, aber eigene
#: Software -- eigenes Suffix (Flug 2088).
SUFFIX = {
    GITHUB: "",
    GITLAB: "*lab",
    FORGEJO: "*forge",
    GITEA: "*gitea",
}


class UngueltigeIdentitaet(ValueError):
    """Die Angaben reichen nicht, um ein Repository zu benennen."""


@dataclass(frozen=True)
class RepositoryIdentity:
    """Eindeutige Kennung eines Repositories bei einem Anbieter."""

    provider: str
    host: str
    provider_id: str
    full_name: str

    def __post_init__(self) -> None:
        for feld in ("provider", "host", "provider_id", "full_name"):
            if not str(getattr(self, feld) or "").strip():
                raise UngueltigeIdentitaet(f"{feld} fehlt")
        if "/" not in self.full_name:
            raise UngueltigeIdentitaet(
                f"full_name braucht die Form gruppe/projekt: {self.full_name!r}"
            )
        if self.provider not in SUFFIX:
            raise UngueltigeIdentitaet(f"unbekannter Anbieter: {self.provider!r}")

    @property
    def uid(self) -> str:
        """Interner Schluessel, z. B. ``gitlab:789012``.

        Der Host steckt bewusst nicht darin: die Anbieter-ID ist je
        Instanz vergeben. Zwei Instanzen desselben Anbieters trennt
        :attr:`storage_key`.
        """
        return f"{self.provider}:{self.provider_id}"

    @property
    def storage_key(self) -> str:
        """Schluessel fuer die Ablage -- inklusive Host, also wirklich global."""
        return f"{self.provider}@{self.host}:{self.provider_id}"

    @property
    def display_full_name(self) -> str:
        """Name fuer die Oberflaeche, z. B. ``foo/bar*lab``."""
        return f"{self.full_name}{SUFFIX[self.provider]}"

    def as_dict(self) -> dict[str, str]:
        return {
            "provider": self.provider,
            "host": self.host,
            "provider_id": self.provider_id,
            "full_name": self.full_name,
            "uid": self.uid,
            "storage_key": self.storage_key,
            "display_full_name": self.display_full_name,
        }

    @classmethod
    def from_dict(cls, roh: dict[str, str]) -> RepositoryIdentity:
        return cls(
            provider=roh["provider"],
            host=roh["host"],
            provider_id=str(roh["provider_id"]),
            full_name=roh["full_name"],
        )


def strip_suffix(anzeigename: str) -> str:
    """Nimmt einem Anzeigenamen das Suffix wieder ab.

    Gebraucht, sobald ein Anzeigename zurueck in eine Abfrage geht --
    ``foo/bar*lab`` existiert im GitLab nicht.
    """
    for suffix in SUFFIX.values():
        if suffix and anzeigename.endswith(suffix):
            return anzeigename[: -len(suffix)]
    return anzeigename
