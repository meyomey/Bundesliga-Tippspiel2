/* (93) Theme-Engine — API: { initialTheme, anwenden, umschalten, SCHLUESSEL }
 * Konsolidiert mit dem Alt-System: Speicher-Key ist der historische 'theme'
 * (app.js), die Buttons in base.html (Mobile-Menue + Desktop-User-Area)
 * rufen weiter toggleTheme() -> Delegat -> WTTheme.umschalten(). Das
 * No-Flash-Skript im base.html-Head liest denselben Key vor dem ersten
 * Paint. Node-Export fuer tests/js/theme_test.js. */
(function (global) {
  'use strict';

  var SCHLUESSEL = 'theme';

  function initialTheme() {
    try {
      var t = global.localStorage.getItem(SCHLUESSEL);
      return (t === 'light' || t === 'dark') ? t : 'dark';
    } catch (e) { return 'dark'; }
  }

  function anwenden(mode) {
    var theme = (mode === 'light') ? 'light' : 'dark';
    global.document.documentElement.setAttribute('data-theme', theme);
    return theme;
  }

  function umschalten() {
    var aktuell = global.document.documentElement.getAttribute('data-theme');
    var next = (aktuell === 'light') ? 'dark' : 'light';
    anwenden(next);
    try { global.localStorage.setItem(SCHLUESSEL, next); } catch (e) { /* Privatmodus: nur Sitzung */ }
    return next;
  }

  var api = { initialTheme: initialTheme, anwenden: anwenden, umschalten: umschalten, SCHLUESSEL: SCHLUESSEL };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  } else {
    global.WTTheme = api;
    var boot = function () { anwenden(initialTheme()); };
    if (global.document.readyState === 'loading') {
      global.document.addEventListener('DOMContentLoaded', boot);
    } else {
      boot();
    }
  }
})(typeof window !== 'undefined' ? window : globalThis);
