/* The side panel's collapse state, per browser; and the Log out form on
 * the panel's last item. No inline handlers: the CSP forbids them. */
(function () {
  var app = document.querySelector(".app");
  var toggle = document.getElementById("collapse-toggle");
  if (!app || !toggle) { return; }
  var KEY = "shift-central.sidebar";
  try { if (localStorage.getItem(KEY) === "collapsed") { app.classList.add("is-collapsed"); } } catch (e) {}
  toggle.addEventListener("click", function () {
    app.classList.toggle("is-collapsed");
    try { localStorage.setItem(KEY, app.classList.contains("is-collapsed") ? "collapsed" : "open"); } catch (e) {}
  });
})();

/* Selects and date inputs marked data-submit-on-change submit their form
 * when changed (the Rota's weeks and from). No inline onchange: the CSP
 * forbids it. */
document.addEventListener("change", function (e) {
  var el = e.target.closest && e.target.closest("[data-submit-on-change]");
  if (el && el.form) { el.form.requestSubmit(); }
});

/* Log out (forms marked data-logout) first stops this phone's notifications:
 * it tells the server to forget the device, then drops the subscription, so a
 * phone handed to someone else shows nothing more of the last person's. The
 * idle sign-out after ten minutes does not, which is what lets notifications
 * reach a closed app. Log out still happens if any of this fails or stalls. */
document.addEventListener("submit", function (e) {
  var form = e.target;
  if (!form.hasAttribute || !form.hasAttribute("data-logout")) { return; }
  if (!("serviceWorker" in navigator) || !navigator.serviceWorker.getRegistration) { return; }
  e.preventDefault();
  var gone = false;
  function leave() { if (!gone) { gone = true; form.submit(); } }
  setTimeout(leave, 2000);
  var token = form.querySelector("input[name=csrfmiddlewaretoken]");
  navigator.serviceWorker.getRegistration().then(function (reg) {
    return reg && reg.pushManager ? reg.pushManager.getSubscription() : null;
  }).then(function (sub) {
    if (!sub) { return null; }
    return fetch(form.dataset.unsubscribeUrl, { method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": token ? token.value : "" },
      body: JSON.stringify({ endpoint: sub.endpoint }) })
      .catch(function () { return null; })
      .then(function () { return sub.unsubscribe(); });
  }).catch(function () { return null; }).then(leave);
});
