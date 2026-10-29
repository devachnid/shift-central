/* Pop-ups (FindMyShift's profile, time-off and department windows) are
 * HTML the server renders, fetched into #dialog.
 *
 *  - <a data-dialog href="…"> or <button data-dialog data-url="…"> fetches
 *    the URL (GET, same origin, X-Requested-With) and puts the body in
 *    #dialog, focusing the first field.
 *  - <form data-dialog-form> inside posts by fetch. A 200 replaces the
 *    dialog with the response (a form shown again with its errors); a JSON
 *    {"redirect": url} follows it; anything else shows a flash.
 *  - [data-dialog-close], Escape and a click on the backdrop close it.
 *  - Tab stays inside while it is open; focus returns to the opener after.
 */
(function () {
  var dialog = document.getElementById("dialog");
  if (!dialog) { return; }
  var FOCUSABLE = 'a[href], button:not([disabled]), select:not([disabled]), textarea:not([disabled]), input:not([type="hidden"]):not([disabled]), [tabindex]:not([tabindex="-1"])';
  var opener = null;
  var csrf = document.querySelector('meta[name="csrf-token"]').content;

  function open() { return dialog.childElementCount > 0; }
  function close() { dialog.innerHTML = ""; if (opener && opener.isConnected) { opener.focus({ preventScroll: true }); } opener = null; }
  function focusFirst() {
    var first = dialog.querySelector("[autofocus]") || dialog.querySelector(FOCUSABLE);
    if (first) { first.focus(); }
  }
  function show(html) { dialog.innerHTML = html; focusFirst(); }

  function load(url, from) {
    opener = from;
    fetch(url, { headers: { "X-Requested-With": "fetch" }, credentials: "same-origin" })
      .then(function (r) { return r.text(); }).then(show);
  }

  document.addEventListener("click", function (e) {
    var t = e.target.closest && e.target.closest("[data-dialog]");
    if (t) { e.preventDefault(); load(t.getAttribute("href") || t.dataset.url, t); return; }
    if (e.target.closest && e.target.closest("[data-dialog-close]")) { e.preventDefault(); close(); return; }
    if (e.target === dialog) { close(); }
  });

  document.addEventListener("submit", function (e) {
    var form = e.target.closest && e.target.closest("form[data-dialog-form]");
    if (!form) { return; }
    e.preventDefault();
    var data = new FormData(form);
    if (e.submitter && e.submitter.name) { data.append(e.submitter.name, e.submitter.value); }
    fetch(form.action, { method: "POST", body: data, credentials: "same-origin",
                         headers: { "X-CSRFToken": csrf, "X-Requested-With": "fetch" } })
      .then(function (r) {
        var type = r.headers.get("Content-Type") || "";
        if (type.indexOf("application/json") === 0) {
          return r.json().then(function (j) { if (j.redirect) { window.location.assign(j.redirect); } });
        }
        return r.text().then(show);
      });
  });

  document.addEventListener("keydown", function (e) {
    if (!open()) { return; }
    if (e.key === "Escape") { e.preventDefault(); close(); return; }
    if (e.key !== "Tab") { return; }
    var items = [].filter.call(dialog.querySelectorAll(FOCUSABLE), function (el) { return el.offsetParent !== null; });
    if (!items.length) { return; }
    var first = items[0], last = items[items.length - 1];
    if (!dialog.contains(document.activeElement)) { e.preventDefault(); first.focus(); }
    else if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  });

  // Tabs inside a dialog (the profile's General / Display / …) load their
  // panel the same way, keeping the dialog open.
  document.addEventListener("click", function (e) {
    var tab = e.target.closest && e.target.closest("#dialog a.tab");
    if (tab) { e.preventDefault(); fetch(tab.href, { headers: { "X-Requested-With": "fetch" }, credentials: "same-origin" }).then(function (r) { return r.text(); }).then(show); }
  });
})();
