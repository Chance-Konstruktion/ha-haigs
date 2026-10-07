"""Gemeinsame Ausstattung der Kern-Suite (``tests/``).

Diese Bahn laeuft ohne Home-Assistant-Installation -- schnell und
trocken. Der Kern wird dazu von ``tests/kern_laden`` unter ``haigs``
angemeldet; die Begruendung steht dort.

Die Home-Assistant-Bahn (``tests_ha/``) hat ihre eigene Ausstattung in
``tests_ha/conftest.py`` und fasst diese Datei nicht an.
"""

from __future__ import annotations

import tests.kern_laden  # noqa: F401 -- Anmeldung als Nebenwirkung
