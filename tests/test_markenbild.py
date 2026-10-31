"""Das Markenbild: logo.png ist das eine Icon.

EIN Bild ueberall, wo ein Logo gebraucht
wird. Diese Pruefungen halten die Zusage gegen den Stand:

* logo.png ist die 512er-Form der Marke (Avatar, exe, Verpackung);
  die volle Quelle liegt nicht mehr im Repository
* das Panel traegt kein eigenes Logo mehr: die Leiste
  ist die von Home Assistant, wie bei HACS -- die Marke lebt in der
  Seitenleiste (Iconset) und auf der Ladentheke

Absichtlich ohne Bildbibliothek: der CI-Raum hat keine, und die Form
(PNG-Kopf, Groesse, Zeichen im panel.js) sagt genug. Getrocknet wie
alle Tests -- keine Netzanfrage, keine Instanz.
"""

from __future__ import annotations

from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
PNG_KOPF = b"\x89PNG\r\n\x1a\n"


def _ist_png(pfad: Path) -> bool:
    return pfad.read_bytes()[:8] == PNG_KOPF


def test_die_512er_form_ist_die_gleiche_marke():
    form = WURZEL / "logo.png"
    assert form.exists(), "logo.png fehlt -- die Avatar-/exe-Form der Marke"
    assert _ist_png(form)
    groesse = form.stat().st_size
    assert 20_000 < groesse < 200_000, (
        f"logo.png wiegt {groesse} Bytes -- GitLims Avatarlimit (200 KiB) "
        "und Ladezeit zugleich"
    )
