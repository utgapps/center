/* ============================================================
   CLASS CODES  —  edit this file to control who gets in.

   Kids enter a 4-letter code on the home page. A code only works
   while  enabled: true . To lock a class out (after class / at home)
   set its  enabled  to  false  and push. To let them in, set it  true .

     code    : the 4 letters kids type (not case sensitive)
     label   : a name just for you (shown after they sign in)
     enabled : true = works now,  false = locked
     tools   : "all", or a list of what this code unlocks —
               "pixel-art"  and/or  "camp"
     print   : true = may use "Print to PDF" on the coding workbooks;
               leave it out (or false) to block printing for that code.
     play    : who may PLAY the finished games (the "Play" buttons).
               "all", a list of game slugs, or [] / leave out for none.
               Game slugs:
                 catch whack flappy subway geo crossy pong brick doodle
                 shooter heli slice dodge stack fishing rhythm lander
                 platformer cookie pacman drift
               e.g.  play: ["flappy","drift"]  lets them play only those.

   This is a simple gate, NOT real security — the codes are public
   in this file. It just keeps kids out of the resources outside class.
   (Note: browsers may cache this file for a few minutes, so a lock
   can take a little while to take effect at home.)
   ============================================================ */
window.CLASS_CODES = [
  { code: "QWER", label: "Students",  enabled: false, tools: "all", print: false, play: [] },
  { code: "ASDF", label: "Teacher",   enabled: true, tools: "all", print: true,  play: "all" },
];
