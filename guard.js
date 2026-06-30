/* Shared access guard for tool pages.
   A page must, BEFORE loading this file, set:
       window.UTG_GUARD = "../";          // path back to the home page
       window.UTG_TOOL  = "pixel-art";    // which tool this page is
       window.UTG_PLAY  = "flappy";       // (final game pages only) the game slug
   and load  class-codes.js  first.

   - If the saved class code is missing/disabled or doesn't include this tool,
     the kid is sent to the home gate so resources stay locked outside class.
   - On a final game page (UTG_PLAY set), if the code may not PLAY that game,
     the kid is sent to that game's guide instead.
   - Records permissions for the page: html.utg-can-print (print:true), and
     window.UTG.canPlay(slug) for the hub to show/hide Play buttons. */
(function () {
  function deny(to) { location.replace(to || ((window.UTG_GUARD || "../") + "?locked=1")); }
  var entry = null;
  try {
    var saved = (localStorage.getItem("utg_class_code") || "").trim().toUpperCase();
    var list = window.CLASS_CODES || [];
    for (var i = 0; i < list.length; i++) {
      if (list[i].enabled && String(list[i].code).trim().toUpperCase() === saved) { entry = list[i]; break; }
    }
  } catch (e) {}
  function allow(perm, key) {
    return perm === true || perm === "all" || (!!perm && perm.indexOf && perm.indexOf(key) >= 0);
  }
  window.UTG = { entry: entry, canPlay: function (slug) { return !!entry && allow(entry.play, slug); } };

  if (window.UTG_TOOL) {
    var ok = !!entry && (entry.tools === "all" || (entry.tools && entry.tools.indexOf(window.UTG_TOOL) >= 0));
    if (!ok) { deny(); return; }
    if (entry.print) document.documentElement.classList.add("utg-can-print");
    if (window.UTG_PLAY && !window.UTG.canPlay(window.UTG_PLAY)) { deny(window.UTG_PLAY + "-workbook.html"); return; }
  }
})();
