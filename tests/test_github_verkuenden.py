"""Der GitHub-Auftritt: der Pruefstand fuer den zweiten Release-Weg.

GitHub ist die Ladentheke -- HACS installiert nur von dort und nur aus
Releases. Die Vorlage in ``claude/ci-vorlagen`` legt den Eintrag an,
haengt aber nichts daran; beide READMEs schicken die Leute aber zu
``haigs-vX.Y.Z.zip``. Hier wird bewiesen:

* **Was auf die Reise geht** -- Eintrag und Anhang, die Adresse aus der
  Antwort statt einer geratenen, die Bytes des gebauten ZIP.
* **Was nicht passiert** -- ohne Token geht nichts ins Netz und nichts
  wird rot; ein Release, den es drueben schon gibt, wird nicht ersetzt;
  ein Anhang, der schon haengt, wird nicht verdoppelt.
* **Was der Fehlerfall sagt** -- kein ZIP oder mehrere: beim Namen
  nennen, nichts eintragen.

Der Transport ist die Naht: die Tests legen eine Attrappe hinein, es
geht nie ein Byte ins Netz.
"""

import pytest

from auslieferung.github_verkuenden import GithubFehler, main


class Attrappe:
    """Zeichnet jeden Aufruf auf und spielt vorbereitete Antworten ein."""

    def __init__(self, antworten):
        self.aufrufe = []
        self.antworten = list(antworten)

    def __call__(self, adresse, token, daten=None, art="application/json", methode="GET"):
        self.aufrufe.append(
            {
                "adresse": adresse,
                "token": token,
                "daten": daten,
                "art": art,
                "methode": methode,
            }
        )
        antwort = self.antworten.pop(0)
        if isinstance(antwort, Exception):
            raise antwort
        return antwort


def _fehler(code: int, koerper: str = "{}") -> GithubFehler:
    """Was der Transport aus einer Absage macht -- kein Netz-Modul noetig."""
    return GithubFehler(code, koerper)


@pytest.fixture
def bahn(tmp_path, monkeypatch):
    """Ein ausgeliefertes dist/ mit genau einem ZIP, wie die CI es baut."""
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "haigs-v0.3.0.zip").write_bytes(b"PK\x03\x04-die-bytes")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CI_COMMIT_TAG", "v0.3.0")
    monkeypatch.setenv("CI_PROJECT_NAME", "haigs")
    monkeypatch.setenv("CI_PROJECT_URL", "https://forge.example/x/haigs")
    monkeypatch.setenv("GITHUB_TOKEN", "geheim")
    monkeypatch.delenv("GITHUB_REPO", raising=False)
    return tmp_path


def test_ohne_token_geschieht_nichts(bahn, monkeypatch, capsys):
    """Kein Token ist kein Fehler -- aber es wird gesagt, was ausfaellt."""
    monkeypatch.setenv("GITHUB_TOKEN", "")
    attrappe = Attrappe([])

    assert main(attrappe) == 0
    assert attrappe.aufrufe == []
    assert "sehen diesen Stand nicht" in capsys.readouterr().out


def test_eintrag_und_anhang(bahn):
    """Der ganze Weg: nachsehen, eintragen, ZIP anhaengen."""
    attrappe = Attrappe(
        [
            _fehler(404),
            {
                "html_url": "https://github.com/Chance-Konstruktion/haigs/releases/tag/v0.3.0",
                "upload_url": "https://uploads.github.com/repos/x/haigs/releases/7/assets{?name,label}",
                "assets": [],
            },
            {"browser_download_url": "https://github.com/x/haigs-v0.3.0.zip"},
        ]
    )

    assert main(attrappe) == 0

    nachsehen, eintragen, anhaengen = attrappe.aufrufe
    assert nachsehen["adresse"].endswith(
        "/repos/Chance-Konstruktion/haigs/releases/tags/v0.3.0"
    )
    assert eintragen["methode"] == "POST"
    assert b'"tag_name": "v0.3.0"' in eintragen["daten"]
    # Die Upload-Adresse kommt aus der Antwort, nicht aus einer Annahme --
    # die Vorlage "{?name,label}" faellt weg, der Dateiname wird angehaengt.
    assert anhaengen["adresse"] == (
        "https://uploads.github.com/repos/x/haigs/releases/7/assets?name=haigs-v0.3.0.zip"
    )
    assert anhaengen["art"] == "application/zip"
    assert anhaengen["daten"] == b"PK\x03\x04-die-bytes"


def test_vorhandener_release_wird_nicht_ersetzt(bahn, capsys):
    """Derselbe Tag zweimal ist kein Schaden -- aber auch kein Ueberschreiben."""
    attrappe = Attrappe(
        [
            {
                "upload_url": "https://uploads.github.com/r/1/assets{?name,label}",
                "assets": [],
            },
            {"browser_download_url": "https://github.com/x/haigs-v0.3.0.zip"},
        ]
    )

    assert main(attrappe) == 0
    assert [a["methode"] for a in attrappe.aufrufe] == ["GET", "POST"]
    assert "gibt es auf GitHub bereits" in capsys.readouterr().out


def test_vorhandener_anhang_wird_nicht_verdoppelt(bahn, capsys):
    attrappe = Attrappe(
        [
            {
                "upload_url": "https://uploads.github.com/r/1/assets{?name,label}",
                "assets": [{"name": "haigs-v0.3.0.zip"}],
            },
        ]
    )

    assert main(attrappe) == 0
    assert len(attrappe.aufrufe) == 1
    assert "haengt schon daran" in capsys.readouterr().out


@pytest.mark.parametrize("dateien", [[], ["eins.zip", "zwei.zip"]])
def test_ohne_genau_ein_zip_wird_nichts_eingetragen(bahn, dateien, capsys):
    """Was nicht eindeutig ist, wird nicht veroeffentlicht."""
    for alt in (bahn / "dist").glob("*.zip"):
        alt.unlink()
    for name in dateien:
        (bahn / "dist" / name).write_bytes(b"x")
    attrappe = Attrappe([])

    assert main(attrappe) == 1
    assert attrappe.aufrufe == []
    assert "genau ein ZIP" in capsys.readouterr().err


def test_abgelehnter_eintrag_faellt_auf(bahn, capsys):
    attrappe = Attrappe(
        [_fehler(404), _fehler(403, '{"message":"Resource not accessible"}')]
    )

    assert main(attrappe) == 1
    assert "GitHub antwortet 403" in capsys.readouterr().err


def test_github_repo_sticht_den_projektnamen(bahn, monkeypatch):
    """Drueben heisst es anders -- das GitLab-Projekt wird nicht umbenannt.

    Das Projekt heisst hier `haigs`, auf GitHub `ha-haigs` (die
    ha-Familie: ha-powerline, ha-kontinuum, ...). GITHUB_REPO ist die
    einzige Stelle, an der dieser Unterschied steht -- ohne sie liefe
    der Release gegen eine Adresse, die es drueben nicht gibt.
    """
    monkeypatch.setenv("GITHUB_REPO", "ha-haigs")
    attrappe = Attrappe(
        [
            {
                "upload_url": "https://uploads.github.com/r/1/assets{?name,label}",
                "assets": [],
            },
            {"browser_download_url": "https://github.com/x/haigs-v0.3.0.zip"},
        ]
    )

    assert main(attrappe) == 0
    assert attrappe.aufrufe[0]["adresse"].endswith(
        "/repos/Chance-Konstruktion/ha-haigs/releases/tags/v0.3.0"
    )
