/* --- Kopfblock: Live-Status --- */
(function() {
  const tabButtons = document.querySelectorAll('[data-live-tab]');
  if (tabButtons.length) {
    function setLiveTab(tab) {
      document.body.classList.toggle('live-tab-ranking', tab === 'ranking');
      document.body.classList.toggle('live-tab-games', tab !== 'ranking');
      tabButtons.forEach(btn => btn.classList.toggle('is-active', btn.dataset.liveTab === tab));
      const header = document.querySelector('.live-header');
      if (header) header.scrollIntoView({ block: 'start' });
    }
    setLiveTab('games');
    tabButtons.forEach(btn => {
      btn.addEventListener('click', () => setLiveTab(btn.dataset.liveTab || 'games'));
    });
  }
})();

/* --- Live-Center Polling & UI --- */
(function() {
  const POLL = 20_000; // passt zum 20s-OLB-Boost-Fenster (Server drosselt selbst)
  const matchesList = document.getElementById('liveMatchesList');
  const lbList = document.getElementById('liveLeaderboard');
  const refreshBtn = document.getElementById('liveRefreshBtn');
  const toggleBtn = document.getElementById('autoRefreshToggle');
  const lastSyncEl = document.getElementById('lastSync');
  const liveCountPill = document.getElementById('liveCountPill');

  if (!matchesList && !lbList) return;

  let autoRefreshOn = true;
  let lastSyncTs = Date.now();

  // Snapshots zum Vergleich
  let lastSnapshot = {
    matches: {},  // id → {home_score, away_score, status}
    leaderboard: {},  // user_id → {rank, points}
  };

  // Bezugswert beim Seitenaufruf (Nutzerfeedback 06.09.): Trendpfeile und
  // +Punkte bleiben dauerhaft sichtbar und zeigen die Veraenderung seit dem
  // Oeffnen der Seite - nicht nur den letzten 30s-Poll, der nach 8s verblasste.
  let baseLb = {};  // user_id -> {rank, points}

  // Bewusst keine Spielminute ab Anstosszeit schaetzen: gezeigt wird nur,
  // was der Live-Feed liefert (via /api/live/center, alle 30s). Ohne Feed-
  // Minute steht nur "LIVE", in der Halbzeit "Halbzeitpause".

  // Erstinitialisierung aus dem DOM
  document.querySelectorAll('.live-match-card').forEach(el => {
    const id = el.dataset.matchId;
    lastSnapshot.matches[id] = {
      home: el.querySelector('.lm-home-score').textContent.trim(),
      away: el.querySelector('.lm-away-score').textContent.trim(),
      status: [...el.classList].find(c => c.startsWith('status-'))?.replace('status-', ''),
    };
  });
  document.querySelectorAll('.live-lb-row').forEach(el => {
    const b = {
      rank: parseInt(el.dataset.rank),
      points: parseInt(el.dataset.points),
    };
    lastSnapshot.leaderboard[el.dataset.userId] = b;
    baseLb[el.dataset.userId] = { ...b };
  });

  function relTime(d) {
    const s = Math.floor((Date.now() - d) / 1000);
    if (s < 5) return 'gerade eben';
    if (s < 60) return `vor ${s}s`;
    if (s < 3600) return `vor ${Math.floor(s/60)}min`;
    return `vor ${Math.floor(s/3600)}h`;
  }

  function updateSyncTimer() {
    if (lastSyncEl) lastSyncEl.textContent = `· ${relTime(lastSyncTs)}`;
  }
  setInterval(updateSyncTimer, 1000);

  function setPersistent(el, html) {
    // Nur bei echter Aenderung neu einsetzen: die CSS-Einblend-Animation
    // laeuft so nicht bei jedem 30s-Poll erneut.
    if (el && el.innerHTML !== html) el.innerHTML = html;
  }

  function flashElement(el, cls = 'flash-update') {
    el.classList.add(cls);
    setTimeout(() => el.classList.remove(cls), 1500);
  }

  function updateMatch(m) {
    const card = matchesList?.querySelector(`.live-match-card[data-match-id="${m.id}"]`);
    if (!card) return;
    const prev = lastSnapshot.matches[m.id] || {};

    // Score
    const homeEl = card.querySelector('.lm-home-score');
    const awayEl = card.querySelector('.lm-away-score');
    const newHome = m.home_score === null ? '-' : String(m.home_score);
    const newAway = m.away_score === null ? '-' : String(m.away_score);

    if (homeEl.textContent.trim() !== newHome) {
      homeEl.textContent = newHome;
      flashElement(homeEl, 'score-change');
    }
    if (awayEl.textContent.trim() !== newAway) {
      awayEl.textContent = newAway;
      flashElement(awayEl, 'score-change');
    }

    // Status-Klasse + Badge - dasselbe Prinzip wie serverseitig:
    // Feed-Werte (minute/halftime) sind verbindlich; die abgeleitete
    // Struktur-Uhr (minute_derived) wird mit '≈' als Naeherung markiert.
    card.classList.remove('status-scheduled', 'status-live', 'status-finished');
    card.classList.add(`status-${m.status}`);
    const badge = card.querySelector('.lm-status');
    if (badge) {
      badge.className = `lm-status status-${m.status}`;
      const halft = m.halftime;
      let html;
      if (m.status === 'live') {
        if (halft === 'feed') {
          html = '⏸ Halbzeitpause';
          badge.removeAttribute('title');
        } else if (m.minute) {
          const approx = m.minute_derived ? '≈ ' : '';
          const val = (m.overtime && m.minute_derived) ? '90+' : m.minute;
          html = `<span class="live-dot small"></span> LIVE · ${approx}${val}. Min`;
          if (m.minute_derived) {
            badge.setAttribute('title', 'Minute näherungsweise aus der Anstosszeit (Halbzeit berücksichtigt, ohne Nachspielzeit)');
          } else {
            badge.removeAttribute('title');
          }
        } else {
          html = halft === 'derived' ? '⏸ Halbzeit ≈' : '<span class="live-dot small"></span> LIVE';
          if (halft === 'derived') {
            badge.setAttribute('title', 'Halbzeitpause aus der Anstosszeit abgeleitet');
          } else {
            badge.removeAttribute('title');
          }
        }
      } else {
        html = m.status === 'finished' ? '✓ ENDE' : 'geplant';
        badge.removeAttribute('title');
      }
      badge.innerHTML = html;
    }

    lastSnapshot.matches[m.id] = { home: newHome, away: newAway, status: m.status };
  }

  function rebuildLeaderboard(rows) {
    if (!lbList) return;
    // Vorher: alte Rang-Map
    const oldRanks = {};
    Object.entries(lastSnapshot.leaderboard).forEach(([uid, d]) => oldRanks[uid] = d.rank);
    const oldPoints = {};
    Object.entries(lastSnapshot.leaderboard).forEach(([uid, d]) => oldPoints[uid] = d.points);

    // Neue Reihenfolge HTML bauen
    const fragment = document.createDocumentFragment();
    rows.forEach(r => {
      let row = lbList.querySelector(`.live-lb-row[data-user-id="${r.user_id}"]`);
      const rankBefore = oldRanks[r.user_id];
      const pointsBefore = oldPoints[r.user_id];

      if (!row) {
        // neuer User → Element erzeugen (selten)
        row = document.createElement('div');
        row.className = `live-lb-row ${r.is_me ? 'me' : ''} ${r.rank === 1 ? 'top1' : ''}`;
        row.dataset.userId = r.user_id;
        row.innerHTML = `
          <div class="lb-rank">
            <span class="rank-num-big">${r.rank}</span>
            <span class="rank-change" data-change=""></span>
          </div>
          <div class="lb-user">
            <div class="avatar-fallback small">${r.username[0].toUpperCase()}</div>
            <div><strong>${r.username}</strong>
              <small class="muted" title="Exakte Tipps · richtige Tordifferenz · richtige Tendenz">${r.exact} exakt · ${r.diff} Diff · ${r.tendency} Tendenz</small>
            </div>
          </div>
          <div class="lb-points">
            <span class="points-num">${r.points}</span>
            <span class="points-delta" data-delta=""></span>
          </div>`;
      } else {
        // Update inhalte
        row.querySelector('.rank-num-big').textContent = r.rank;
        row.querySelector('.points-num').textContent = r.points;
        const small = row.querySelector('.lb-user small');
        if (small) small.textContent = `${r.exact} exakt · ${r.diff} Diff · ${r.tendency} Tendenz`;
        row.classList.toggle('top1', r.rank === 1);
      }

      // Persistenter Vergleich zur Seitenbasis: wer stieg seit dem Oeffnen
      // wie viele Plaetze, wer bekam wie viele Punkte. Blinken nur bei
      // frischer Aenderung (letzter Poll), die Anzeige selbst bleibt stehen.
      const base = baseLb[r.user_id] || { rank: r.rank, points: r.points };
      baseLb[r.user_id] = base;
      const rankDelta = base.rank - r.rank;    // positiv: aufgestiegen
      const ptsDelta = r.points - base.points; // positiv: Punkte dazubekommen

      const rankEl = row.querySelector('.rank-change');
      setPersistent(rankEl,
        rankDelta > 0 ? `<span class="rank-up" title="Rang seit Seitenöffnung +${rankDelta}">▲ ${rankDelta}</span>`
        : rankDelta < 0 ? `<span class="rank-down" title="Rang seit Seitenöffnung ${rankDelta}">▼ ${-rankDelta}</span>`
        : '');
      if (rankBefore !== undefined && rankBefore !== r.rank) {
        flashElement(row, rankBefore > r.rank ? 'row-up' : 'row-down');
      }

      const pointsEl = row.querySelector('.points-delta');
      setPersistent(pointsEl,
        ptsDelta > 0 ? `<span class="points-up" title="Punkte seit Seitenöffnung">+${ptsDelta}</span>`
        : ptsDelta < 0 ? `<span class="points-down" title="Punkte seit Seitenöffnung">${ptsDelta}</span>`
        : '');
      if (pointsBefore !== undefined && pointsBefore !== r.points) {
        flashElement(row.querySelector('.points-num'), 'points-flash');
      }

      fragment.appendChild(row);
      lastSnapshot.leaderboard[r.user_id] = { rank: r.rank, points: r.points };
    });
    lbList.innerHTML = '';
    lbList.appendChild(fragment);
  }

  async function refresh() {
    if (refreshBtn) { refreshBtn.disabled = true; refreshBtn.textContent = '⏳'; }
    try {
      const r = await fetch('/api/live/center', { credentials: 'same-origin' });
      const data = await r.json();
      if (!data.ok) {
        console.warn('Live-Center API-Fehler:', data);
        return;
      }
      lastSyncTs = Date.now();
      // Live-Count berechnen
      const liveCount = data.matches.filter(m => m.status === 'live').length;
      if (liveCountPill) {
        liveCountPill.textContent = liveCount > 0 ? `${liveCount} LIVE` : '';
        liveCountPill.style.display = liveCount > 0 ? '' : 'none';
      }
      // Matches updaten
      data.matches.forEach(updateMatch);
      // Leaderboard
      rebuildLeaderboard(data.leaderboard);
      updateSyncTimer();
    } catch(e) {
      console.error('Live-Refresh fehlgeschlagen:', e);
    } finally {
      if (refreshBtn) { refreshBtn.disabled = false; refreshBtn.textContent = '🔄 Jetzt aktualisieren'; }
    }
  }

  let intervalId = null;
  let eventSource = null;

  function handleLiveData(data) {
    lastSyncTs = Date.now();
    // Live-Count berechnen
    const liveCount = data.matches.filter(m => m.status === 'live').length;
    if (liveCountPill) {
      liveCountPill.textContent = liveCount > 0 ? `${liveCount} LIVE` : '';
      liveCountPill.style.display = liveCount > 0 ? '' : 'none';
    }
    // Matches updaten
    data.matches.forEach(updateMatch);
    // Leaderboard
    rebuildLeaderboard(data.leaderboard);
    updateSyncTimer();
  }

  function startSSE() {
    // Stabilitaet auf Plesk/Passenger: keine dauerhaften SSE-Verbindungen.
    // Polling ist fuer dieses Hosting deutlich robuster, weil jede Anfrage
    // kurz bleibt und keinen Worker dauerhaft blockiert.
    startPolling();
  }

  function stopSSE() {
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }
  }

  function startPolling() {
    stopPolling();
    intervalId = setInterval(refresh, POLL);
  }
  
  function stopPolling() {
    if (intervalId) clearInterval(intervalId);
    intervalId = null;
  }

  if (refreshBtn) refreshBtn.addEventListener('click', refresh);
  if (toggleBtn) {
    toggleBtn.addEventListener('click', () => {
      autoRefreshOn = !autoRefreshOn;
      if (autoRefreshOn) {
        startSSE();
        toggleBtn.textContent = '⏸ Pause Auto';
        toggleBtn.classList.add('btn-primary');
        toggleBtn.classList.remove('btn-ghost');
      } else {
        stopSSE();
        stopPolling();
        toggleBtn.textContent = '▶ Auto starten';
        toggleBtn.classList.remove('btn-primary');
        toggleBtn.classList.add('btn-ghost');
      }
    });
  }

  // Initialer Live-Count
  const initialLive = document.querySelectorAll('.live-match-card.status-live').length;
  if (liveCountPill && initialLive > 0) {
    liveCountPill.textContent = `${initialLive} LIVE`;
  }

  // Starte stabiles HTTP-Polling
  startSSE();
  updateSyncTimer();
})();
