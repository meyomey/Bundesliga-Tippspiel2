/* Tipp-Optimizer-Engine: Dixon-Coles-Poisson + EP-Optimierung (4/3/2).
 *
 * 1:1 portiert aus dem Standalone-Tool "Bundesliga 4/3/2-Optimizer" v1.4
 * (Dixon-Coles-Korrekturfaktoren empirisch; Defaults hier, produktiv werden
 * sie serverseitig aus den Saisondaten der App-Datenbank gefittet).
 *
 * Bewusst ohne DOM-Zugriffe: laeuft im Browser (window.TOEngine) und in
 * Node (module.exports) – Regressionstests: tests/js/tip_optimizer_engine_test.js
 * (läuft in der CI, Job "JS-Engine-Tests (Node)").
 *
 * Neue Parameter gegenüber dem Standalone-Port:
 *   fitLambdas(target, ex, rho, prior, goalPrior)
 *     prior     = {lh, la, w} | null  – weicher Anker an Teamstärken aus der
 *                                       Saisondaten-DB (w = Gewicht; die UI
 *                                       setzt 0.15, damit der Markt-Fit das
 *                                       Hauptsignal bleibt)
 *     goalPrior = Zahl | null         – ligaübliche Torsumme (sonst 3,20)
 */
(function (root, factory) {
  var api = factory();
  root.TOEngine = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (typeof globalThis !== "undefined") globalThis.TOEngine = api;
})(typeof window !== "undefined" ? window : globalThis, function () {
  "use strict";

  var NMAX = 11;

  function fact(k) { var f = 1; for (var i = 2; i <= k; i++) f *= i; return f; }
  function poissonVec(l) {
    var v = new Array(NMAX + 1), e = Math.exp(-l);
    for (var k = 0; k <= NMAX; k++) v[k] = e * Math.pow(l, k) / fact(k);
    return v;
  }
  function buildMatrix(lh, la, rho0, rhoD, rho1) {
    var ph = poissonVec(lh), pa = poissonVec(la), M = [], s = 0;
    for (var i = 0; i <= NMAX; i++) { M.push(new Array(NMAX + 1));
      for (var j = 0; j <= NMAX; j++) {
        var x = ph[i] * pa[j];
        if (i === 0 && j === 0) x *= rho0;
        else if (i === 1 && j === 1) x *= rhoD;
        else if ((i === 1 && j === 0) || (i === 0 && j === 1)) x *= rho1;
        M[i][j] = x; s += x;
      } }
    for (var a = 0; a <= NMAX; a++) for (var b = 0; b <= NMAX; b++) M[a][b] /= s;
    return M;
  }
  function stats(M) {
    var p1 = 0, px = 0, p2 = 0, ou25 = 0, ou35 = 0, btts = 0;
    for (var i = 0; i <= NMAX; i++) for (var j = 0; j <= NMAX; j++) {
      var p = M[i][j];
      if (i > j) p1 += p; else if (i === j) px += p; else p2 += p;
      if (i + j > 2.5) ou25 += p; if (i + j > 3.5) ou35 += p;
      if (i > 0 && j > 0) btts += p;
    }
    return { p1: p1, px: px, p2: p2, ou25: ou25, ou35: ou35, btts: btts };
  }
  function tipPoints(h, a, th, ta) {
    if (h === th && a === ta) return 4;
    if ((h - a) === (th - ta)) return 3;
    var sA = (h > a) - (h < a), sT = (th > ta) - (th < ta);
    return sA === sT ? 2 : 0;
  }
  function analyse(M) {
    var ep = [], list = [];
    for (var th = 0; th <= 7; th++) { ep.push(new Array(8));
      for (var ta = 0; ta <= 7; ta++) {
        var s = 0;
        for (var i = 0; i <= NMAX; i++) for (var j = 0; j <= NMAX; j++) s += M[i][j] * tipPoints(i, j, th, ta);
        ep[th][ta] = s; list.push({ t: [th, ta], ep: s });
      } }
    list.sort(function (a, b) { return b.ep - a.ep; });
    var sc = [];
    for (var i2 = 0; i2 <= NMAX; i2++) for (var j2 = 0; j2 <= NMAX; j2++) sc.push({ t: [i2, j2], p: M[i2][j2] });
    sc.sort(function (a, b) { return b.p - a.p; });
    var best = list[0].t;
    var pGe2 = 0, pGe3 = 0, pEx = 0;
    for (var i3 = 0; i3 <= NMAX; i3++) for (var j3 = 0; j3 <= NMAX; j3++) {
      var pts = tipPoints(i3, j3, best[0], best[1]);
      if (pts >= 2) pGe2 += M[i3][j3]; if (pts >= 3) pGe3 += M[i3][j3]; if (pts === 4) pEx += M[i3][j3];
    }
    return { ep: ep, list: list, sc: sc, best: best, epBest: list[0].ep, epGap: list[0].ep - list[1].ep,
             pGe2: pGe2, pGe3: pGe3, pEx: pEx,
             topTips: list.slice(0, 3), topScores: sc.slice(0, 3), st: stats(M) };
  }
  function deMargin(o1, ox, o2, method) {
    var i1 = 1 / o1, ix = 1 / ox, i2 = 1 / o2;
    if (method === "prop") {
      var S = i1 + ix + i2;
      return [i1 / S, ix / S, i2 / S, 1];
    }
    // Power-Methode: p_i ∝ (1/o_i)^k, Summe = 1 – korrigiert den
    // Favorite-Longshot-Bias (Außenseiterquoten überzeichnen deren Wahrscheinlichkeit).
    var lo = 1, hi = 3;
    function sk(k) { return Math.pow(i1, k) + Math.pow(ix, k) + Math.pow(i2, k); }
    for (var it = 0; it < 60; it++) { var k = (lo + hi) / 2; if (sk(k) > 1) lo = k; else hi = k; }
    var kk = (lo + hi) / 2, SS = sk(kk);
    return [Math.pow(i1, kk) / SS, Math.pow(ix, kk) / SS, Math.pow(i2, kk) / SS, kk];
  }
  function fitLambdas(target, ex, rho, prior, goalPrior) {
    var gp = (typeof goalPrior === "number" && goalPrior > 0) ? goalPrior : 3.20;
    function obj(lh, la) {
      var st = stats(buildMatrix(lh, la, rho.r0, rho.rD, rho.r1));
      var e = Math.pow(st.p1 - target[0], 2) + Math.pow(st.px - target[1], 2) + Math.pow(st.p2 - target[2], 2);
      if (ex.ou25 != null) e += 0.3 * Math.pow(st.ou25 - ex.ou25, 2);
      if (ex.ou35 != null) e += 0.2 * Math.pow(st.ou35 - ex.ou35, 2);
      if (ex.btts != null) e += 0.2 * Math.pow(st.btts - ex.btts, 2);
      // Sanfter Prior auf die Torsumme, wenn keine Tor-Märkte vorliegen.
      // gp = ligauebliche Torsumme (serverseitig aus der Saisondaten-DB gefittet,
      // Fallback 3,20 = BL-Mittel 25/26).
      if (ex.ou25 == null && ex.ou35 == null)
        e += (ex.btts == null ? 0.05 : 0.015) * Math.pow(lh + la - gp, 2);
      // Weicher Anker an die Teamstaerken aus der Saisondaten-DB (prior =
      // {lh, la, w}): die Quoten bleiben das Hauptsignal, die Form stützt.
      if (prior && prior.lh != null)
        e += (prior.w || 0.25) * (Math.pow(lh - prior.lh, 2) + Math.pow(la - prior.la, 2));
      return e;
    }
    var bl = 0, bh = 0, bv = Infinity;
    var lh, la, v;
    for (lh = 0.05; lh <= 6.001; lh += 0.05)
      for (la = 0.05; la <= 6.001; la += 0.05) {
        v = obj(lh, la);
        if (v < bv) { bv = v; bl = lh; bh = la; }
      }
    for (lh = Math.max(0.05, bl - 0.06); lh <= bl + 0.061; lh += 0.005)
      for (la = Math.max(0.05, bh - 0.06); la <= bh + 0.061; la += 0.005) {
        v = obj(lh, la);
        if (v < bv) { bv = v; bl = lh; bh = la; }
      }
    return [bl, bh];
  }

  return { NMAX: NMAX, fact: fact, poissonVec: poissonVec, buildMatrix: buildMatrix,
           stats: stats, tipPoints: tipPoints, analyse: analyse, deMargin: deMargin,
           fitLambdas: fitLambdas };
});
