"""Zielpfade: wohin welche Kategorie gehoert, und welcher Ausschnitt
eines Archivs wandert. Reine Berechnung -- kein einziger Test hier
ruehrt eine Datei an, das Entpacken ist Sache von test_entpacken."""

from pathlib import PurePosixPath

import pytest
from haigs.core.zielpfade import (
    Ausschnitt,
    ZielpfadFehler,
    ausschnitt,
    waehle_eintraege,
    zielverzeichnis,
)

# ------------------------------------------------- Zielpfade je Kategorie


def test_integration_liegt_unter_custom_components():
    assert zielverzeichnis("integration", "haigs") == PurePosixPath(
        "custom_components/haigs"
    )


def test_plugin_liegt_unter_www_community():
    assert zielverzeichnis("plugin", "MeinPlugin") == PurePosixPath(
        "www/community/MeinPlugin"
    )


def test_theme_und_python_script_liegen_flach():
    assert zielverzeichnis("theme", "MeinTheme") == PurePosixPath("themes")
    assert zielverzeichnis("python_script", "hallo_welt") == PurePosixPath(
        "python_scripts"
    )


def test_appdaemon_und_template_bekommen_eigenen_ordner():
    assert zielverzeichnis("appdaemon", "meine_app") == PurePosixPath("apps/meine_app")
    assert zielverzeichnis("template", "meine_vorlage") == PurePosixPath(
        "templates/meine_vorlage"
    )


def test_unbekannte_kategorie_wird_abgewiesen():
    with pytest.raises(ZielpfadFehler):
        zielverzeichnis("netdaemon", "irgendwas")


@pytest.mark.parametrize(
    "name",
    ["", "  ", ".", "..", "a/b", "a\\b", ".versteckt", "a\x00b"],
)
def test_untaugliche_namen_werden_abgewiesen(name):
    with pytest.raises(ZielpfadFehler):
        zielverzeichnis("integration", name)


# ------------------------------------------- Ausschnitt aus der hacs.json


def test_ohne_angaben_steckt_der_inhalt_im_tag_ordner():
    assert ausschnitt(None) == Ausschnitt(art="unterordner", unterordner="")
    assert ausschnitt({}) == Ausschnitt(art="unterordner", unterordner="")


def test_filename_waehlt_genau_eine_datei():
    ergebnis = ausschnitt({"filename": "dist.js"})
    assert ergebnis.art == "dateien"
    assert ergebnis.dateien == ("dist.js",)


def test_filename_gilt_auch_neben_zip_release():
    """Das Plugin-Normalfall: das Anhang-Archiv enthaelt die Datei in
    der Wurzel, das Quell-Archiv unter dem Tag-Ordner -- beides mal
    entscheidet filename."""
    ergebnis = ausschnitt({"filename": "dist.js", "zip_release": True})
    assert ergebnis.art == "dateien"


def test_content_in_root_und_zip_release_bedienen_die_wurzel():
    assert ausschnitt({"content_in_root": True}).art == "wurzel"
    assert ausschnitt({"zip_release": True}).art == "wurzel"


def test_hacs_json_ohne_objekt_wird_abgewiesen():
    with pytest.raises(ZielpfadFehler):
        ausschnitt(["liste", "ist", "kein", "objekt"])


# ---------------------------------------------- Eintraege des Archivs


def test_wurzel_uebernimmtdie_eintraege_eins_zu_eins():
    namen = ["a.py", "b/c.py", "b/"]
    assert waehle_eintraege(Ausschnitt(art="wurzel"), namen) == {
        "a.py": "a.py",
        "b/c.py": "b/c.py",
    }


def test_datei_in_der_wurzel_des_archivs():
    ergebnis = waehle_eintraege(
        Ausschnitt(art="dateien", dateien=("dist.js",)), ["dist.js", "liesmich.md"]
    )
    assert ergebnis == {"dist.js": "dist.js"}


def test_datei_unter_dem_tag_ordner():
    """GitLab und GitHub packen den Quellinhalt unter einen Ordner --
    die gesuchte Datei heisst dort ``projekt-v1/dist.js``."""
    namen = ["projekt-v1/dist.js", "projekt-v1/liesmich.md"]
    ergebnis = waehle_eintraege(Ausschnitt(art="dateien", dateien=("dist.js",)), namen)
    assert ergebnis == {"projekt-v1/dist.js": "dist.js"}


def test_fehlende_datei_wird_benannt():
    with pytest.raises(ZielpfadFehler, match="dist.js"):
        waehle_eintraege(Ausschnitt(art="dateien", dateien=("dist.js",)), ["anderes.js"])


def test_mehrdeutige_datei_wird_abgewiesen():
    namen = ["a/dist.js", "b/dist.js"]
    with pytest.raises(ZielpfadFehler, match="mehrfach"):
        waehle_eintraege(Ausschnitt(art="dateien", dateien=("dist.js",)), namen)


def test_tag_ordner_wird_abgeleitet_und_faellt_weg():
    namen = [
        "mein-projekt-v1.2.0/manifest.json",
        "mein-projekt-v1.2.0/integration/__init__.py",
        "mein-projekt-v1.2.0/integration/leer/",
    ]
    ergebnis = waehle_eintraege(Ausschnitt(), namen)
    assert ergebnis == {
        "mein-projekt-v1.2.0/manifest.json": "manifest.json",
        "mein-projekt-v1.2.0/integration/__init__.py": "integration/__init__.py",
    }


def test_verschiedene_oberste_ordner_sind_nicht_eindeutig():
    with pytest.raises(ZielpfadFehler, match="nicht eindeutig"):
        waehle_eintraege(Ausschnitt(), ["a/x.py", "b/y.py"])


def test_flaches_archiv_ohne_content_in_root_wird_benannt():
    """Steht der Inhalt doch in der Wurzel, fehlt der Hinweis -- der
    Fehler sagt, was an der hacs.json fehlt, statt still nichts zu tun."""
    with pytest.raises(ZielpfadFehler, match="content_in_root"):
        waehle_eintraege(Ausschnitt(), ["nur_eine_datei.py"])


def test_benannter_unterordner_faellt_weg():
    namen = ["fester-ordner/a.py", "fester-ordner/b/c.py"]
    ergebnis = waehle_eintraege(
        Ausschnitt(art="unterordner", unterordner="fester-ordner"), namen
    )
    assert ergebnis == {"fester-ordner/a.py": "a.py", "fester-ordner/b/c.py": "b/c.py"}


def test_fehlender_unterordner_wird_benannt():
    ergebnis = Ausschnitt(art="unterordner", unterordner="gibts-nicht")
    with pytest.raises(ZielpfadFehler, match="gibts-nicht"):
        waehle_eintraege(ergebnis, ["anderes/a.py"])
