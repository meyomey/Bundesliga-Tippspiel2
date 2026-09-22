/* (85) Heute/Morgen-Tagesmarkierung für das Dashboard.
 *
 * Reine Logik ohne DOM — bewusst in einer eigenen, Node-testbaren Datei
 * (CI: node tests/js/dash_days_test.js). Die Bewertung passiert in der
 * LOKALEN Zeit des Betrachters — exakt dieselbe Uhr, die auch die
 * Anstoßzeiten anzeigt (data-utc-Konvertierung). Keine Schätzung:
 * ein Kalendertagvergleich, sonst nichts.
 */
"use strict";
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();          // Node (Tests/CI)
  } else {
    root.DashDays = factory();           // Browser (window.DashDays)
    /* (88) Selbst-Init: wir auf jeder Seite automatisch — Spielplan,
     * Schnelltipp und Dashboard brauchen keine eigene Verdrahtung mehr. */
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", function () { root.DashDays.anwenden(); });
    } else {
      root.DashDays.anwenden();
    }
  }
})(typeof self !== "undefined" ? self : this, function () {
  function tagesLabel(utcStr, now) {
    if (!utcStr) return null;
    const d = new Date(utcStr);
    if (isNaN(d.getTime())) return null;
    const ref = now ? new Date(now) : new Date();
    if (isNaN(ref.getTime())) return null;
    // Lokale Kalendertage (Mitternacht) vergleichen — DST-fest
    const tag = new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
    const heut = new Date(ref.getFullYear(), ref.getMonth(), ref.getDate()).getTime();
    const diff = Math.round((tag - heut) / 86400000);
    if (diff === 0) return "heute";
    if (diff === 1) return "morgen";
    return null;
  }
  /* Wendet ist-heute/ist-morgen auf alle [data-utc]-Elemente an und
   * fuellt die MD-Trenner-Chips (.md-sep-when). Ein Aufruf pro Seite —
   * die Initialisierung macht der Browser-Zweig unten von selbst. */
  function anwenden(bereich) {
    var elemente = (bereich || document).querySelectorAll("[data-utc]");
    for (var i = 0; i < elemente.length; i++) {
      var el = elemente[i];
      var label = tagesLabel(el.dataset ? el.dataset.utc : el.getAttribute("data-utc"));
      if (!label) continue;
      el.classList.add("ist-" + label);
      if (el.classList.contains("md-sep-when")) el.textContent = label;
    }
  }
  return { tagesLabel: tagesLabel, anwenden: anwenden };
});
