/* Tipp-Optimizer (Admin) – UI für die Dixon-Coles-EP-Optimierung (4/3/2).
 *
 * Die Engine liegt in static/js/to_engine.js (TOEngine, 1:1-Port des
 * Standalone-Tools v1.4, getest via tests/js/tip_optimizer_engine_test.js).
 * Läuft komplett client-seitig; die App liefert die Ansetzungen aus der DB,
 * (optional) die Online-Quoten über den Server-Proxy /admin/tip-optimizer/odds
 * und die Saisondaten-Anker (Teamstärken-λ, Dixon-Coles-Faktoren, Torsumme)
 * in der #to-config-Insel – serverseitig aus der App-Datenbank gefittet.
 *
 * Eingaben und Ergebnisse bleiben je Spieltag im localStorage (Key to_md_<N>),
 * damit ein Neuladen oder Matchday-Wechsel nichts wegwirft.
 */
(function () {
  "use strict";

  // Engine (Dixon-Coles + EP-Optimierung) aus to_engine.js (1:1-Port,
  // server-unabhängig getestet in der CI).
  var NMAX = TOEngine.NMAX;
  var fact = TOEngine.fact, poissonVec = TOEngine.poissonVec,
      buildMatrix = TOEngine.buildMatrix, stats = TOEngine.stats,
      tipPoints = TOEngine.tipPoints, analyse = TOEngine.analyse,
      deMargin = TOEngine.deMargin, fitLambdas = TOEngine.fitLambdas;

  var CFG = { md: 0, season: "", has_key: false,
              rho: null, goal_prior: null, priors: null };
  var CONFIG_ISLAND = document.getElementById("to-config");
  if (CONFIG_ISLAND) {
    try {
      var parsed = JSON.parse(CONFIG_ISLAND.textContent || "{}");
      if (parsed && typeof parsed === "object") CFG = parsed;
    } catch (e) { /* Konfiguration fehlt -> Defaults */ }
  }
  var STORE_KEY = "to_" + (CFG.season || "x") + "_md_" + CFG.md;
  var cards = Array.prototype.slice.call(document.querySelectorAll(".to-card"));
  var lastTips = [];
  // Vollstaendige Modell-Ausgaben des letzten Recalc (pro Karte, null wenn
  // unvollstaendig) – Basis fuer "Vorhersage speichern" (Modellguete).
  var lastFull = [];
  var foldInitialized = false; // Quoten-Fold: Auto-Regel nur beim ersten Rechenlauf

  function $(s, root) { return (root || document).querySelector(s); }
  function fmt(x, d) { return x.toFixed(d == null ? 2 : d).replace(".", ","); }
  function pct(x) { return Math.round(x * 100) + " %"; }
  function num(v) {
    if (v == null || v === "") return null;
    var x = parseFloat(String(v).replace(",", "."));
    return isFinite(x) && x > 1 ? x : null;
  }
  function clampN(v, min, max) {
    if (v == null || v === "") return 0;
    var x = parseFloat(String(v).replace(",", "."));
    if (!isFinite(x)) return 0;
    return Math.max(min, Math.min(max, x));
  }
  function esc(s) { return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;"); }
  function namesMatch(a, b) {
    if (!a || !b) return false;
    var ABBR = { "bor": "borussia", "mg": "mönchengladbach", "mgladbach": "mönchengladbach" };
    function norm(s) {
      return s.toLowerCase().replace(/\./g, " ").split(/[\s\-]+/)
        .map(function (t) { return ABBR.hasOwnProperty(t) ? ABBR[t] : t; }).filter(Boolean).join(" ").trim();
    }
    a = norm(a); b = norm(b);
    return a === b || (a.indexOf(b) >= 0 && b.length >= 4) || (b.indexOf(a) >= 0 && a.length >= 4);
  }

  function rho() {
    function g(id, lo, hi, dflt) {
      var el = document.getElementById(id);
      if (!el) return dflt;
      var v = num(el.value);
      if (v == null) return dflt;
      return Math.min(hi, Math.max(lo, v));
    }
    return { r0: g("to-rho0", 0.7, 1.6, 1.00), rD: g("to-rhoD", 0.7, 1.6, 1.09), r1: g("to-rho1", 0.5, 1.4, 0.97) };
  }
  function marginMethod() {
    var el = document.getElementById("to-margin");
    return el && el.value === "prop" ? "prop" : "power";
  }
  function confidence(pGe2) {
    if (pGe2 >= 0.70) return ["hoch", "b-hoch"];
    if (pGe2 >= 0.40) return ["mittel", "b-mittel"];
    return ["niedrig", "b-niedrig"];
  }
  // Ligaübliche Torsumme: serverseitig aus den Saisondaten gefittet, sonst
  // der Standalone-Default 3,20 (BL-Mittel 25/26).
  var GOAL_PRIOR = (typeof CFG.goal_prior === "number" && CFG.goal_prior > 0) ? CFG.goal_prior : 3.20;
  // Teamstärken-Prior (λ Heim/Gast) aus der Saisondaten-DB – weicher Anker,
  // die Quoten bleiben das Hauptsignal.
  function priorFor(h, a) {
    if (!CFG.priors) return null;
    var p = CFG.priors[h + "|" + a];
    if (p && typeof p[0] === "number" && typeof p[1] === "number")
      // Weiches Gewicht (0,15): der Saisondaten-Prior stützt den
      // Markt-Fit, ohne ihn bei abweichenden Quoten zu verdrängen
      // (stärker getestet in tests/js/tip_optimizer_engine_test.js).
      return { lh: p[0], la: p[1], w: 0.15 };
    return null;
  }

  function readInputs() {
    var m = loadStore();
    cards.forEach(function (c, i) {
      m[i] = {
        o1: num(c.querySelector(".to-o1").value),
        ox: num(c.querySelector(".to-ox").value),
        o2: num(c.querySelector(".to-o2").value),
        ou25: num(c.querySelector(".to-ou25").value),
        btts: num(c.querySelector(".to-btts").value),
        ou35: num(c.querySelector(".to-ou35").value),
        adjH: clampN(c.querySelector(".to-adjh").value, -40, 40),
        adjA: clampN(c.querySelector(".to-adja").value, -40, 40)
      };
    });
    saveStore(m);
    return m;
  }
  function loadStore() {
    try {
      var raw = localStorage.getItem(STORE_KEY);
      if (raw) {
        var d = JSON.parse(raw);
        if (d && typeof d === "object") return d;
      }
    } catch (e) { /* kaputter Stand wird ersetzt */ }
    return {};
  }
  function saveStore(m) { try { localStorage.setItem(STORE_KEY, JSON.stringify(m)); } catch (e) { } }
  function applyStore(m) {
    cards.forEach(function (c, i) {
      var s = m[i];
      if (!s) return;
      function set(sel, v) { if (v != null) c.querySelector(sel).value = v; }
      set(".to-o1", s.o1); set(".to-ox", s.ox); set(".to-o2", s.o2); set(".to-ou25", s.ou25);
      set(".to-btts", s.btts); set(".to-ou35", s.ou35);
      if (s.adjH) c.querySelector(".to-adjh").value = s.adjH;
      if (s.adjA) c.querySelector(".to-adja").value = s.adjA;
    });
  }

  function initLocalTimes() {
    // Anstoss-Zeiten in die Ortszeit des Browsers übersetzen (DB ist UTC).
    cards.forEach(function (c) {
      var iso = c.getAttribute("data-kick");
      var el = c.querySelector(".to-kick");
      if (!iso || !el) return;
      var d = new Date(iso);
      if (isNaN(d.getTime())) return;
      el.textContent = d.toLocaleDateString("de-DE", { weekday: "short", day: "2-digit", month: "2-digit" }) +
        ", " + d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }) + " Uhr";
      el.title = "Ortszeit deines Browsers (Anstoss " + iso + " UTC)";
    });
  }
  // Datum + Uhrzeit des letzten Online-Abrufs (aus dem Spieltag-Store) —
  // ohne Datum war unklar, von welchem Tag die Quoten sind (Nutzerwunsch (71)).
  function loadStampText() {
    var s = loadStore()["_load"];
    if (!s || !s.ts) return null;
    var d = new Date(s.ts);
    if (isNaN(d.getTime())) return null;
    return d.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" }) + ", " +
      d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }) + " Uhr";
  }
  function loadStamp() {
    var t = loadStampText();
    return t ? " · Quotenstand " + t + " (letzter Online-Abruf)" : "";
  }
  // Server-Zeitstempel (UTC-ISO in data-ts-utc) in lokale Zeit umrechnen —
  // vorher zeigten Chip/Status (lokal) und Karten (UTC) denselben Moment
  // unterschiedlich an (z. B. 14:04 vs. 12:04). (Nutzerwunsch (72).)
  function localizeTimestamps() {
    document.querySelectorAll("[data-ts-utc]").forEach(function (el) {
      var d = new Date(el.getAttribute("data-ts-utc"));
      if (isNaN(d.getTime())) return;
      el.textContent = d.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" }) + " " +
        d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
    });
    document.querySelectorAll("th").forEach(function (th) {
      if (th.textContent.trim() === "Gespeichert (UTC)") th.textContent = "Gespeichert (lokale Zeit)";
    });
  }
  function renderLoadChip() {
    // Persistenter, gut auffindbarer Zeiger oben an der Aktionszeile.
    var chip = $("#to-load-chip");
    if (!chip) return;
    var t = loadStampText();
    if (!t) { chip.style.display = "none"; return; }
    chip.textContent = "🕓 Quotenstand: " + t;
    chip.title = "Zeitpunkt des letzten „Quoten online laden“-Abrufs. Alle Zeitangaben auf dieser Seite sind lokale Zeit (vom UTC-Zeitstempel umgerechnet).";
    chip.style.display = "";
  }

  function recalc() {
    var m = readInputs();
    var R = rho();
    var METHOD = marginMethod();
    var altMethod = METHOD === "power" ? "prop" : "power";
    var rows = [], details = [];
    var analyzed = [], methodDiffs = 0;
    var totalEp = 0, count = 0;
    lastTips = [];
    lastFull = [];

    cards.forEach(function (card, idx) {
      var mm = m[idx] || {};
      var h = card.getAttribute("data-h"), a = card.getAttribute("data-a");
      var fairBox = card.querySelector(".to-fair");
      if (!(mm.o1 && mm.ox && mm.o2)) {
        if (fairBox) fairBox.textContent = "1X2-Quoten unvollständig – Spiel wird nicht berechnet.";
        rows.push("<tr><td><b>" + esc(h) + "</b> – " + esc(a) + "</td><td colspan=\"9\" class=\"muted\">—</td></tr>");
        lastTips.push(null);
        lastFull.push(null);
        return;
      }
      var target = deMargin(mm.o1, mm.ox, mm.o2, METHOD);
      var ex = {
        ou25: mm.ou25 ? Math.min(0.95, Math.max(0.05, 1 / (1.06 * mm.ou25))) : null,
        btts: mm.btts ? Math.min(0.95, Math.max(0.05, 1 / (1.06 * mm.btts))) : null,
        ou35: mm.ou35 ? Math.min(0.95, Math.max(0.05, 1 / (1.06 * mm.ou35))) : null
      };
      var prior = priorFor(h, a);
      var fit = fitLambdas(target, ex, R, prior, GOAL_PRIOR);
      var lh = fit[0], la = fit[1];
      if (mm.adjH) lh = Math.max(0.05, lh * (1 + mm.adjH / 100));
      if (mm.adjA) la = Math.max(0.05, la * (1 + mm.adjA / 100));
      var M = buildMatrix(lh, la, R.r0, R.rD, R.r1);
      var A = analyse(M);
      // Vergleichs-Run mit der anderen Margen-Methode (S. 4 des
      // Standalone-Tools, für den aktuellen Spieltag): zeigt, ob der Tipp
      // von der Methode abhängt.
      var tAlt = deMargin(mm.o1, mm.ox, mm.o2, altMethod);
      var fAlt = fitLambdas(tAlt, ex, R, prior, GOAL_PRIOR);
      var lhAlt = fAlt[0], laAlt = fAlt[1];
      if (mm.adjH) lhAlt = Math.max(0.05, lhAlt * (1 + mm.adjH / 100));
      if (mm.adjA) laAlt = Math.max(0.05, laAlt * (1 + mm.adjA / 100));
      var AAlt = analyse(buildMatrix(lhAlt, laAlt, R.r0, R.rD, R.r1));
      if (AAlt.best[0] !== A.best[0] || AAlt.best[1] !== A.best[1]) methodDiffs++;
      totalEp += A.epBest; count++;
      var bh = A.best[0], bh2 = A.best[1];
      analyzed.push({ h: h, a: a, ep: A.epBest, best: [bh, bh2] });
      var ml = A.topScores[0].t;
      var diff = (bh !== ml[0] || bh2 !== ml[1]);
      var conf = confidence(A.pGe2);
      var knapp = A.epGap < 0.03;
      lastTips.push({ tip: [bh, bh2], modal: ml.slice() });
      lastFull.push({
        match_id: parseInt(card.getAttribute("data-match-id") || "0", 10),
        tip_h: bh, tip_a: bh2,
        ep: A.epBest,
        p1: A.st.p1, px: A.st.px, p2: A.st.p2,
        pge2: A.pGe2, pge3: A.pGe3, pex: A.pEx,
        lh: lh, la: la,
        o1: mm.o1, ox: mm.ox, o2: mm.o2
      });

      rows.push("<tr>" +
        "<td><b>" + esc(h) + "</b> – " + esc(a) + "</td>" +
        "<td class=\"to-lam\">" + fmt(lh) + "</td><td class=\"to-lam\">" + fmt(la) + "</td>" +
        "<td>" + pct(A.st.p1) + "</td><td>" + pct(A.st.px) + "</td><td>" + pct(A.st.p2) + "</td>" +
        "<td>" + ml[0] + ":" + ml[1] + " <span class=\"muted\">(" + pct(A.topScores[0].p) + ")</span></td>" +
        "<td class=\"to-tw\">" + bh + ":" + bh2 + (diff ? " <span class=\"to-warn\" title=\"Optimaler Tipp weicht vom wahrscheinlichsten Einzel-Ergebnis ab\">⚠</span>" : "") + "</td>" +
        "<td><b>" + fmt(A.epBest) + "</b></td>" +
        "<td><span class=\"to-badge " + conf[1] + "\">" + conf[0] + "</span>" + (knapp ? " <span class=\"to-badge to-knapp\" title=\"Zweitbeste Wahl liegt unter 0,03 EP Abstand – Tipp instabil\">knapp</span>" : "") + "</td>" +
        "</tr>");

      var tt = A.topTips.map(function (x, i) { return (i + 1) + ". <b>" + x.t[0] + ":" + x.t[1] + "</b> – " + fmt(x.ep) + " EP"; }).join(" · ");
      var ts = A.topScores.map(function (x, i) { return (i + 1) + ". <b>" + x.t[0] + ":" + x.t[1] + "</b> – " + pct(x.p); }).join(" · ");
      details.push("<details><summary>" + esc(h) + " – " + esc(a) + " &nbsp;<span class=\"to-tw\">" + bh + ":" + bh2 + "</span> " +
        "<span class=\"muted\" style=\"font-weight:400\">(EP " + fmt(A.epBest) + " · Sicherheit " + conf[0] + (knapp ? ", Zweitwahl fast gleich gut" : "") + ")</span></summary>" +
        "<div class=\"to-row\">λ Heim <b>" + fmt(lh) + "</b> · λ Gast <b>" + fmt(la) + "</b>" +
        (mm.adjH || mm.adjA ? " <span class=\"to-warn\">(Adjuster aktiv: Heim " + (mm.adjH > 0 ? "+" : "") + (mm.adjH || 0) + " %, Gast " + (mm.adjA > 0 ? "+" : "") + (mm.adjA || 0) + " % – Markt-Fit war " + fmt(fit[0]) + "/" + fmt(fit[1]) + ")</span>" : "") +
        (prior ? " <span class=\"muted\" title=\"Weicher Anker an die Teamstärken aus den fertigen Spielen der Saison in der App-Datenbank (Quoten bleiben das Hauptsignal)\">Saisondaten-Prior λ " + fmt(prior.lh) + "/" + fmt(prior.la) + " → Fit " + fmt(fit[0]) + "/" + fmt(fit[1]) + "</span>" : "") +
        " &nbsp;|&nbsp; fair 1X2 (" + (METHOD === "power" ? "Power-Methode, k=" + fmt(target[3]) : "proportional") + "): <b>" + pct(target[0]) + " / " + pct(target[1]) + " / " + pct(target[2]) + "</b>" +
        (ex.ou25 != null ? " &nbsp;|&nbsp; fair Ü2,5: <b>" + pct(ex.ou25) + "</b>" : "") +
        (ex.btts != null ? " &nbsp;|&nbsp; fair BTTS: <b>" + pct(ex.btts) + "</b>" : "") +
        (ex.ou35 != null ? " &nbsp;|&nbsp; fair Ü3,5: <b>" + pct(ex.ou35) + "</b>" : "") + "</div>" +
        "<div class=\"to-row\">Top 3 Ergebnisse: " + ts + "</div>" +
        "<div class=\"to-row\">Top 3 Tipps nach EP: " + tt + " <span class=\"muted\">(Abstand zum Zweitbesten: " + fmt(A.epGap) + (knapp ? " → Tipp instabil" : "") + ")</span></div>" +
        "<div class=\"to-row\">Tipp-" + bh + ":" + bh2 + "-Chancen: ≥2 P <b>" + pct(A.pGe2) + "</b> · ≥3 P <b>" + pct(A.pGe3) + "</b> · exakt <b>" + pct(A.pEx) + "</b></div>" +
        (diff ? "<div class=\"to-row to-warn\">⚠ Der optimale Tipp " + bh + ":" + bh2 + " weicht vom wahrscheinlichsten Einzel-Ergebnis (" + ml[0] + ":" + ml[1] + ") ab – unter der 4/3/2-Regel sammelt er über die gesamte Ergebnisverteilung mehr Punkte.</div>" : "") +
        "<div class=\"to-row\">Margen-Methode: " + (METHOD === "power" ? "Power (Standard)" : "proportional") + " → <b>" + bh + ":" + bh2 + "</b> (EP " + fmt(A.epBest) +
        ") · " + (altMethod === "power" ? "Power" : "proportional") + " → " + AAlt.best[0] + ":" + AAlt.best[1] + " (EP " + fmt(AAlt.epBest) + ")" +
        ((AAlt.best[0] !== bh || AAlt.best[1] !== bh2)
          ? " <span class=\"to-warn\">– Tipp hängt an der Margen-Methode ab</span>"
          : " <span class=\"muted\">(beide Methoden: identisch)</span>") + "</div>" +
        "</details>");

      if (fairBox) {
        var margin = (1 / mm.o1 + 1 / mm.ox + 1 / mm.o2 - 1) * 100;
        // Plausibilität: echte BL-1X2-Märkte haben ~5–10 % implizite Marge;
        // deutlich mehr (oder Mini-Quoten) deutet auf einen Eingabefehler hin.
        var oddWarn = (margin > 35 || Math.min(mm.o1, mm.ox, mm.o2) < 1.05)
          ? " <span class=\"to-warn\" title=\"Implizite Marge wirkt unplausibel – bitte Quoten-Eingabe prüfen (kein Engine-Fehler)\">⚠ Quoten prüfen</span>"
          : "";
        fairBox.innerHTML = "fair: 1 <b>" + pct(target[0]) + "</b> · X <b>" + pct(target[1]) + "</b> · 2 <b>" + pct(target[2]) +
          "</b> &nbsp;(Marge ≈ " + fmt(margin, 1) + " %)" +
          (ex.ou25 != null ? " · fair Ü2,5: <b>" + pct(ex.ou25) + "</b>" : "") + oddWarn;
      }
    });

    var results = $("#to-results");
    if (results) results.innerHTML = "<table><thead><tr><th>Spiel</th><th title=\"Vom Modell erwartete Tore (Heim) – λ ist der Poisson-Mittelwert\">λ H</th><th title=\"Vom Modell erwartete Tore (Auswärts) – λ ist der Poisson-Mittelwert\">λ G</th><th title=\"Quote: Heim-Sieg\">1</th><th title=\"Quote: Remis\">X</th><th title=\"Quote: Gast-Sieg\">2</th>" +
      "<th>Wahrsch. Ergebnis</th><th title=\"Tipp mit dem höchsten erwarteten Punktwert (EP) nach der 4/3/2-Regel\">Optimaler Tipp</th><th title=\"Erwartungswert des Tipps in Punkten: exakt 4, gleicher Torsaldo 3, richtiges 1X2 2, sonst 0\">EP</th><th title=\"Wahrscheinlichkeit (P), dass der Tipp mindestens 2 Punkte bringt: ≥70 % hoch, ≥40 % mittel, darunter niedrig\">Sicherheit</th></tr></thead>" +
      "<tbody>" + rows.join("") + "</tbody></table>" +
      "<div class=\"muted to-legend\">⚠ = optimaler Tipp ≠ wahrscheinlichstes Einzel-Ergebnis · „knapp“ = Zweitwahl unter 0,03 EP Abstand (Tipp instabil) · Sicherheit = P(≥ 2 Punkte mit dem Tipp): ≥70 % hoch, ≥40 % mittel, darunter niedrig</div>";
    var det = $("#to-details");
    if (det) det.innerHTML = details.join("");
    var total = $("#to-total");
    if (total) total.innerHTML = count
      ? "Modell-Erwartung für Spieltag " + CFG.md + ": <b>" + fmt(totalEp) + " P</b> (" + count + " Spiele, Maximum " + (count * 4) + ")"
      : "Noch keine vollständigen 1X2-Quoten eingetragen.";
    var chips = $("#to-chips");
    if (chips) chips.innerHTML = count
      ? "<span class=\"to-chip\">Spiele <b>" + count + "</b></span><span class=\"to-chip\">Σ Erwartung <b>" + fmt(totalEp) + " P</b></span><span class=\"to-chip\">Ø/Spiel <b>" + fmt(totalEp / count) + " P</b></span>" +
        (methodDiffs ? "<span class=\"to-chip\" title=\"Beim gewählten Margen-Methoden-Vergleich fällt der optimale Tipp in so vielen Spielen unterschiedlich aus – Details im Akkordeon pro Spiel.\">Methode-empfindlich <b>" + methodDiffs + "</b> Spiele</span>" : "")
      : "";
    var joker = $("#to-joker");
    if (joker) {
      if (analyzed.length === cards.length && analyzed.length) {
        // Der ×2-Joker verdoppelt die erzielten Punkte genau eines Spiels –
        // der Erwartungswert-Gewinn ist also EP des gewählten Tipps: Joker auf
        // das Spiel mit dem höchsten EP.
        var ji = 0;
        for (var k = 1; k < analyzed.length; k++) if (analyzed[k].ep > analyzed[ji].ep) ji = k;
        joker.innerHTML = "🃏 Joker-Vorschlag: <b>" + esc(analyzed[ji].h) + " – " + esc(analyzed[ji].a) + "</b>, Tipp " +
          analyzed[ji].best[0] + ":" + analyzed[ji].best[1] + " – erwartet " + fmt(analyzed[ji].ep) + " P, mit Joker " +
          fmt(analyzed[ji].ep * 2) + " P (höchster Verdopplungs-Effekt des Spieltags)";
      } else {
        joker.textContent = "🃏 Joker-Vorschlag erscheint, sobald alle Spiele vollständige 1X2-Quoten haben.";
      }
    }
    // Quoten-Fold: live-Status im Summary; beim ersten Rechenlauf automatisch
    // einklappen, wenn bereits Quoten eingetragen sind (Ergebnis steht oben).
    var fold = $("#to-input-fold");
    var foldState = $("#to-fold-state");
    if (foldState) foldState.textContent = count + "/" + cards.length + " mit 1X2-Quoten";
    if (!foldInitialized) { foldInitialized = true; if (fold) fold.open = (count === 0); }
  }

  function setStatus(msg, kind) {
    var st = $("#to-online-status");
    if (!st) return;
    st.textContent = msg;
    st.className = "to-online-status " + (kind || "muted");
  }

  function loadOnlineOdds() {
    var btn = $("#to-btn-online");
    if (btn) { btn.classList.add("to-loading"); btn.disabled = true; }
    var foldL = $("#to-input-fold");
    if (foldL) foldL.open = true;
    setStatus("Lade aktuelle Quoten von The-Odds-API (Konsens über alle Buchmacher) …", "muted");
    var url = "/admin/tip-optimizer/odds?md=" + CFG.md;
    fetch(url, { headers: { "Accept": "application/json" } })
      .then(function (r) { return r.json().catch(function () { return { ok: false, msg: "Antwort nicht lesbar." }; }).then(function (d) { return { status: r.status, data: d }; }); })
      .then(function (res) {
        var d = res.data || {};
        if (!d.ok) {
          setStatus(d.msg || "Laden nicht möglich.", "to-bad");
          return;
        }
        var apiMatches = d.matches || [];
        var used = {};
        var filled = 0;
        var unmatched = [];
        var logItems = [];
        cards.forEach(function (card, idx) {
          var h = card.getAttribute("data-h"), a = card.getAttribute("data-a");
          var idxMatch = apiMatches.findIndex(function (p, i) {
            return !used[i] && ((p.h === h && p.a === a) || (namesMatch(p.h, h) && namesMatch(p.a, a)));
          });
          if (idxMatch < 0) {
            // Nur melden, wenn das Spiel danach wirklich ohne 1X2 dasteht
            // (manuell gefüllte Karten bleiben in Ruhe).
            var o1v = card.querySelector(".to-o1").value,
                oxv = card.querySelector(".to-ox").value,
                o2v = card.querySelector(".to-o2").value;
            if (!o1v || !oxv || !o2v) unmatched.push(h + " – " + a);
            return;
          }
          used[idxMatch] = true;
          var p = apiMatches[idxMatch];
          function set(sel, v) { if (v != null) card.querySelector(sel).value = v; }
          set(".to-o1", p.o1); set(".to-ox", p.ox); set(".to-o2", p.o2);
          if (p.ou25 != null) set(".to-ou25", p.ou25);
          if (p.btts != null) { set(".to-btts", p.btts); card.querySelector(".to-btts").closest(".to-extras").hidden = false; }
          if (p.ou35 != null) { set(".to-ou35", p.ou35); card.querySelector(".to-ou35").closest(".to-extras").hidden = false; }
          filled++;
          logItems.push({
            match_id: parseInt(card.getAttribute("data-match-id") || "0", 10),
            o1: p.o1, ox: p.ox, o2: p.o2,
            ou25: p.ou25, btts: p.btts, ou35: p.ou35
          });
        });
        if (filled) { recalc(); }
        // Abruf-Zeitstempel merken (bleibt im Spieltag-Store, übersteht Neuladen).
        try {
          var store = loadStore();
          store["_load"] = { ts: d.ts || new Date().toISOString() };
          saveStore(store);
        } catch (e) { /* ohne Store läuft es trotzdem */ }
        renderLoadChip();
        var cr = d.credits_remaining != null ? " · Credits übrig: " + d.credits_remaining : "";
        var miss = unmatched.length ? " · Nicht zugeordnet (Name): " + unmatched.join("; ") : "";
        var baseMsg = "✓ " + filled + "/" + cards.length + " Spiele mit Quoten befüllt (Median-Konsens)" + miss + cr +
          (d.budget ? " · Monat: " + d.budget + "/" + (CFG.budget_cap || 60) + " Abrufe" : "") + loadStamp();
        var baseKind = filled ? (unmatched.length ? "to-warn" : "to-good") : "to-warn";
        // Quoten-Stand als Zeitstempel in der DB merken (Quoten-Bewegung, 0 €).
        var logP = Promise.resolve({ ok: false, skip: true });
        if (logItems.length) {
          logP = fetch("/admin/tip-optimizer/odds-log", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ matchday: CFG.md, items: logItems })
          })
            .then(function (r) { return r.json().catch(function () { return null; }).then(function (d) { return d || { ok: false, msg: "HTTP " + r.status }; }); })
            .catch(function () { return { ok: false, msg: "Netzwerkfehler" }; });
        }
        logP.then(function (lg) {
          if (lg && lg.skip) { setStatus(baseMsg, baseKind); return; }
          if (!lg || !lg.ok) {
            setStatus(baseMsg + " · ℹ️ Historie: nicht gespeichert" + (lg && lg.msg ? " (" + lg.msg + ")" : "") + " (Quoten-Bewegung bleibt unberührt)", "to-warn");
            return;
          }
          setStatus(baseMsg + " · Historie: " + lg.count + " Stand/Stände gespeichert ✓", baseKind);
        });
      })
      .catch(function (e) {
        setStatus("Netzwerkfehler: " + e.message, "to-bad");
      })
      .then(function () {
        if (btn) { btn.classList.remove("to-loading"); btn.disabled = false; }
      });
  }

  // ---------- Events ----------
  var debounce = null;
  document.addEventListener("input", function (e) {
    var t = e.target;
    if (!t.classList || !t.classList.contains("to-inp")) return;
    clearTimeout(debounce);
    debounce = setTimeout(recalc, 200);
  });
  document.addEventListener("click", function (e) {
    var t = e.target;
    if (!t.classList) return;
    if (t.classList.contains("to-apply-paste")) {
      var card = t.closest(".to-card");
      var txt = card.querySelector(".to-paste").value.replace(/,/g, ".");
      var nums = (txt.match(/\d+(\.\d+)?/g) || []).map(parseFloat).filter(function (x) { return x > 1; });
      function set(sel, v) { if (v != null) card.querySelector(sel).value = v; }
      set(".to-o1", nums[0]); set(".to-ox", nums[1]); set(".to-o2", nums[2]);
      set(".to-ou25", nums[3]); set(".to-btts", nums[4]); set(".to-ou35", nums[5]);
      card.querySelector(".to-paste").value = "";
      recalc();
      return;
    }
    if (t.classList.contains("to-toggle-extras")) {
      var ex = t.closest(".to-card").querySelector(".to-extras");
      ex.hidden = !ex.hidden;
      t.setAttribute("aria-expanded", ex.hidden ? "false" : "true");
      t.textContent = ex.hidden ? "⚙ Optionen (BTTS · Ü3,5 · Adjuster) ▸" : "⚙ Optionen (BTTS · Ü3,5 · Adjuster) ▾";
      return;
    }
    if (t.id === "to-btn-snapshot") {
      // Modellguete-Tracking: aktuellen Modell-Zustand (nur vollstaendige
      // Spiele) als Vorhersage-Run in der DB ablegen. Die Meldung erscheint
      // direkt neben dem Button (#to-snap-msg), nicht im Seiten-Status.
      var sm = $("#to-snap-msg");
      function snapMsg(txt, color) { if (sm) { sm.textContent = txt; sm.style.color = color; } }
      var items = lastFull.filter(Boolean);
      if (!items.length) { snapMsg("Nichts zu speichern – zuerst 1X2-Quoten eintragen.", "var(--warning)"); return; }
      fetch("/admin/tip-optimizer/snapshot", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ matchday: CFG.md, items: items })
      })
        .then(function (r) { return r.json().catch(function () { return null; }).then(function (d) { return { st: r.status, d: d }; }); })
        .then(function (res) {
          if (res.d && res.d.ok) {
            snapMsg("Gespeichert (" + res.d.count + " Spiele) · " + new Date().toISOString().slice(11, 16) + " UTC ✓", "#4ade80");
          } else {
            snapMsg((res.d && res.d.msg) || "Speichern nicht möglich (HTTP " + res.st + ").", "var(--danger)");
          }
        })
        .catch(function (e) { snapMsg("Netzwerkfehler: " + e.message, "var(--danger)"); });
      return;
    }
    if (t.id === "to-btn-backtest") {
      // Walk-Forward-Backtest (Server rechnet aus den fertigen DB-Spielen).
      var bt = $("#to-backtest");
      var btnB = $("#to-btn-backtest");
      if (btnB) { btnB.classList.add("to-loading"); btnB.disabled = true; }
      if (bt) bt.innerHTML = '<div class="muted">Berechne Walk-Forward-Backtest (je abgelaufenen Spieltag aus allen bisherigen Spielen neu fit) …</div>';
      fetch("/admin/tip-optimizer/backtest", { headers: { "Accept": "application/json" } })
        .then(function (r) { return r.json().catch(function () { return {}; }); })
        .then(function (d) {
          d = d || {};
          if (!bt) return;
          if (d.n_matches === 0) {
            bt.innerHTML = '<div class="muted">' + esc(d.message || "Noch zu wenig Daten.") + "</div>";
            return;
          }
          var rows = (d.per_md || []).map(function (r) {
            return "<tr><td>ST " + r.md + "</td><td>" + r.n + "</td><td>" + fmt(r.ep_per_match) + "</td>" +
              "<td>" + pct(r.hit1x2) + "</td><td>" + pct(r.pge2_rate) + "</td><td>" + fmt(r.brier, 3) + "</td></tr>";
          }).join("");
          bt.innerHTML =
            '<div class="to-chips-row">' +
            "<span class=\"to-chip\">Spiele <b>" + d.n_matches + "</b></span>" +
            "<span class=\"to-chip\">bewertet. Spieltage <b>" + d.n_matchdays + "</b></span>" +
            "<span class=\"to-chip\">EP/Spiel <b>" + fmt(d.ep_per_match) + "</b></span>" +
            "<span class=\"to-chip\" title=\"Anteil der Spiele, in denen der optimale Tipp mindestens 2 Punkte holt\">P(≥2 P) <b>" + pct(d.pge2_rate) + "</b></span>" +
            "<span class=\"to-chip\">Exakt-Top-1 <b>" + pct(d.top1_rate) + "</b></span>" +
            "<span class=\"to-chip\">Exakt-Top-3 <b>" + pct(d.top3_rate) + "</b></span>" +
            "<span class=\"to-chip\" title=\"Mittlerer Fehler der vorhergesagten Torsumme\">Torsumme MAE <b>" + fmt(d.goals_mae) + "</b></span>" +
            "</div>" +
            '<div class="to-row">1X2-Trefferquote: <b>' + pct(d.hit1x2) + "</b> · Baselines: Immer-Heim " + pct(d.hit1x2_immer_heim) + " · Zufall 33 %</div>" +
            '<div class="to-row" title="Brier: Zuverlässigkeit der Prozentzahlen (0 = perfekt, 0,67 = Zufallstipp). Das Modell ist gut, wenn sein Wert deutlich unter dem Zufall-Wert liegt.">Brier 1X2 (kleiner = besser): <b>' + fmt(d.brier, 3) + "</b> · Immer-Heim " + fmt(d.brier_immer_heim, 3) + " · Liga-Durchschnitt " + fmt(d.brier_liga, 3) + " · Zufall " + fmt(d.brier_zufall, 3) + "</div>" +
            '<div class="muted" style="font-size:12px">' + esc(d.note || "") + "</div>" +
            '<div class="to-tblwrap"><table class="to-tblwide-narrow"><thead><tr><th title="Spieltag">ST</th><th>Spiele</th><th title="Erwartungswert je Spiel (4/3/2-Regel)">EP/Spiel</th><th title="Anteil der Spiele, in denen die richtige 1X2-Wahl (1/X/2) getippt wurde">1X2-Treffer</th><th title="Anteil der Spiele, in denen der Tipp mindestens 2 Punkte bringt">P(≥2 P)</th><th title="Qualität der 1X2-Wahrscheinlichkeitsprognose: 0 = perfekt, ~0,67 = Zufall, kleiner ist besser">Brier</th></tr></thead><tbody>' + rows + "</tbody></table></div>";
        })
        .catch(function (e) {
          if (bt) bt.innerHTML = '<div class="to-online-status to-bad">Netzwerkfehler: ' + esc(e.message) + "</div>";
        })
        .then(function () { if (btnB) { btnB.classList.remove("to-loading"); btnB.disabled = false; } });
      return;
    }
    if (t.id === "to-btn-clear") {
      var foldC = $("#to-input-fold");
      if (foldC) foldC.open = true;
      cards.forEach(function (card) {
        card.querySelectorAll("input").forEach(function (inp) {
          if (inp.classList.contains("to-adjh") || inp.classList.contains("to-adja")) inp.value = 0;
          else inp.value = "";
        });
        var ex2 = card.querySelector(".to-extras");
        if (ex2) ex2.hidden = true;
      });
      try { localStorage.removeItem(STORE_KEY); } catch (e2) { }
      recalc();
      return;
    }
    if (t.id === "to-btn-online") { loadOnlineOdds(); }
  });
  document.addEventListener("keydown", function (e) {
    if (e.target.classList && e.target.classList.contains("to-paste") && e.key === "Enter") {
      e.preventDefault();
      e.target.closest(".to-card").querySelector(".to-apply-paste").click();
    }
  });
  ["to-rho0", "to-rhoD", "to-rho1"].forEach(function (id) {
    var el = document.getElementById(id);
    if (el) el.addEventListener("input", function () { clearTimeout(debounce); debounce = setTimeout(recalc, 250); });
  });
  var mm = document.getElementById("to-margin");
  if (mm) mm.addEventListener("change", recalc);

  // ---------- Init ----------
  initLocalTimes();
  localizeTimestamps();
  applyStore(loadStore());
  renderLoadChip();
  if (cards.length) recalc();
  var statusEl = $("#to-online-status");
  var stamp = loadStamp();
  if (statusEl && stamp) statusEl.textContent += stamp;
})();
