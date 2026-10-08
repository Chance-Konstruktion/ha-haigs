/**
 * HAIGS Iconset -- der Fuchskopf (Kitsune), monochrom.
 *
 * Home Assistants Frontend kennt eigene Zeichenkollektionen: alles vor
 * dem Doppelpunkt einer Icon-Adresse nennt die Kollektion, alles dahinter
 * das Zeichen. ``mdi:hexagon-multiple`` ist MDI; ``haigs:fuchs``
 * ist dieses Hier.
 *
 * Hohe Spitzohren mit Ohrmuschel, schmale Schnauze -- der Fuchs aus dem
 * Logo, ein einziger Pfad in der Schreibfarbe der Seitenleiste. Eigenes Zeichen: bis 0.6.2 stand
 * hier der Tanuki von GitLab, und der ist GitLabs Markenzeichen.
 * ``haigs:tanuki`` und ``haigs:kralle`` liefern weiter den Fuchs, damit alte Verweise nicht
 * ins Leere zeigen.
 *
 * Die Datei laeuft als ES-Modul auf JEDER Seite des Frontends (Angemeldet
 * ueber ``add_extra_js_url`` in ``frontend.py``) -- die Seitenleiste
 * braucht das Zeichen schon, bevor jemand das Panel oeffnet.
 */

const FUCHS =
  "M4.2 0.8L9 6.6L15 6.6L19.8 0.8L20.8 9.6L22.6 13L17.6 15.2L13.4 21.6L12 22.6L10.6 21.6L6.4 15.2L1.4 13L3.2 9.6ZM5.6 9L8 7.4L5 3.6ZM19 3.6L16 7.4L18.4 9ZM7.6 13L9.4 13.7L10.2 12.8L7 11.6ZM17 11.6L13.8 12.8L14.6 13.7L16.4 13Z";

window.customIconsets = window.customIconsets || {};
window.customIconsets["haigs"] = (name) => {
  if (name !== "fuchs" && name !== "kralle" && name !== "tanuki") {
    return null;
  }
  return { path: FUCHS, viewBox: "0 0 24 24" };
};
