"""Kern von HAIGS: reines Python, ohne Home-Assistant-Abhaengigkeit.

Alles in diesem Paket laesst sich ohne laufendes Home Assistant testen.
Die Home-Assistant-Anbindung ist das Elternpaket --
``custom_components/haigs`` -- und reicht ihre Sitzung herein.
Der Kern wohnt hier seit der Form-Entscheidung zu #11: eine Adresse,
kein Suchpfad-Kunststueck, keine zweite Kopie.
"""
