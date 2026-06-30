/* Shared access guard for tool pages.
   A page must, BEFORE loading this file, set:
       window.UTG_GUARD = "../";          // path back to the home page
       window.UTG_TOOL  = "pixel-art";    // which tool this page is
   and load  class-codes.js  first. If the saved class code is missing,
   disabled, or doesn't include this tool, the kid is sent to the home
   gate so the tools stay locked outside class. */
(function () {
  try {
    var saved = (localStorage.getItem("utg_class_code") || "").trim().toUpperCase();
    var list = window.CLASS_CODES || [];
    var entry = null;
    for (var i = 0; i < list.length; i++) {
      if (list[i].enabled && String(list[i].code).trim().toUpperCase() === saved) { entry = list[i]; break; }
    }
    var ok = !!entry && (entry.tools === "all" ||
             (entry.tools && entry.tools.indexOf(window.UTG_TOOL) >= 0));
    if (!ok) location.replace((window.UTG_GUARD || "../") + "?locked=1");
  } catch (e) {
    location.replace((window.UTG_GUARD || "../") + "?locked=1");
  }
})();
