document.addEventListener('DOMContentLoaded', function() {
  const sdEl = document.getElementById('stats-chart-data');
  const SD = sdEl ? JSON.parse(sdEl.textContent) : {};
  if (typeof Chart === 'undefined') {
    console.warn('Chart.js ist nicht geladen; Statistikdiagramme werden uebersprungen.');
    return;
  }
  const teal = '#14b8a6';
  const blue = '#3b82f6';
  const green = '#10b981';
  const yellow = '#f59e0b';
  const red = '#ef4444';

  const compactChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
  };

  // Ranglistenverlauf aller Spieler
  const rankCtx = document.getElementById('rankProgressChart');
  let rankChart = null;
  const rankDatasets = SD.rank_datasets;
  if (rankCtx && rankDatasets.length) {
    rankChart = new Chart(rankCtx, {
      type: 'line',
      data: {
        labels: SD.rank_labels,
        datasets: rankDatasets
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'nearest', intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function(ctx) { return `${ctx.dataset.label}: Platz ${ctx.parsed.y}`; }
            }
          }
        },
        scales: {
          y: {
            reverse: true,
            min: 1,
            max: SD.rank_max,
            ticks: { stepSize: 1, precision: 0 },
            title: { display: true, text: 'Platz' }
          },
          x: { title: { display: true, text: 'Spieltag' } }
        }
      }
    });
  }

  function syncRankCheckboxes() {
    if (!rankChart) return;
    document.querySelectorAll('[data-rank-player]').forEach(cb => {
      const idx = Number(cb.dataset.rankPlayer);
      cb.checked = rankChart.isDatasetVisible(idx);
    });
  }

  function setRankVisibility(mode) {
    if (!rankChart) return;
    rankChart.data.datasets.forEach((ds, idx) => {
      let visible = false;
      if (mode === 'all') visible = true;
      if (mode === 'me') visible = !!ds.isMe;
      if (mode === 'top') visible = idx < 5 || !!ds.isMe;
      rankChart.setDatasetVisibility(idx, visible);
    });
    rankChart.update();
    syncRankCheckboxes();
  }

  document.querySelectorAll('[data-rank-player]').forEach(cb => {
    cb.addEventListener('change', () => {
      if (!rankChart) return;
      const idx = Number(cb.dataset.rankPlayer);
      rankChart.setDatasetVisibility(idx, cb.checked);
      rankChart.update();
    });
  });
  document.getElementById('rankSelectTop')?.addEventListener('click', () => setRankVisibility('top'));
  document.getElementById('rankSelectMe')?.addEventListener('click', () => setRankVisibility('me'));
  document.getElementById('rankSelectAll')?.addEventListener('click', () => setRankVisibility('all'));
  syncRankCheckboxes();

  // Punkte-Verlauf
  const ptsCtx = document.getElementById('pointsChart');
  if (ptsCtx) {
    new Chart(ptsCtx, {
      type: 'line',
      data: {
        labels: SD.md_labels,
        datasets: [{
          label: 'Punkte',
          data: SD.md_data,
          borderColor: teal,
          backgroundColor: teal + '20',
          fill: true,
          tension: 0.3,
          pointRadius: 4,
        }]
      },
      options: {
        ...compactChartOptions,
        plugins: { legend: { display: false } },
        scales: {
          x: { title: { display: true, text: 'Spieltag' } },
          y: { beginAtZero: true, title: { display: true, text: 'Punkte' } }
        }
      }
    });
  }

  // Tipp-Qualität (gestapelt)
  const accCtx = document.getElementById('accuracyChart');
  if (accCtx) {
    new Chart(accCtx, {
      type: 'bar',
      data: {
        labels: SD.acc_labels,
        datasets: [
          { label: 'Exakt %', data: SD.acc_exact, backgroundColor: green },
          { label: 'Differenz %', data: SD.acc_diff, backgroundColor: blue },
          { label: 'Tendenz %', data: SD.acc_tendency, backgroundColor: yellow },
          { label: 'Daneben %', data: SD.acc_wrong, backgroundColor: red },
        ]
      },
      options: {
        ...compactChartOptions,
        plugins: {
          legend: { position: 'bottom' },
          tooltip: {
            callbacks: {
              label: function(ctx) { return ctx.dataset.label + ': ' + ctx.parsed.y.toFixed(1) + '%'; }
            }
          }
        },
        scales: {
          x: { stacked: true, title: { display: true, text: 'Spieltag' } },
          y: { stacked: true, max: 100, title: { display: true, text: '%' } }
        }
      }
    });
  }
});
