/* Regressionstests: Heute/Morgen-Tagesmarkierung ((85), static/js/dash_days.js).
 * Reiner Node-Lauf ohne DOM (CI-Job "JS-Engine-Tests (Node)").
 * Datumskonstruktion ueber lokale Kalendertage, damit der Test in jeder
 * Zeitzone identisch laeuft (Sandbox/CI = UTC, Dev = Berlin).
 */
"use strict";
const assert = require("assert");
const D = require("../../static/js/dash_days.js");

const now = new Date(2026, 8, 22, 15, 0); // 22.09.2026, 15:00 lokal

/* gleicher lokaler Kalendertag -> 'heute' (auch kurz vor Mitternacht) */
assert.strictEqual(D.tagesLabel(new Date(2026, 8, 22, 0, 5), now), "heute");
assert.strictEqual(D.tagesLabel(new Date(2026, 8, 22, 23, 30), now), "heute");

/* naechster lokaler Kalendertag -> 'morgen' (auch kurz nach Mitternacht) */
assert.strictEqual(D.tagesLabel(new Date(2026, 8, 23, 0, 30), now), "morgen");
assert.strictEqual(D.tagesLabel(new Date(2026, 8, 23, 23, 59), now), "morgen");

/* gestern / uebermorgen -> null (keine Markierung) */
assert.strictEqual(D.tagesLabel(new Date(2026, 8, 21, 12, 0), now), null);
assert.strictEqual(D.tagesLabel(new Date(2026, 8, 24, 12, 0), now), null);

/* Monatsgrenze: 29.09 -> 30.09 bleibt 'morgen', 30.09 bleibt 'heute' */
const sep30 = new Date(2026, 8, 30, 20, 0);
const nowSep29 = new Date(2026, 8, 29, 15, 0);
assert.strictEqual(D.tagesLabel(sep30, nowSep29), "morgen");
assert.strictEqual(D.tagesLabel(sep30, sep30), "heute");

/* ohne now -> Systemzeit (kein Crash, Rueckgabe aus der bekannten Menge) */
assert.ok(["heute", "morgen", null].includes(D.tagesLabel(new Date())));

/* Muell-Eingaben -> null (nie werfen) */
assert.strictEqual(D.tagesLabel(""), null);
assert.strictEqual(D.tagesLabel(null), null);
assert.strictEqual(D.tagesLabel("Quatsch-mit-Soße"), null);

/* ISO-String wird akzeptiert (Zeitzone-abhaengiger Kalendertag ist gewollt:
 * Bewertung bewusst in Betrachter-Zeit, siehe Modul-Kopf) */
assert.strictEqual(
  ["heute", "morgen", null].includes(D.tagesLabel("2026-09-22T20:00:00Z", now)),
  true
);

console.log("dash_days_test: alle Assertions gruen");
