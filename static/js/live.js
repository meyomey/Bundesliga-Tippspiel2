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
  const POLL = 30_000;
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

  function estimateInitialLiveMinutes() {
    document.querySelectorAll('.live-match-card.status-live .lm-status').forEach(badge => {
      if (badge.textContent.includes('Min')) return;
      const raw = badge.dataset.kickoff;
      if (!raw) return;
      const ko = new Date(raw);
      if (Number.isNaN(ko.getTime())) return;
      const minute = Math.max(1, Math.min(90, Math.floor((Date.now() - ko.getTime()) / 60000) + 1));
      badge.innerHTML = `<span class="live-dot small"></span> LIVE · ${minute}. Min`;
    });
  }
  estimateInitialLiveMinutes();

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
    lastSnapshot.leaderboard[el.dataset.userId] = {
      rank: parseInt(el.dataset.rank),
      points: parseInt(el.dataset.points),
    };
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

    // Status-Klasse + Badge inklusive Spielminute
    card.classList.remove('status-scheduled', 'status-live', 'status-finished');
    card.classList.add(`status-${m.status}`);
    const badge = card.querySelector('.lm-status');
    if (badge) {
      badge.className = `lm-status status-${m.status}`;
      let minute = m.minute;
      if (m.status === 'live' && (!minute || Number.isNaN(Number(minute))) && m.kickoff) {
        const ko = new Date(m.kickoff);
        if (!Number.isNaN(ko.getTime())) {
          minute = Math.max(1, Math.min(90, Math.floor((Date.now() - ko.getTime()) / 60000) + 1));
        }
      }
      badge.innerHTML = m.status === 'live'    ? `<span class="live-dot small"></span> LIVE${minute ? ` · ${minute}. Min` : ''}`
                       : m.status === 'finished' ? '✓ ENDE'
                       : 'geplant';
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

      // Rang-Veränderung anzeigen
      const rankEl = row.querySelector('.rank-change');
      if (rankBefore !== undefined && rankBefore !== r.rank) {
        const diff = rankBefore - r.rank; // positive: aufgestiegen
        if (diff > 0) {
          rankEl.innerHTML = `<span class="rank-up">▲ ${diff}</span>`;
          flashElement(row, 'row-up');
        } else {
          rankEl.innerHTML = `<span class="rank-down">▼ ${-diff}</span>`;
          flashElement(row, 'row-down');
        }
        // Nach 8s ausblenden
        setTimeout(() => { rankEl.innerHTML = ''; }, 8000);
      }

      // Punkte-Veränderung
      const pointsEl = row.querySelector('.points-delta');
      if (pointsBefore !== undefined && pointsBefore !== r.points) {
        const diff = r.points - pointsBefore;
        if (diff > 0) {
          pointsEl.innerHTML = `<span class="points-up">+${diff}</span>`;
          flashElement(row.querySelector('.points-num'), 'points-flash');
        }
        setTimeout(() => { pointsEl.innerHTML = ''; }, 8000);
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
