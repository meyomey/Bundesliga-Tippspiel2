/* --- Live-Punkte-Refresh (nur bei laufenden Spielen geladen) --- */
(function() {
  const tbody = document.getElementById('tipOverviewBody');
  if (!tbody) return;
  async function refreshLivePoints() {
    try {
      const liveUrl = tbody.dataset.liveUrl;
      if (!liveUrl) return;
      const res = await fetch(liveUrl, { credentials: 'same-origin' });
      const data = await res.json();
      if (!data.ok || !Array.isArray(data.rows)) return;
      const rowMap = new Map();
      tbody.querySelectorAll('tr[data-user-id]').forEach(tr => rowMap.set(parseInt(tr.dataset.userId, 10), tr));
      const ordered = [];
      data.rows.forEach(r => {
        const tr = rowMap.get(r.user_id);
        if (!tr) return;
        const total = tr.querySelector('[data-role="total-points"]');
        const md = tr.querySelector('[data-role="md-points"]');
        if (total) total.innerHTML = `<strong>${r.total_points}</strong>${r.rank ? `<small>Rang ${r.rank}</small>` : ''}`;
        if (md) md.innerHTML = `<strong>${r.matchday_points}</strong>`;
        ordered.push(tr);
      });
      if (tbody.dataset.sort !== 'name') ordered.forEach(tr => tbody.appendChild(tr));
    } catch (e) { console.debug('Livepunkte-Refresh fehlgeschlagen', e); }
  }
  refreshLivePoints();
  setInterval(refreshLivePoints, 20000);
})();
