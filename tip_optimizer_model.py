"""Tipp-Optimizer: Modell-Anker aus den echten Saisondaten der App.

Alle Werte werden NUR aus den fertigen Spielen des aktiven Wettbewerbs in
der App-Datenbank berechnet (keine fremden Schätzwerte):

* Ligate Torschnitt (mu_home/mu_away)
* Teamstärken (Angriff/Abwehr als Multiplikatoren, mit Shrinkage Richtung
  neutral je nach Anzahl gespielter Spiele)
* Dixon-Coles-Niedrigtor-Verhältnis (beobachtet vs. unabhängiges Poisson)
* Torsummen-Prior (Liga-Mittel)
* λ-Priors pro Spiel ( Heim = mu_H * att_Heim * def_Gast, analog Gast )

Unter MIN_MATCHES fertigen Spielen liefert die Funktion die statischen
Defaults des Standalone-Tools (fitted=False), damit der Optimizer auch auf
frischen Datenbanken unverändert läuft.
"""
import math
from datetime import datetime

STATIC_RHO = (1.00, 1.09, 0.97)
STATIC_GOAL_PRIOR = 3.20  # BL-Mittel 25/26 (Standalone-Tool-Default)
MIN_MATCHES = 8  # darunter ist das Fit statistisch zu instabil
LAMBDA_MIN, LAMBDA_MAX = 0.15, 4.5
RHO_MIN, RHO_MAX = 0.5, 1.8


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


# ---- Python-Abbild der JS-Engine (static/js/to_engine.js) -------------------
# Bewusst gleiche Mathematik (Poisson, Dixon-Coles, 4/3/2-Regel), damit der
# Backtest exakt das misst, was die UI berechnet. NMAX = 11 wie in der Engine.
NMAX = 11


def _poisson_vec(l):
    return [math.exp(-l) * (l ** k) / math.factorial(k) for k in range(NMAX + 1)]


def build_matrix(lh, la, rho0, rhoD, rho1):
    """Ergebnismatrix P(i,j) mit Dixon-Coles-Korrektur (wie TOEngine.buildMatrix)."""
    ph, pa = _poisson_vec(lh), _poisson_vec(la)
    M = [[0.0] * (NMAX + 1) for _ in range(NMAX + 1)]
    s = 0.0
    for i in range(NMAX + 1):
        for j in range(NMAX + 1):
            x = ph[i] * pa[j]
            if i == 0 and j == 0:
                x *= rho0
            elif i == 1 and j == 1:
                x *= rhoD
            elif (i, j) in ((1, 0), (0, 1)):
                x *= rho1
            M[i][j] = x
            s += x
    for i in range(NMAX + 1):
        for j in range(NMAX + 1):
            M[i][j] /= s
    return M


def tip_points(h, a, th, ta):
    """App-Regel 4/3/2/0 (identisch zu TOEngine.tipPoints)."""
    if h == th and a == ta:
        return 4
    if (h - a) == (th - ta):
        return 3
    sa = (h > a) - (h < a)
    st = (th > ta) - (th < ta)
    return 2 if sa == st else 0


def ep_table(M):
    """Erwartungswert (EP) fuer alle Tipps (th,ta) <= 7 – O(N^2) statt
    64x144 Brutto-Summen. Die 4/3/2-Regel ist ein disjunktes Indikator-Summe,
    also: EP = P(exakt) + P(gleicher Torsaldo) + 2*P(gleiche Richtung)
    (Pruefung: exakt -> 1+1+2=4, gleicher Saldo -> 0+1+2=3, gleiche Richtung
    -> 0+0+2=2, sonst 0). Die Torsaldo-Klasse ist die Anti-Diagonale i-j=d;
    die Richtungsklasse ist ein ganzes Quadrant (P(1)/P(X)/P(2))."""
    n = NMAX + 1
    diag = {}
    p1 = px = p2 = 0.0
    for i in range(n):
        for j in range(n):
            diag[i - j] = diag.get(i - j, 0.0) + M[i][j]
            if i > j:
                p1 += M[i][j]
            elif i == j:
                px += M[i][j]
            else:
                p2 += M[i][j]
    table = {}
    for th in range(8):
        for ta in range(8):
            quad = p1 if th > ta else (px if th == ta else p2)
            table[(th, ta)] = M[th][ta] + diag[th - ta] + 2.0 * quad
    return table


def _argmax_tip(table):
    """Beste Tippwahl mit demselben Tie-Break wie die Engine
    (Reihenfolge th aufsteigend, dann ta; stabiles Maximum)."""
    best, best_ep = None, -1.0
    for (th, ta), ep in table.items():
        if ep > best_ep:
            best, best_ep = (th, ta), ep
    return best, best_ep


def _top_scores(M, k=3):
    """Die k wahrscheinlichsten Endstaende (Tie-Break: Ergebnis-Reihenfolge)."""
    cells = [(M[i][j], i, j) for i in range(NMAX + 1) for j in range(NMAX + 1)]
    cells.sort(key=lambda c: (-c[0], c[1], c[2]))
    return cells[:k]


def finished_matches(matches):
    """Alle Spiele mit Endstand (für die Saison-Fit-Zwecke)."""
    return [m for m in matches
            if m.status == "finished" and m.home_score is not None
            and m.away_score is not None]


def _team_strengths(finished, mu_h, mu_a):
    """Teamstärken als (Angriff, Abwehr)-Multiplikatoren auf den Ligaschnitt.

    1.0 = genau Ligaschnitt; >1.0 = stärker. Angriffs-Komponente: eigene
    Torschnitts (Heim gemessen am Liga-Heimschnitt, Gast am
    Liga-Auswärtschnitt); Abwehr analog über die kassierten Tore. Shrinkage:
    n/(n+6) – Teams mit wenigen Spielen rücken Richtung neutral, damit
    Ausreißer-Ergebnisse (z. B. 6:0 nach drei Spielen) das Modell nicht
    verrücken.
    """
    agg = {}

    def t(name):
        # [Tore_Heim, Gegentore_Heim, n_Heim, Tore_Gast, Gegentore_Gast, n_Gast]
        return agg.setdefault(name, [0.0, 0.0, 0, 0.0, 0.0, 0])

    for m in finished:
        h = t(m.home_team.name)
        a = t(m.away_team.name)
        h[0] += m.home_score
        h[1] += m.away_score
        h[2] += 1
        a[3] += m.away_score
        a[4] += m.home_score
        a[5] += 1

    out = {}
    for name, (sh, cnh, nh, sca, cna, na) in agg.items():
        atts, defs = [], []
        if nh:
            atts.append((sh / nh) / mu_h)
            defs.append((cnh / nh) / mu_a)
        if na:
            atts.append((sca / na) / mu_a)
            defs.append((cna / na) / mu_h)
        att = sum(atts) / len(atts) if atts else 1.0
        dfn = sum(defs) / len(defs) if defs else 1.0
        w = (nh + na) / (nh + na + 6.0)  # Shrinkage Richtung neutral
        out[name] = (1.0 + w * (att - 1.0), 1.0 + w * (dfn - 1.0))
    return out


def _dixon_coles_ratios(finished, mu_h, mu_a):
    """Empirische Dixon-Coles-Faktoren: beobachtete Niedrigtor-Frequenzen
    geteilt durch die erwarteten Frequenzen des unabhängigen Poisson mit den
    Ligate-Torschnitten (0:0, 1:1, und geometrisches Mittel aus 1:0/0:1)."""
    n = len(finished)
    f00 = sum(1 for m in finished if m.home_score == 0 and m.away_score == 0) / n
    f11 = sum(1 for m in finished if m.home_score == 1 and m.away_score == 1) / n
    f10 = sum(1 for m in finished if m.home_score == 1 and m.away_score == 0) / n
    f01 = sum(1 for m in finished if m.home_score == 0 and m.away_score == 1) / n
    p = math.exp(-mu_h - mu_a)
    p00, p11 = p, mu_h * mu_a * p
    p10, p01 = mu_h * p, mu_a * p
    r0 = f00 / p00 if p00 else 1.0
    rD = f11 / p11 if p11 else 1.0
    r1 = math.sqrt((f10 / p10 if p10 else 1.0) * (f01 / p01 if p01 else 1.0))
    return [_clamp(r0, RHO_MIN, RHO_MAX), _clamp(rD, RHO_MIN, RHO_MAX),
            _clamp(r1, RHO_MIN, RHO_MAX)]


def fit_season_model(matches):
    """Fittet den Saisondaten-Stand für den Optimizer.

    Returns dict mit:
      rho        – [rho0, rhoD, rho1] (DC-Faktoren, gefittet oder Default)
      goal_prior – ligaübliche Torsumme (Zahl)
      fitted     – True, wenn genug Daten für ein echtes Fit vorlagen
      n          – Anzahl ausgewerteter fertiger Spiele
      strengths  – {Team: (angriff, abwehr)} (nur bei fitted=True)
      mu_home / mu_away – Ligaschnitte (nur bei fitted=True)
    """
    finished = finished_matches(matches)
    n = len(finished)
    base = {"rho": list(STATIC_RHO), "goal_prior": STATIC_GOAL_PRIOR,
            "fitted": False, "n": n, "strengths": {}}
    if n < MIN_MATCHES:
        return base
    mu_h = sum(m.home_score for m in finished) / n
    mu_a = sum(m.away_score for m in finished) / n
    if mu_h <= 0 or mu_a <= 0:
        return base
    return {
        "rho": _dixon_coles_ratios(finished, mu_h, mu_a),
        "goal_prior": _clamp(mu_h + mu_a, 2.0, 4.5),
        "fitted": True,
        "n": n,
        "mu_home": mu_h,
        "mu_away": mu_a,
        "strengths": _team_strengths(finished, mu_h, mu_a),
    }


def prior_lambdas(model, home_name, away_name):
    """λ-Prior [Heim, Gast] für ein Spiel aus den Teamstärken (None: kein
    Datenmaterial, dann läuft die Engine ohne Prior wie im Standalone-Tool).

    Heim-λ = Liga-Heimschnitt * Angriff(Heim) * Abwehr(Gast) – analog Gast.
    """
    if not model.get("fitted"):
        return None
    s = model["strengths"]
    if home_name not in s or away_name not in s:
        return None
    att_h, def_h = s[home_name]
    att_a, def_a = s[away_name]
    lh = _clamp(model["mu_home"] * att_h * def_a, LAMBDA_MIN, LAMBDA_MAX)
    la = _clamp(model["mu_away"] * att_a * def_h, LAMBDA_MIN, LAMBDA_MAX)
    return [round(lh, 3), round(la, 3)]


def _brier(p1, px, p2, outcome):
    """Brier-Score (kleiner = besser) fuer ein 1X2-Ziel."""
    o1 = 1 if outcome == 1 else 0
    ox = 1 if outcome == "X" else 0
    o2 = 1 if outcome == 2 else 0
    return (o1 - p1) ** 2 + (ox - px) ** 2 + (o2 - p2) ** 2


def backtest(matches):
    """Walk-Forward-Backtest der Modell-Grundlage (ohne Odds-Anker).

    Fuer jeden abgeschlossenen Spieltag wird das Modell aus ALLEN vorherigen
    fertigen Spielen gefittet (exakt die Produktions-Pfade: Teamstaerken,
    Dixon-Coles-Faktoren, Torsumme) und blind auf den Spieltag angewendet:
    λ = Teamstaerken-Prior, dann EP-optimaler Tipp nach der 4/3/2-Regel.

    Wichtig: Historische 1X2-Quoten sind nicht verfuegbar (keine Gratis-
    Quelle), also misst der Backtest die Modell-Grundlage – eine Untergrenze
    fuer die echte Tipp-Qualitaet mit Odds-Anker.

    Returns JSON-faehiges dict (n_matches=0 => zu wenig Daten).
    """
    finished = finished_matches(matches)
    finished.sort(key=lambda m: (m.matchday or 0,
                                 m.kickoff or datetime.min,
                                 m.id or 0))

    # Spieltage in Reihenfolge ihres Erreichens zusammenfassen
    mds = []  # [(md, [matches])]
    for m in finished:
        if mds and mds[-1][0] == m.matchday:
            mds[-1][1].append(m)
        else:
            mds.append((m.matchday, [m]))

    per_md = []
    tot = {"n": 0, "ep": 0.0, "hit1": 0, "hit3": 0, "pge2": 0,
           "mae": 0.0, "brier": 0.0,
           "brier_heim": 0.0, "brier_unif": 0.0,
           "one": 0, "x": 0, "two": 0}
    preceding = []
    for md, group in mds:
        if len(preceding) < MIN_MATCHES:
            preceding.extend(group)
            continue
        model = fit_season_model(preceding)
        if not model.get("fitted"):
            preceding.extend(group)
            continue
        r0, rD, r1 = model["rho"]
        rows = {"md": md, "n": 0, "ep": 0.0, "hit1x2": 0, "pge2": 0, "brier": 0.0}
        for m in group:
            pl = prior_lambdas(model, m.home_team.name, m.away_team.name)
            if pl is None:
                pl = [model["mu_home"], model["mu_away"]]  # neutrale Liga-Staerken
            M = build_matrix(pl[0], pl[1], r0, rD, r1)
            table = ep_table(M)
            (th, ta), ep = _argmax_tip(table)
            # 1X2-Verteilung des Modells
            p1 = px = p2 = 0.0
            for i in range(NMAX + 1):
                for j in range(NMAX + 1):
                    if i > j:
                        p1 += M[i][j]
                    elif i == j:
                        px += M[i][j]
                    else:
                        p2 += M[i][j]
            h, a = m.home_score, m.away_score
            pts = tip_points(h, a, th, ta)
            outcome = 1 if h > a else ("X" if h == a else 2)
            # 1X2-Vorhersage = wahrscheinlichstes Ergebnis (Tie-Break 1<X<2)
            pred = max(((p1, 1), (px, "X"), (p2, 2)), key=lambda t: t[0])[1]
            top3 = _top_scores(M, 3)
            mae = abs((pl[0] + pl[1]) - (h + a))
            b = _brier(p1, px, p2, outcome)
            # Baselines: "Immer Heim" (Vektor 1,0,0) => Brier 0 bei Heim-Sieg,
            # sonst 1; "Zufall" (1/3,1/3,1/3) => (2/3)^2+2*(1/3)^2 = 2/3 (konst.)
            b_heim = 0.0 if outcome == 1 else 1.0
            b_unif = 2.0 / 3.0

            tot["n"] += 1
            tot["ep"] += ep
            tot["hit1"] += 1 if (h, a) == top3[0][1:] else 0
            tot["hit3"] += 1 if any((h, a) == c[1:] for c in top3) else 0
            tot["pge2"] += 1 if pts >= 2 else 0
            tot["mae"] += mae
            tot["brier"] += b
            tot["brier_heim"] += b_heim
            tot["brier_unif"] += b_unif
            tot["one" if outcome == 1 else ("x" if outcome == "X" else "two")] += 1
            rows["n"] += 1
            rows["ep"] += ep
            rows["hit1x2"] += 1 if pred == outcome else 0
            rows["pge2"] += 1 if pts >= 2 else 0
            rows["brier"] += b
            preceding.append(m)
        n = rows["n"]
        per_md.append({
            "md": md, "n": n,
            "ep": round(rows["ep"], 2), "ep_per_match": round(rows["ep"] / n, 2),
            "hit1x2": round(rows["hit1x2"] / n, 3),
            "pge2_rate": round(rows["pge2"] / n, 3),
            "brier": round(rows["brier"] / n, 4),
        })

    if tot["n"] == 0:
        return {"n_matches": 0, "n_matchdays": 0, "message":
                "Noch zu wenig abgeschlossene Spieltage (Mind."
                f" {MIN_MATCHES} fertige Spiele vor dem zu bewertenden Spieltag)."}
    n = tot["n"]
    home_rate = tot["one"] / n
    draw_rate = tot["x"] / n
    away_rate = tot["two"] / n
    brier_liga = (_brier(home_rate, draw_rate, away_rate, 1) * tot["one"]
                  + _brier(home_rate, draw_rate, away_rate, "X") * tot["x"]
                  + _brier(home_rate, draw_rate, away_rate, 2) * tot["two"]) / n
    hit_model = sum(r["hit1x2"] * r["n"] for r in per_md) / n
    return {
        "n_matches": n,
        "n_matchdays": len(per_md),
        "min_matches": MIN_MATCHES,
        "ep_per_match": round(tot["ep"] / n, 3),
        "pge2_rate": round(tot["pge2"] / n, 3),
        "top1_rate": round(tot["hit1"] / n, 3),
        "top3_rate": round(tot["hit3"] / n, 3),
        "goals_mae": round(tot["mae"] / n, 3),
        "hit1x2": round(hit_model, 3),
        "hit1x2_immer_heim": round(home_rate, 3),
        "brier": round(tot["brier"] / n, 4),
        "brier_immer_heim": round(tot["brier_heim"] / n, 4),
        "brier_liga": round(brier_liga, 4),
        "brier_zufall": round(2.0 / 3.0, 4),
        "outcomes": {"home": tot["one"], "draw": tot["x"], "away": tot["two"]},
        "per_md": per_md,
        "note": ("Ohne Odds-Anker (historische Quoten nicht verfuegbar) – "
                 "Mass fuer die Modell-Grundlage (Teamstaerken + Dixon-Coles), "
                 "Untergrenze der echten Tipp-Qualitaet."),
    }


def evaluate_run_tips(tips):
    """Bewertet eine gespeicherte Vorhersage (OptimizerRunTip-Objekte mit
    .match) gegen die Endstaende: erwartete vs. realisierte EP, Trefferquote
    der Sicherheit-Chips, Kalibrierung (Brier).

    Returns None, wenn noch nicht alle Spiele beendet sind, sonst dict.
    """
    if not tips:
        return None
    acc = {"n": 0, "ep_exp": 0.0, "ep_real": 0.0, "pge2_exp": 0.0, "pge2_hit": 0,
           "brier": 0.0, "one": 0, "x": 0, "two": 0}
    for t in tips:
        m = t.match
        if m is None or m.status != "finished" or m.home_score is None:
            return None
        h, a = m.home_score, m.away_score
        pts = tip_points(h, a, t.tip_h, t.tip_a)
        outcome = 1 if h > a else ("X" if h == a else 2)
        acc["n"] += 1
        acc["ep_exp"] += float(t.ep or 0.0)
        acc["ep_real"] += pts
        acc["pge2_exp"] += float(t.pge2 or 0.0)
        acc["pge2_hit"] += 1 if pts >= 2 else 0
        acc["brier"] += _brier(float(t.p1 or 0.0), float(t.px or 0.0),
                               float(t.p2 or 0.0), outcome)
        acc["one" if outcome == 1 else ("x" if outcome == "X" else "two")] += 1
    n = acc["n"]
    return {
        "n": n,
        "ep_exp": round(acc["ep_exp"], 2),
        "ep_real": round(acc["ep_real"], 2),
        "ep_per_match": round(acc["ep_real"] / n, 2),
        "pge2_exp": round(acc["pge2_exp"] / n, 3),
        "pge2_rate": round(acc["pge2_hit"] / n, 3),
        "brier": round(acc["brier"] / n, 4),
    }
