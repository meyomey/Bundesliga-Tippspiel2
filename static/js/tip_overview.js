/* --- Querformat-Hinweis --- */
(function(){
  const buttons = Array.from(document.querySelectorAll('#tipLandscapeBtn, #tipLandscapeBtnCompact'));
  if (!buttons.length) return;
  const canLock = screen.orientation && screen.orientation.lock;
  buttons.forEach(btn => btn.addEventListener('click', async () => {
    try {
      if (canLock) {
        await screen.orientation.lock('landscape');
        btn.textContent = 'Querformat aktiv';
      } else {
        alert('Bitte das Smartphone ins Querformat drehen. Falls die App nicht rotiert: Android/PWA kurz neu installieren bzw. Anzeige-Drehen aktivieren.');
      }
    } catch (e) {
      alert('Bitte Bildschirmdrehung am Gerät aktivieren und das Smartphone ins Querformat drehen.');
    }
  }));
})();

/* --- Mobiler Spiel-Selector --- */
(function(){
  const select = document.getElementById('mobileMatchSelect');
  if (!select) return;
  select.addEventListener('change', () => {
    document.querySelectorAll('.tip-mobile-match-panel').forEach(p => p.classList.remove('active'));
    const panel = document.getElementById('mobile-' + select.value);
    if (panel) panel.classList.add('active');
  });
})();
