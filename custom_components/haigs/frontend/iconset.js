/**
 * HAIGS Iconset -- der Tanuki von GitLab, monochrom.
 *
 * Home Assistants Frontend kennt eigene Zeichenkollektionen: alles vor
 * dem Doppelpunkt einer Icon-Adresse nennt die Kollektion, alles dahinter
 * das Zeichen. ``mdi:hexagon-multiple`` ist MDI; ``haigs:tanuki``
 * ist dieses Hier.
 *
 * Das Original ist das Markenbild von GitLab (vier farbige Pfade, vom
 * Imker-Server geholt). Die Seitenleiste zeichnet aber nur EINEN Pfad
 * in der Schreibfarbe -- darum steht hier die Silhouette, der große
 * Körperrand des Tanuki, und die Wange bleibt Wange: erkennbar bleibt
 * das Tier auch einfarbig.
 *
 * Die Datei laeuft als ES-Modul auf JEDER Seite des Frontends (Angemeldet
 * ueber ``add_extra_js_url`` in ``frontend.py``) -- die Seitenleiste
 * braucht das Zeichen schon, bevor jemand das Panel oeffnet.
 */

const TANUKI_SILHOUETTE =
  "m49.014 19-.067-.18-6.784-17.696a1.792 1.792 0 0 0-3.389.182l-4.579 14.02H15.651" +
  "l-4.58-14.02a1.795 1.795 0 0 0-3.388-.182l-6.78 17.7-.071.175" +
  "A12.595 12.595 0 0 0 5.01 33.556l.026.02.057.044 10.32 7.734 5.12 3.87 3.11 2.351" +
  "a2.102 2.102 0 0 0 2.535 0l3.11-2.352 5.12-3.869 10.394-7.779.029-.022" +
  "a12.595 12.595 0 0 0 4.182-14.554Z";

/** viewBox des Originalzeichens (0 0 50 48) -- mitgeliefert, passt sonst nicht. */
const TANUKI_VIEWBOX = "0 0 50 48";

window.customIconsets = window.customIconsets || {};
window.customIconsets["haigs"] = (name) => {
  if (name !== "tanuki") {
    return null;
  }
  return { path: TANUKI_SILHOUETTE, viewBox: TANUKI_VIEWBOX };
};
