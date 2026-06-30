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

   This is a simple gate, NOT real security — the codes are public
   in this file. It just keeps kids out of the resources outside class.
   (Note: browsers may cache this file for a few minutes, so a lock
   can take a little while to take effect at home.)
   ============================================================ */
window.CLASS_CODES = [
  { code: "QWER", label: "Students (all resources)", enabled: true, tools: "all", print: false },
  { code: "ASDF", label: "Teacher (can print PDFs)", enabled: true, tools: "all", print: true },
];
