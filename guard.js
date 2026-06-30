/* Shared access guard for tool pages.
   A page must, BEFORE loading this file, set:
       window.UTG_GUARD = "../";          // path back to the home page
       window.UTG_TOOL  = "pixel-art";    // which tool this page is
   and load  class-codes.js  first. If the saved class code is missing,
   disabled, or doesn't include this tool, the kid is sent to the home
   gate so the resources stay locked outside class.

   It also records per-code permissions as classes on <html>:
       utg-can-print  — the code's  print: true  (allowed to Print to PDF). */
(function () {
  function deny() { location.replace((window.UTG_GUARD || "../") + "?locked=1"); }
  try {
    var saved = (localStorage.getItem("utg_class_code") || "").trim().toUpperCase();
    var list = window.CLASS_CODES || [];
    var entry = null;
    for (var i = 0; i < list.length; i++) {
      if (list[i].enabled && String(list[i].code).trim().toUpperCase() === saved) { entry = list[i]; break; }
    }
    var ok = !!entry && (entry.tools === "all" ||
             (entry.tools && entry.tools.indexOf(window.UTG_TOOL) >= 0));
    if (!ok) { deny(); return; }
    if (entry.print) { document.documentElement.classList.add("utg-can-print"); }
  } catch (e) {
    deny();
  }
})();
