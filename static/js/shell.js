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
