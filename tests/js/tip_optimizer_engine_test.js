/* Regressionstests für die Tipp-Optimizer-Engine (static/js/to_engine.js).
 *
 * Reiner Node-Lauf ohne Abhängigkeiten und ohne DOM:
 *   node tests/js/tip_optimizer_engine_test.js
 * Läuft zusätzlich in der GitHub-CI (Job "JS-Engine-Tests (Node)").
 */
"use strict";
const assert = require("assert");
const E = require("../../static/js/to_engine.js");

function sumMatrix(M) {
  let s = 0;
  for (let i = 0; i <= E.NMAX; i++) for (let j = 0; j <= E.NMAX; j++) s += M[i][j];
  return s;
}
const NOEX = { ou25: null, ou35: null, btts: null };
const RHO1 = { r0: 1, rD: 1, r1: 1 };

/* 1. Tipp-Punkte: exakt die App-Regel 4/3/2/0.
 *    4 = exakter Treffer, 3 = gleicher Torsaldo, 2 = gleiche Richtung, 0 = Fehlanzeige. */
assert.strictEqual(E.tipPoints(2, 1, 2, 1), 4, "exakter Treffer = 4 P");
assert.strictEqual(E.tipPoints(0, 0, 0, 0), 4, "0:0 exakt = 4 P");
assert.strictEqual(E.tipPoints(3, 2, 2, 1), 3, "gleicher Saldo (+1) = 3 P");
assert.strictEqual(E.tipPoints(2, 2, 1, 1), 3, "beide Remis = 3 P");
assert.strictEqual(E.tipPoints(3, 1, 2, 1), 2, "gleiche Richtung, anderer Saldo = 2 P");
assert.strictEqual(E.tipPoints(1, 3, 2, 1), 0, "andere Richtung = 0 P");
assert.strictEqual(E.tipPoints(1, 0, 0, 1), 0, "Heim vs. Gast = 0 P");

/* 2. Ergebnis-Matrix: Wahrscheinlichkeitsverteilung (Summe 1) und
 *    Unabhängigkeit ohne DC-Faktoren. */
const M = E.buildMatrix(1.5, 1.2, 1, 1, 1);
assert.ok(Math.abs(sumMatrix(M) - 1) < 1e-9, "Matrix summiert zu 1");
// (Toleranz 1e-5: buildMatrix normalisiert auf die TRUNKIERTEN Poisson-
// Vektoren; der Restschweif jenseits NMAX=11 ist ~1e-6, nicht exakt 0.)
const pv = E.poissonVec(1.5)[2] * E.poissonVec(1.2)[1];
assert.ok(Math.abs(M[2][1] - pv) < 1e-5, "ohne DC-Faktoren: unabhängiges Poisson");

/* 3. Dixon-Coles-Faktoren verschieben die Niedrigtor-Zellen:
 *    rho0 > 1 macht 0:0 teurer (relativ), rhoD > 1 macht 1:1 teurer. */
const MDC = E.buildMatrix(1.5, 1.2, 1.3, 1.2, 0.8);
assert.ok(MDC[0][0] > M[0][0], "rho0>1 erhöht P(0:0) relativ");
assert.ok(MDC[1][1] > M[1][1], "rhoD>1 erhöht P(1:1) relativ");
assert.ok(MDC[1][0] < M[1][0], "rho1<1 senkt P(1:0) relativ");
assert.ok(Math.abs(sumMatrix(MDC) - 1) < 1e-9, "DC-Matrix summiert zu 1");

/* 4. Markt-Statistik: 1/X/2-Teile summieren zu 1, Tor-Märkte im (0,1). */
const st = E.stats(M);
assert.ok(Math.abs(st.p1 + st.px + st.p2 - 1) < 1e-9, "p1+px+p2 = 1");
assert.ok(st.ou25 > 0 && st.ou25 < 1, "ou25 im (0,1)");
assert.ok(st.btts > 0 && st.btts < 1, "btts im (0,1)");
assert.ok(st.ou35 < st.ou25, "P(>3,5) < P(>2,5)");

/* 5. Marge entfernen: prop = klassische Normalisierung der Implied Probs,
 *    power = Favorite-Longshot-Korrektur (k>1, Favorit gewinnt). */
const i1 = 1 / 1.9, ix = 1 / 3.6, i2 = 1 / 3.4, S = i1 + ix + i2;
const dp = E.deMargin(1.9, 3.6, 3.4, "prop");
assert.ok(Math.abs(dp[0] + dp[1] + dp[2] - 1) < 1e-9, "prop summiert zu 1");
assert.ok(Math.abs(dp[0] - i1 / S) < 1e-9, "prop: p ∝ 1/quote");
const dpo = E.deMargin(1.9, 3.6, 3.4, "power");
assert.ok(Math.abs(dpo[0] + dpo[1] + dpo[2] - 1) < 1e-9, "power summiert zu 1");
assert.ok(dpo[3] > 1 && dpo[3] < 3, "power-Exponent k im (1,3)");
assert.ok(dpo[0] > dp[0] + 1e-6, "power hebt den Favoriten über prop");
assert.ok(dpo[2] < dp[2], "power drückt den Longshot unter prop");

/* 6. Lambda-Fit: ein Ziel, das ein Poisson-Paar selbst erzeugt, wird
 *    wiederhergestellt (wenn der Torsumme-Prior neutral gewählt ist).
 *    Hinweis: Nicht JEDES 1X2-Ziel ist exakt erreichbar – unabhängiges
 *    Poisson + DC-Faktoren ist ein Modell mit 2 Freiheitsgraden; z. B.
 *    (0.55, 0.25, 0.20) erreicht px maximal ~0.22. Deshalb hier ein
 *    modellintern erzeugtes Ziel. */
const ref = E.stats(E.buildMatrix(1.8, 1.0, 1, 1, 1));
const fit1 = E.fitLambdas([ref.p1, ref.px, ref.p2], NOEX, RHO1, null, 2.8);
const st1 = E.stats(E.buildMatrix(fit1[0], fit1[1], 1, 1, 1));
assert.ok(Math.abs(st1.p1 - ref.p1) < 0.01, "Fit stellt p1 wieder her");
assert.ok(Math.abs(st1.px - ref.px) < 0.01, "Fit stellt px wieder her");
assert.ok(Math.abs(st1.p2 - ref.p2) < 0.01, "Fit stellt p2 wieder her");

/* 6b. Torsumme-Prior wirkt: höherer Prior -> höhere λ-Summe. */
const fLow = E.fitLambdas([ref.p1, ref.px, ref.p2], NOEX, RHO1, null, 2.3);
const fHigh = E.fitLambdas([ref.p1, ref.px, ref.p2], NOEX, RHO1, null, 4.2);
assert.ok(fLow[0] + fLow[1] < fit1[0] + fit1[1] - 0.1, "niedrigerer Torsumme-Prior senkt λ-Summe");
assert.ok(fHigh[0] + fHigh[1] > fit1[0] + fit1[1] + 0.5, "höherer Torsumme-Prior hebt λ-Summe");

/* 7. Lambda-Fit mit Teamstärken-Prior: zieht das Ergebnis Richtung Prior
 *    (weich: das Markt-Ziel bleibt das Hauptsignal). */
const tm = [0.50, 0.25, 0.25];
const fitNo = E.fitLambdas(tm, NOEX, RHO1, null, 3.2);
const fit2 = E.fitLambdas(tm, NOEX, RHO1, { lh: 2.6, la: 0.5, w: 0.15 }, 3.2);
assert.ok(fit2[0] > fitNo[0] + 0.1, "starker Heim-Prior hebt λ Heim");
assert.ok(fit2[1] < fitNo[1] - 0.1, "schwacher Gast-Prior drückt λ Gast");
const st2 = E.stats(E.buildMatrix(fit2[0], fit2[1], 1, 1, 1));
assert.ok(Math.abs(st2.p1 - 0.50) < 0.25, "Prior ist weich: Markt bleibt Hauptsignal");

/* 8. Analyse: EP des besten Tipps stimmt mit der Brutto-Summe überein,
 *    Sicherkeits-Flags sind konsistent, Top-Listen sind sortiert. */
const A = E.analyse(E.buildMatrix(2.0, 1.0, 1.1, 1.1, 0.9));
const Mx = E.buildMatrix(2.0, 1.0, 1.1, 1.1, 0.9);
let manual = 0;
for (let i = 0; i <= E.NMAX; i++) for (let j = 0; j <= E.NMAX; j++)
  manual += Mx[i][j] * E.tipPoints(i, j, A.best[0], A.best[1]);
assert.ok(Math.abs(manual - A.epBest) < 1e-9, "epBest = Brutto-EP des Tipps");
assert.ok(A.pGe2 >= A.pGe3 - 1e-9 && A.pGe3 >= A.pEx - 1e-9, "P(≥2) ≥ P(≥3) ≥ P(exakt)");
assert.ok(A.epGap >= 0, "Abstand zum Zweitbesten ≥ 0");
for (let k = 1; k < A.topTips.length; k++)
  assert.ok(A.topTips[k - 1].ep >= A.topTips[k].ep - 1e-12, "Top-Tipps absteigend");
for (let k = 1; k < A.topScores.length; k++)
  assert.ok(A.topScores[k - 1].p >= A.topScores[k].p - 1e-12, "Top-Ergebnisse absteigend");

/* 9. Robustheit: extreme λ laufen durch, ohne NaN. */
const Mext = E.buildMatrix(6.0, 0.15, 1, 1, 1);
assert.ok(isFinite(sumMatrix(Mext)) && Math.abs(sumMatrix(Mext) - 1) < 1e-9, "extreme λ OK");

console.log("ENGINE-TESTS OK (9 Bereiche, alle Assertions bestanden)");
