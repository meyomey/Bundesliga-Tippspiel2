/* (132) Spieldetail-Popup: Klick auf eine Spielzeile (Dashboard-Link
 * .match-row oder Live-Center-Karte .live-match-card) oeffnet die
 * vorhandene /match/<id>-Seite als Modal (iframe, embed=1 = schlanke
 * Shell ohne Navigation). Delegation auf document, damit SSE-Rerenders
 * im Live-Center weitergreifen. Strg/Klick etc. oeffnet weiter im Tab.
 */
(function () {
  "use strict";
  var overlay = null;
  var lastFocus = null;

  function isPlainClick(e) {
    return !(e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0);
  }

  function escHandler(e) {
    if (e.key === "Escape") closePopup();
  }

  function closePopup() {
    document.removeEventListener("keydown", escHandler);
    if (overlay && overlay.parentNode) overlay.parentNode.removeChild(overlay);
    overlay = null;
    document.body.classList.remove("mp-lock");
    if (lastFocus && lastFocus.focus) lastFocus.focus();
    lastFocus = null;
  }

  function openPopup(matchId) {
    closePopup();
    lastFocus = document.activeElement;
    overlay = document.createElement("div");
    overlay.className = "mp-overlay";
    overlay.innerHTML =
      '<div class="mp-dialog" role="dialog" aria-modal="true" aria-label="Spieldetails">' +
      '<div class="mp-head"><span class="mp-title">Spieldetails</span>' +
      '<button type="button" class="mp-close" aria-label="Schlie\u00dfen">\u2715</button></div>' +
      '<div class="mp-body"><div class="mp-spinner" aria-hidden="true"></div>' +
      '<iframe class="mp-frame" src="/match/' + matchId + '?embed=1" title="Spieldetails"></iframe>' +
      "</div></div>";
    document.body.appendChild(overlay);
    document.body.classList.add("mp-lock");
    overlay.addEventListener("click", function (e) {
      if (e.target === overlay) closePopup();
    });
    overlay.querySelector(".mp-close").addEventListener("click", closePopup);
    var frame = overlay.querySelector(".mp-frame");
    frame.addEventListener("load", function () {
      if (overlay) overlay.classList.add("mp-ready");
    });
    document.addEventListener("keydown", escHandler);
    overlay.querySelector(".mp-close").focus();
  }

  document.addEventListener("click", function (e) {
    if (!isPlainClick(e)) return;
    var card = e.target.closest(".live-match-card[data-match-id]");
    if (card) {
      e.preventDefault();
      openPopup(card.getAttribute("data-match-id"));
      return;
    }
    var qt = e.target.closest("a.qt-details-link[href*='/match/']");
    if (qt) {
      var qid = qt.getAttribute("href").split("/match/")[1].split(/[?#/]/)[0];
      if (qid) {
        e.preventDefault();
        openPopup(qid);
      }
      return;
    }
    var row = e.target.closest("a.match-row[href*='/match/']");
    if (row) {
      var id = row.getAttribute("href").split("/match/")[1].split(/[?#/]/)[0];
      if (id) {
        e.preventDefault();
        openPopup(id);
      }
    }
  });
})();
