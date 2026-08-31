(function() {
  // ============= Zeitzone-Korrektur: UTC → Lokal =============
  const DAYS_DE = ['So', 'Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa'];
  
  document.querySelectorAll('.qt-match-time').forEach(el => {
    const utcStr = el.dataset.utc;
    if (!utcStr) return;
    
    const d = new Date(utcStr);
    if (isNaN(d.getTime())) return;
    
    el.querySelector('.qt-day-name').textContent = DAYS_DE[d.getDay()] + ',';
    el.querySelector('.qt-date-display').textContent = 
      String(d.getDate()).padStart(2, '0') + '.' + String(d.getMonth() + 1).padStart(2, '0') + '.';
    el.querySelector('.qt-time-display').textContent = 
      String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0') + ' Uhr';
  });

  // ============= +/- Stepper =============
  document.querySelectorAll('.qt-step-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const inputId = btn.dataset.input;
      const input = document.getElementById(inputId);
      if (!input || input.disabled) return;
      
      const dir = parseInt(btn.dataset.dir);
      const cur = parseInt(input.value) || 0;
      const next = Math.max(0, Math.min(20, cur + dir));
      
      input.value = next;
      input.classList.add('input-flash');
      setTimeout(() => input.classList.remove('input-flash'), 250);
      input.dispatchEvent(new Event('change'));
    });
  });

  // ============= Joker Toggle =============
  function refreshJokerUi() {
    document.querySelectorAll('.qt-joker-label').forEach(label => {
      const input = label.querySelector('.qt-joker-input');
      const active = !!(input && input.checked);
      label.classList.toggle('is-active', active);
      const text = label.querySelector('.qt-joker-text');
      if (text) text.textContent = active ? 'Joker aktiv – doppelte Punkte' : 'Joker setzen';
      const card = label.closest('.qt-match-card');
      if (card) card.classList.toggle('has-joker', active);
    });
  }
  document.querySelectorAll('.qt-joker-input').forEach(radio => {
    radio.addEventListener('change', () => {
      refreshJokerUi();
    });
  });
  refreshJokerUi();

  // ============= Fortschritt & Counter =============
  function updateProgress() {
    const cards = document.querySelectorAll('.qt-match-card');
    const total = cards.length;
    let tipped = 0;
    
    cards.forEach(card => {
      const matchId = card.dataset.matchId;
      const home = document.getElementById('home_' + matchId);
      const away = document.getElementById('away_' + matchId);
      const locked = card.classList.contains('closed');
      const filled = home && away && home.value !== '' && away.value !== '';
      if (filled) tipped++;
      card.classList.toggle('has-tip', filled);

      const status = card.querySelector('.qt-card-status');
      if (status) {
        status.classList.toggle('is-open', !locked && !filled);
        status.classList.toggle('is-saved', !locked && filled);
        status.classList.toggle('is-locked', locked);
        status.textContent = locked ? '🔒 nicht mehr änderbar' : (filled ? '✅ gespeichert' : '⏰ offen');
      }
    });
    const missing = Math.max(0, total - tipped);
    const progressText = document.getElementById('qtProgressText');
    if (progressText) progressText.textContent = `${tipped} von ${total} getippt · ${missing} fehlen`;
    const progressBar = document.getElementById('qtProgressBar');
    if (progressBar) progressBar.style.width = (total > 0 ? (tipped / total * 100) : 0) + '%';
  }

  const saveTimers = new Map();
  function scheduleAutoSave(matchId, delay = 650) {
    if (!matchId) return;
    clearTimeout(saveTimers.get(matchId));
    saveTimers.set(matchId, setTimeout(() => autoSave(matchId), delay));
  }

  document.querySelectorAll('.qt-input-num').forEach(inp => {
    inp.addEventListener('change', () => { updateProgress(); scheduleAutoSave(inp.dataset.matchId); });
    inp.addEventListener('input', () => { updateProgress(); scheduleAutoSave(inp.dataset.matchId, 900); });
  });
  updateProgress();

  // ============= Auto-Save =============
  const statusBar = document.getElementById('qtStatusBar');
  const statusIcon = document.getElementById('qtStatusIcon');
  const statusMsg = document.getElementById('qtStatusMessage');

  function setStatus(icon, message, type) {
    statusIcon.textContent = icon;
    statusMsg.textContent = message;
    statusBar.className = 'qt-status-bar' + (type ? ' qt-status-' + type : '');
  }

  async function autoSave(matchId) {
    const home = document.getElementById('home_' + matchId);
    const away = document.getElementById('away_' + matchId);
    if (!home || !away || home.value === '' || away.value === '') return;
    
    const jokerRadio = document.querySelector(`.qt-joker-input[value="${matchId}"]`);
    const useJoker = jokerRadio && jokerRadio.checked;

    const card = document.querySelector(`.qt-match-card[data-match-id="${matchId}"]`);
    if (card) card.classList.add('save-flash');
    setStatus('✅', 'Gespeichert', 'ok');

    try {
      const res = await fetch('/api/tip/' + matchId, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || ''
        },
        body: JSON.stringify({
          home_tip: parseInt(home.value) || 0,
          away_tip: parseInt(away.value) || 0,
          joker: !!useJoker,
        }),
      });
      const data = await res.json();
      if (!data.ok) throw new Error(data.error);
      
      setTimeout(() => {
        card?.classList.remove('save-flash');
        setStatus('💡', 'Auto-Save aktiv · Joker ×2', '');
      }, 1000);
    } catch (e) {
      card?.classList.remove('save-flash');
      setStatus('⚠️', 'Fehler beim Speichern', 'err');
    }
  }

  document.querySelectorAll('.qt-input-num').forEach(inp => {
    inp.addEventListener('blur', () => autoSave(inp.dataset.matchId));
  });

  document.querySelectorAll('.qt-joker-input').forEach(radio => {
    radio.addEventListener('change', () => {
      updateProgress();
      if (radio.checked) scheduleAutoSave(radio.value, 150);
    });
  });

  // ============= Zufällig füllen =============
  document.getElementById('qtRandomBtn')?.addEventListener('click', () => {
    if (!confirm('Leere Felder mit zufälligen Tipps (0–3 Tore) füllen?')) return;
    
    const touchedMatches = new Set();
    document.querySelectorAll('.qt-input-num').forEach(inp => {
      if (inp.value === '' && !inp.disabled) {
        inp.value = Math.floor(Math.random() * 4);
        touchedMatches.add(inp.dataset.matchId);
        inp.classList.add('input-flash');
        setTimeout(() => inp.classList.remove('input-flash'), 250);
      }
    });
    updateProgress();
    touchedMatches.forEach(id => scheduleAutoSave(id, 250));
    setStatus('🎲', 'Zufällig befüllt – Auto-Save läuft', 'warn');
  });

  // ============= Submit =============
  document.getElementById('quickTipForm')?.addEventListener('submit', (e) => {
    updateProgress();
  });
})();
