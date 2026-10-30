/* Pop-ups (FindMyShift's profile, time-off and department windows) are
 * HTML the server renders, fetched into #dialog.
 *
 *  - <a data-dialog href="…"> or <button data-dialog data-url="…"> fetches
 *    the URL (GET, same origin, X-Requested-With) and puts the body in
 *    #dialog, focusing the first field.
 *  - <form data-dialog-form> inside posts by fetch, its buttons disabled
 *    while the post is in flight. A 200 replaces the dialog with the response
 *    (a form shown again with its errors); a JSON {"redirect": url} follows it, and
 *    {"refresh": true} closes the dialog and fires shift-central:refresh.
 *  - Failures never put an error page in the dialog. A redirect to the log-in
 *    page (the session ended) or a non-2xx answer shows a "Something went
 *    wrong" dialog for a fetch, or a flash at the top of the form (which stays
 *    on screen, buttons re-enabled) for a post; a network error says the
 *    server couldn't be reached.
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
    // The header's close button is first in the DOM but never the right
    // place to start typing; it is only the fallback.
    var first = dialog.querySelector("[autofocus]");
    if (!first) {
      first = [].filter.call(dialog.querySelectorAll(FOCUSABLE), function (el) { return !el.classList.contains("close"); })[0]
        || dialog.querySelector(".close");
    }
    if (first) { first.focus(); }
  }
  // Islands (the colour picker) inside new dialog HTML mount on this event.
  function mounted() { document.dispatchEvent(new CustomEvent("shift-central:mounted", { detail: dialog })); }
  function show(html) { dialog.innerHTML = html; mounted(); focusFirst(); }

  var UNREACHABLE = "The server couldn't be reached. Check your connection and try again.";

  // What went wrong with a response, or null when it is fine. A session that
  // ended answers with a redirect to the log-in page, which fetch follows.
  function problem(r) {
    if (r.redirected && new URL(r.url).pathname.indexOf("/accounts/login/") === 0) {
      return { message: "Your session ended. Sign in again.", signIn: true };
    }
    if (!r.ok) {
      return { message: "That didn't work (HTTP " + r.status + "). Reload the page and try again." };
    }
    return null;
  }

  function flash(p) {
    var el = document.createElement("p");
    el.className = "flash flash-error";
    el.setAttribute("role", "alert");
    el.setAttribute("data-dialog-error", "");
    el.textContent = p.message;
    if (p.signIn) {
      var a = document.createElement("a");
      // Back to the page the dialog was opened on, once signed in again.
      a.href = "/accounts/login/?next=" + encodeURIComponent(location.pathname + location.search);
      a.textContent = "Sign in";
      el.appendChild(document.createTextNode(" "));
      el.appendChild(a);
    }
    return el;
  }

  // A whole dialog of its own, for a fetch that never produced one.
  function fail(p) {
    dialog.innerHTML = '<div class="dialog"><div class="dialog-head"><span id="dialog-title">Something went wrong</span>'
      + '<button type="button" class="close" data-dialog-close aria-label="Close">\u00d7</button></div>'
      + '<div class="dialog-body"></div></div>';
    dialog.querySelector(".dialog-body").appendChild(flash(p));
    mounted();
    focusFirst();
  }

  // The same message above a form that stays on screen, so nothing typed is lost.
  function failInForm(form, p) {
    var body = form.closest(".dialog-body");
    if (!body) { fail(p); return; }
    var old = body.querySelector("[data-dialog-error]");
    if (old) { old.remove(); }
    body.insertBefore(flash(p), body.firstChild);
  }

  function get(url) {
    return fetch(url, { headers: { "X-Requested-With": "fetch" }, credentials: "same-origin" })
      .then(function (r) {
        var p = problem(r);
        if (p) { fail(p); return; }
        return r.text().then(show);
      })
      .catch(function () { fail({ message: UNREACHABLE }); });
  }

  function load(url, from) {
    opener = from;
    get(url);
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
    var buttons = form.querySelectorAll('button, input[type="submit"]');
    function setBusy(busy) { [].forEach.call(buttons, function (b) { b.disabled = busy; }); }
    setBusy(true);
    fetch(form.action, { method: "POST", body: data, credentials: "same-origin",
                         headers: { "X-CSRFToken": csrf, "X-Requested-With": "fetch" } })
      .then(function (r) {
        var p = problem(r);
        if (p) { setBusy(false); failInForm(form, p); return; }
        var type = r.headers.get("Content-Type") || "";
        if (type.indexOf("application/json") === 0) {
          return r.json().then(function (j) {
            if (j.redirect) { window.location.assign(j.redirect); return; }
            if (j.refresh) { close(); document.dispatchEvent(new CustomEvent("shift-central:refresh")); return; }
            setBusy(false);
          });
        }
        return r.text().then(show);
      })
      .catch(function () { setBusy(false); failInForm(form, { message: UNREACHABLE }); });
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
    if (tab) { e.preventDefault(); get(tab.href); }
  });
})();
