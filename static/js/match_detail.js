(function() {
  // ============= COUNTDOWN =============
  const cd = document.getElementById('countdown');
  if (cd) {
    const target = new Date(cd.dataset.target);
    function tick() {
      const diff = target - new Date();
      if (diff <= 0) { cd.innerHTML = '<strong>ANPFIFF!</strong>'; return; }
      const d = Math.floor(diff / 86400000);
      const h = Math.floor(diff % 86400000 / 3600000);
      const m = Math.floor(diff % 3600000 / 60000);
      const s = Math.floor(diff % 60000 / 1000);
      const dEl = cd.querySelector('.d'), hEl = cd.querySelector('.h'),
            mEl = cd.querySelector('.m'), sEl = cd.querySelector('.s');
      if (dEl) dEl.textContent = d;
      if (hEl) hEl.textContent = String(h).padStart(2, '0');
      if (mEl) mEl.textContent = String(m).padStart(2, '0');
      if (sEl) sEl.textContent = String(s).padStart(2, '0');
      const compact = cd.querySelector('.tu-countdown-compact');
      if (compact) {
        compact.textContent = diff > 48 * 3600000
          ? `⏳ Noch ${d} Tag${d === 1 ? '' : 'e'} · Anpfiff ${target.toLocaleDateString('de-DE', {day:'2-digit', month:'2-digit'})}. ${target.toLocaleTimeString('de-DE', {hour:'2-digit', minute:'2-digit'})} Uhr`
          : `⏳ Noch ${d ? d + 'T ' : ''}${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')} h · Anpfiff ${target.toLocaleTimeString('de-DE', {hour:'2-digit', minute:'2-digit'})} Uhr`;
      }
    }
    tick(); setInterval(tick, 1000);
  }

  // ============= STEPPER (+/-) =============
  document.querySelectorAll('.tip-step-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const target = btn.dataset.target;
      const input = document.getElementById(target);
      if (!input) return;
      const cur = parseInt(input.value) || 0;
      const isPlus = btn.classList.contains('plus');
      const next = isPlus ? Math.min(20, cur + 1) : Math.max(0, cur - 1);
      input.value = next;
      input.classList.add('value-flash');
      setTimeout(() => input.classList.remove('value-flash'), 250);
      markDirty();
    });
  });

  // ============= QUICK-TENDENCY =============
  document.querySelectorAll('.qt-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const t = btn.dataset.tendency;
      const home = document.getElementById('home_tip');
      const away = document.getElementById('away_tip');
      if (!home || !away) return;
      if (t === 'home') { home.value = 2; away.value = 1; }
      if (t === 'draw') { home.value = 1; away.value = 1; }
      if (t === 'away') { home.value = 1; away.value = 2; }
      home.classList.add('value-flash'); away.classList.add('value-flash');
      setTimeout(() => {
        home.classList.remove('value-flash'); away.classList.remove('value-flash');
      }, 250);
      markDirty();
    });
  });

  // ============= JOKER-TOGGLE =============
  const jokerToggle = document.getElementById('jokerToggle');
  if (jokerToggle) {
    const lbl = jokerToggle.closest('.joker-toggle');
    jokerToggle.addEventListener('change', () => {
      lbl.classList.toggle('is-on', jokerToggle.checked);
      markDirty();
    });
  }

  // ============= TIPP-INPUTS LIVE-CHANGE =============
  document.querySelectorAll('.tip-step-input').forEach(input => {
    input.addEventListener('input', markDirty);
  });

  // ============= AUTO-SAVE STATE =============
  let isDirty = false;
  let isSaving = false;
  const swipeArea = document.getElementById('swipeArea');
  const canTip = swipeArea && swipeArea.dataset.canTip === '1';
  const matchId = swipeArea ? swipeArea.dataset.matchId : null;
  const statusEl = document.getElementById('tipSaveStatus');

  function markDirty() {
    isDirty = true;
    if (statusEl) statusEl.innerHTML = '✏️ <em>Änderungen ungespeichert</em>';
  }

  async function saveTip() {
    if (!canTip || !isDirty || !matchId) return true;
    if (isSaving) return false;
    const home = document.getElementById('home_tip');
    const away = document.getElementById('away_tip');
    if (!home || !away) return true;
    isSaving = true;
    if (statusEl) statusEl.innerHTML = '⏳ Speichern...';
    try {
      const res = await fetch(`/api/tip/${matchId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || ''
        },
        body: JSON.stringify({
          home_tip: parseInt(home.value) || 0,
          away_tip: parseInt(away.value) || 0,
          joker: !!(jokerToggle && jokerToggle.checked),
        }),
      });
      const data = await res.json();
      if (data.ok) {
        isDirty = false;
        if (statusEl) statusEl.innerHTML = '✅ Gespeichert';
        setTimeout(() => { if (statusEl && !isDirty) statusEl.innerHTML = ''; }, 2000);
        return true;
      } else {
        if (statusEl) statusEl.innerHTML = `❌ ${data.error || 'Fehler'}`;
        return false;
      }
    } catch (e) {
      if (statusEl) statusEl.innerHTML = '❌ Netzwerkfehler';
      return false;
    } finally {
      isSaving = false;
    }
  }

  // ============= NAVIGATION HANDLER =============
  async function navigate(url) {
    if (!url) return;
    const ok = await saveTip();
    // Egal ob Save geklappt hat - bei Fehler bleibt der User auf der Seite
    if (ok || !isDirty) {
      window.location.href = url;
    }
  }

  document.querySelectorAll('#navPrev, #navNext, .float-nav-btn, .md-dot').forEach(el => {
    if (el.tagName !== 'A') return;
    el.addEventListener('click', e => {
      if (!isDirty) return; // normaler Link
      e.preventDefault();
      navigate(el.href);
    });
  });

  // Auch bei Klick auf "Speichern & weiter" (falls noch da):
  const tipForm = document.getElementById('tipForm');
  if (tipForm) {
    tipForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const ok = await saveTip();
      if (ok) {
        const nextLink = document.getElementById('navNext');
        if (nextLink) {
          window.location.href = nextLink.href;
        } else {
          // letztes Spiel → zurueck zum Schnelltipp
          const qtCfg = document.getElementById('md-config');
          window.location.href = qtCfg && qtCfg.dataset.quickTipUrl ? qtCfg.dataset.quickTipUrl : '/';
        }
      }
    });
  }

  // ============= KEYBOARD SHORTCUTS =============
  document.addEventListener('keydown', (e) => {
    // Ignorieren wenn in Input/Textarea getippt wird
    const tag = (e.target.tagName || '').toLowerCase();
    const isInput = ['input', 'textarea', 'select'].includes(tag);

    if (e.key === 'ArrowLeft' && !isInput) {
      e.preventDefault();
      const prev = document.getElementById('navPrev');
      if (prev) navigate(prev.href);
    } else if (e.key === 'ArrowRight' && !isInput) {
      e.preventDefault();
      const next = document.getElementById('navNext');
      if (next) navigate(next.href);
    } else if (e.key === 'ArrowUp' && isInput && (e.target.id === 'home_tip' || e.target.id === 'away_tip')) {
      // arrow up im Score-Input erhöht (Browser macht das schon, aber wir markieren dirty)
      markDirty();
    } else if (e.key === 'ArrowDown' && isInput && (e.target.id === 'home_tip' || e.target.id === 'away_tip')) {
      markDirty();
    } else if (e.key === 'j' && !isInput) {
      // J = Joker togglen
      if (jokerToggle && !jokerToggle.disabled) {
        jokerToggle.checked = !jokerToggle.checked;
        jokerToggle.dispatchEvent(new Event('change'));
      }
    }
  });

  // ============= TOUCH-SWIPE =============
  if (swipeArea) {
    let touchStartX = 0, touchStartY = 0;
    let touchEndX = 0, touchEndY = 0;
    const SWIPE_THRESHOLD = 50;
    const VERTICAL_TOLERANCE = 80;

    swipeArea.addEventListener('touchstart', e => {
      touchStartX = e.changedTouches[0].screenX;
      touchStartY = e.changedTouches[0].screenY;
    }, { passive: true });

    swipeArea.addEventListener('touchend', e => {
      touchEndX = e.changedTouches[0].screenX;
      touchEndY = e.changedTouches[0].screenY;
      const dx = touchEndX - touchStartX;
      const dy = touchEndY - touchStartY;
      // Horizontaler Swipe? (ignoriert vertikales Scrollen)
      if (Math.abs(dx) > SWIPE_THRESHOLD && Math.abs(dy) < VERTICAL_TOLERANCE) {
        if (dx < 0) {
          // Wisch nach links → nächstes Spiel
          const nextUrl = swipeArea.dataset.next;
          if (nextUrl) {
            swipeArea.classList.add('swipe-out-left');
            setTimeout(() => navigate(nextUrl), 200);
          }
        } else {
          // Wisch nach rechts → vorheriges
          const prevUrl = swipeArea.dataset.prev;
          if (prevUrl) {
            swipeArea.classList.add('swipe-out-right');
            setTimeout(() => navigate(prevUrl), 200);
          }
        }
      }
    }, { passive: true });
  }

  // ============= BEFORE-UNLOAD WARNUNG =============
  window.addEventListener('beforeunload', (e) => {
    if (isDirty && !isSaving) {
      // Versuche letzten Save beim Verlassen per keepalive-fetch
      const home = document.getElementById('home_tip');
      const away = document.getElementById('away_tip');
      if (home && away && matchId) {
        fetch(`/api/tip/${matchId}`, {
          method: 'POST',
          keepalive: true,
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || ''
          },
          body: JSON.stringify({
            home_tip: parseInt(home.value) || 0,
            away_tip: parseInt(away.value) || 0,
            joker: !!(jokerToggle && jokerToggle.checked),
          }),
        }).catch(() => {});
      }
    }
  });
})();
