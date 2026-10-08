/**
 * HAIGS Iconset -- die Fuchskralle, monochrom.
 *
 * Home Assistants Frontend kennt eigene Zeichenkollektionen: alles vor
 * dem Doppelpunkt einer Icon-Adresse nennt die Kollektion, alles dahinter
 * das Zeichen. ``mdi:hexagon-multiple`` ist MDI; ``haigs:kralle``
 * ist dieses Hier.
 *
 * Drei Sichelkrallen wie die des Fuchses im Logo, ein einziger Pfad in
 * der Schreibfarbe der Seitenleiste. Eigenes Zeichen: bis 0.6.2 stand
 * hier der Tanuki von GitLab, und der ist GitLabs Markenzeichen.
 * ``haigs:tanuki`` liefert weiter die Kralle, damit alte Verweise nicht
 * ins Leere zeigen.
 *
 * Die Datei laeuft als ES-Modul auf JEDER Seite des Frontends (Angemeldet
 * ueber ``add_extra_js_url`` in ``frontend.py``) -- die Seitenleiste
 * braucht das Zeichen schon, bevor jemand das Panel oeffnet.
 */

const KRALLE =
  "M3.50 6.39C1.50 11.05 2.69 16.42 6.05 18.16C4.06 15.23 4.97 11.44 6.75 7.45Q5.44 5.96 3.50 6.39ZM8.58 5.84C7.85 11.58 10.85 17.09 15.08 17.95C11.97 15.36 11.77 10.92 12.48 5.98Q10.57 4.76 8.58 5.84ZM14.11 7.50C14.87 12.51 18.73 16.43 22.50 16.13C19.26 14.70 18.02 11.01 17.42 6.68Q15.52 6.11 14.11 7.50Z";

window.customIconsets = window.customIconsets || {};
window.customIconsets["haigs"] = (name) => {
  if (name !== "kralle" && name !== "tanuki") {
    return null;
  }
  return { path: KRALLE, viewBox: "0 0 24 24" };
};
