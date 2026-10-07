"""Gitea als Anbieter (REST API v1) -- die Schwester von Forgejo.

Forgejo ist aus Gitea gegabelt; die API v1 ist seither weitgehend
gemeinsam geblieben. Deshalb ist :class:`GiteaForge` keine eigene
Uebersetzung der Endpunkte, sondern die Tochter der
:class:`~forgejo_forge.ForgejoForge` -- sie unterscheidet sich in
genau **zwei** Stuecken:

* der Name (``gitea`` statt ``forgejo``) -- er wandert in Identitaet,
  Speicherschluessel und Anzeige-Suffix (``foo/bar*gitea``);
* die Stichwortsuche: Gitea kennt und ehrt den Parameter ``topic``
  der Repositoriums-Suche -- ``q=hacs&topic=true`` sucht Themen
  statt Namen. Forgejo (gemessen an codeberg.org) ignoriert ihn;
  deshalb schickt nur diese Tochter ihn mit.

Alles andere -- Stammdaten, Releases, Tags, Dateien, Archive,
Anhaenge, Auflistung von Organisationen und Benutzern -- erbt sie
unveraendert: dass die Elternklasse ohne jede Sonderbehandlung im
Ablauf auskommt, ist der Beweis von Stufe M9; Gitea ist derselbe
Beweis, ein zweites Mal geflogen (Flug 2088).
"""

from __future__ import annotations

from .forgejo_forge import ForgejoForge
from .identity import GITEA

#: Das Topic, mit dem ein Besitzer sagt: dieses Projekt darf gefunden
#: werden -- dasselbe Wort wie bei GitLab und Forgejo.
TOPIC = "hacs"


class GiteaForge(ForgejoForge):
    """Umsetzung von :class:`~forge.Forge` fuer Gitea."""

    provider = GITEA

    #: Gitea ehrt ``topic=true`` in der Stichwortsuche; Forgejo
    #: ignoriert den Parameter. Die Elternklasse entscheidet allein
    #: an dieser Schaltung, ob sie ihn mitschickt -- nichts wird
    #: doppelt gewusst oder doppelt geschrieben.
    SUCHE_MIT_TOPIC_PARAMETER = True
