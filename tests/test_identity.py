"""Die Identitaet ist der Kern: sie entscheidet, was doppelt ist und was nicht."""

import pytest
from haigs.core.identity import (
    GITHUB,
    GITLAB,
    RepositoryIdentity,
    UngueltigeIdentitaet,
    strip_suffix,
)


def gitlab_repo(**rest):
    daten = {
        "provider": GITLAB,
        "host": "gitlab.example.net",
        "provider_id": "789012",
        "full_name": "foo/bar",
    }
    daten.update(rest)
    return RepositoryIdentity(**daten)


def test_gitlab_bekommt_das_suffix():
    assert gitlab_repo().display_full_name == "foo/bar*lab"


def test_github_bleibt_unveraendert():
    ident = RepositoryIdentity(GITHUB, "github.com", "123456", "foo/bar")
    assert ident.display_full_name == "foo/bar"
    assert ident.uid == "github:123456"


def test_gleicher_name_verschiedene_anbieter_sind_zwei_repos():
    github = RepositoryIdentity(GITHUB, "github.com", "123456", "foo/bar")
    gitlab = gitlab_repo()
    assert github.uid != gitlab.uid
    assert github.display_full_name != gitlab.display_full_name


def test_gleiche_id_auf_zwei_instanzen_bleibt_getrennt():
    eine = gitlab_repo(host="gitlab.com")
    andere = gitlab_repo(host="gitlab.example.net")
    assert eine.uid == andere.uid, "die uid kennt den Host bewusst nicht"
    assert eine.storage_key != andere.storage_key


def test_umbenennen_aendert_die_identitaet_nicht():
    vorher = gitlab_repo(full_name="foo/bar")
    nachher = gitlab_repo(full_name="foo/besser")
    assert vorher.uid == nachher.uid


def test_suffix_wird_fuer_abfragen_wieder_entfernt():
    assert strip_suffix("foo/bar*lab") == "foo/bar"
    assert strip_suffix("foo/bar") == "foo/bar"


def test_ein_echtes_repo_namens_etwas_lab_wird_nicht_verwechselt():
    # Ein GitHub-Repo darf "lab" heissen, ohne als GitLab-Eintrag zu gelten.
    ident = RepositoryIdentity(GITHUB, "github.com", "1", "foo/bar-lab")
    assert ident.display_full_name == "foo/bar-lab"
    assert ident.provider == GITHUB


@pytest.mark.parametrize(
    "kaputt",
    [
        {"full_name": "ohne-schraegstrich"},
        {"provider_id": ""},
        {"host": "  "},
        {"provider": "bitbucket"},
    ],
)
def test_unvollstaendige_angaben_fliegen_auf(kaputt):
    with pytest.raises(UngueltigeIdentitaet):
        gitlab_repo(**kaputt)


def test_hin_und_zurueck():
    ident = gitlab_repo()
    assert RepositoryIdentity.from_dict(ident.as_dict()) == ident
