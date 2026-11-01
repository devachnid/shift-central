/* The Notifications page: ask permission, subscribe this device and tell the
 * server, or undo it. A static file because the CSP allows no inline script. */
(function () {
  "use strict";
  var card = document.getElementById("push-card");
  if (!card) { return; }
  var csrf = document.querySelector('meta[name="csrf-token"]').content;
  var statusEl = card.querySelector("[data-push-status]");
  var hint = card.querySelector("[data-push-hint]");
  var turnOn = card.querySelector("[data-push-on]");
  var turnOff = card.querySelector("[data-push-off]");
  var ios = /iPhone|iPad|iPod/.test(navigator.userAgent);
  var standalone = window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone === true;
  var supported = "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;

  function show(el, yes) { el.hidden = !yes; }
  function say(text) { statusEl.textContent = text; }
  function keyBytes(base64) {
    var padded = base64 + "=".repeat((4 - base64.length % 4) % 4);
    var raw = atob(padded.replace(/-/g, "+").replace(/_/g, "/"));
    var out = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i++) { out[i] = raw.charCodeAt(i); }
    return out;
  }
  function post(url, body) {
    return fetch(url, { method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf }, body: JSON.stringify(body) });
  }
  function registration() {
    return navigator.serviceWorker.register("/sw.js").then(function () { return navigator.serviceWorker.ready; });
  }

  function refresh() {
    show(turnOn, false); show(turnOff, false); show(hint, false);
    if (ios && !standalone) { say(""); show(hint, true); return Promise.resolve(); }
    if (!supported) { say("This browser can't receive notifications."); return Promise.resolve(); }
    if (Notification.permission === "denied") {
      say("Notifications are blocked for this site in your browser's settings."); return Promise.resolve();
    }
    return registration().then(function (reg) { return reg.pushManager.getSubscription(); }).then(function (sub) {
      if (!sub) { say("Notifications are off for this device."); show(turnOn, true); return null; }
      // The phone holding a subscription is not enough: the server must hold it
      // too, for whoever is signed in now. Send it on every visit; a phone the
      // server refused, or one last used by someone else, is put right here.
      return tell(sub).then(function (data) {
        if (data.created) { window.location.assign(window.location.href); return; }   // list the device
        say("Notifications are on for this device."); show(turnOff, true);
      }, function (e) { say(e.message); show(turnOff, true); });
    });
  }
  function failure(text) { var e = new Error(text); e.forPeople = true; return e; }
  function tell(sub) {   // the server's own sentence when it refuses
    return post(card.dataset.subscribeUrl, sub.toJSON()).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (data) {
        if (!r.ok) { throw failure(data.error || "This phone couldn't be registered. Try again."); }
        return data;
      });
    }, function () { throw failure("Shift Central couldn't be reached. Try again."); });
  }

  turnOn.addEventListener("click", function () {
    turnOn.disabled = true;
    Notification.requestPermission().then(function (permission) {
      if (permission !== "granted") { return null; }
      return registration().then(function (reg) {
        return reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes(card.dataset.key) });
      }).then(tell).then(function () { window.location.assign(window.location.href); });
    }).catch(function (e) { say(e && e.forPeople ? e.message : "That didn't work. Try again."); })
      .then(function () { turnOn.disabled = false; });
  });

  turnOff.addEventListener("click", function () {
    turnOff.disabled = true;
    registration().then(function (reg) { return reg.pushManager.getSubscription(); }).then(function (sub) {
      if (!sub) { return null; }
      return post(card.dataset.unsubscribeUrl, { endpoint: sub.endpoint }).then(function () { return sub.unsubscribe(); });
    }).then(function () { window.location.assign(window.location.href); })
      .catch(function () { say("That didn't work. Try again."); turnOff.disabled = false; });
  });

  refresh().catch(function () { say("This device can't receive notifications."); });
})();
