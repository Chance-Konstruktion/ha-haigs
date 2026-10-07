"""Die Integration findet ihren Kern ohne jeden Suchpfad-Griff.

Form-Entscheidung zu #11 (Befund a): der Kern wohnt als Unterpaket in
der Integration (``custom_components/haigs/core``). Damit entfaellt
der Fallback ganz -- und das ist hier der Beweis, nicht die Behauptung.

Eine Sonde im Unterprozess richtet ein Haus in der Lage einer echten
Installation (Integration samt Kern, bewusst OHNE jeden Eintrag auf
dem Suchpfad), dazu Gift-Dateien, die stdlib-Module vortaeuschen --
falls irgendwer doch den Suchpfad streckt. Die Integration muss den
Kern aus dem eigenen Verzeichnis laden, der Suchpfad muss exakt
unveraendert bleiben, und die Gift-Dateien muessen wirkungslos sein.
Gegen jeden Stand, der den Suchpfad anfasst, fliegt jede der drei
Pruefungen -- gegen den alten Fallback (append hinten) genauso wie
gegen das einst boese insert(0).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

REPO = Path(__file__).resolve().parent.parent

# stdlib-Module, die ein frischer Interpreter unberuehrt laedt. Die
# Sonde prueft mindestens einen davon gegen die Gift-Datei im Haus.
GIFT_KANDIDATEN = ("tarfile", "wave", "netrc", "fileinput")

SONDE = dedent(
    """
    import importlib.util
    import sys
    import types
    from pathlib import Path

    haus = Path(sys.argv[1]).resolve()

    # Anfangsstand sichern: das Haus darf spaeter NIRGENDWO stehen.
    anfang = list(sys.path)
    assert str(haus) not in anfang, sys.path

    # Das Haus in der Lage einer echten Installation: die Integration
    # liegt unter custom_components, der Kern IN ihr. Kein haigs an
    # der Wurzel, kein Eintrag auf dem Suchpfad -- genau hier muss die
    # Integration ohne jede Suche auskommen.
    wurzel = types.ModuleType("custom_components")
    wurzel.__path__ = [str(haus / "custom_components")]
    sys.modules["custom_components"] = wurzel

    datei = haus / "custom_components" / "haigs" / "__init__.py"
    spec = importlib.util.spec_from_file_location(
        "custom_components.haigs",
        datei,
        submodule_search_locations=[str(datei.parent)],
    )
    modul = importlib.util.module_from_spec(spec)
    sys.modules["custom_components.haigs"] = modul
    spec.loader.exec_module(modul)

    # Der Kern wurde gefunden -- als Unterpaket, aus demselben Ordner.
    kern = sys.modules.get("custom_components.haigs.core.forge")
    assert kern is not None, "Kern wurde nicht mitgeladen"
    assert str(haus) in str(kern.__file__), kern.__file__

    # Der Suchpfad blieb exakt unveraendert -- kein append, kein
    # insert, kein Kunststueck. Das ist die eigentliche Behauptung.
    assert sys.path == anfang, "Suchpfad wurde veraendert"

    # Der Giftbecher: stdlib-Module duerfen nicht aus dem Haus kommen.
    geprueft = 0
    for name in ("tarfile", "wave", "netrc", "fileinput"):
        if name in sys.modules:
            continue
        modul = importlib.import_module(name)
        assert str(haus) not in str(modul.__file__), modul.__file__
        print("unschaedlich:", name, modul.__file__)
        geprueft += 1
    assert geprueft >= 1, "keine Gift-Datei mehr zu pruefen"
    """
)


def haus_richten(tmp_path: Path) -> Path:
    """Ein Haus wie eine echte Installation: Integration, Kern inklusive."""
    haus = tmp_path / "haus"
    shutil.copytree(REPO / "custom_components", haus / "custom_components")
    assert not (REPO / "haigs").exists(), (
        "Kern liegt noch an der Wurzel -- das widerspricht der Form aus #11"
    )
    for name in GIFT_KANDIDATEN:
        (haus / f"{name}.py").write_text(
            'raise RuntimeError("Beschattung duerfte nie wirken: " + __file__)\n',
            encoding="utf-8",
        )
    return haus


async def test_kern_wird_ohne_jeden_suchpfad_gefunden(tmp_path: Path) -> None:
    """Form aus #11: kein sys.path-Griff, Kern aus dem eigenen Ordner."""
    haus = haus_richten(tmp_path)
    sonde = tmp_path / "sonde.py"
    sonde.write_text(SONDE, encoding="utf-8")

    umgebung = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    umgebung["PYTHONUTF8"] = "1"
    ergebnis = subprocess.run(
        [sys.executable, str(sonde), str(haus)],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
        env=umgebung,
        timeout=180,
        check=False,
    )
    assert ergebnis.returncode == 0, ergebnis.stdout + "\n" + ergebnis.stderr
