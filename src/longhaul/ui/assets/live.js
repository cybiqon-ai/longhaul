// Live updates without polling from the browser.
//
// The server watches .longhaul/ and pushes an event when it changes; this
// re-fetches the body and swaps it in place, so scroll position and the page's
// identity survive. A full reload on every state write would make the page
// unusable to actually watch.
(function () {
  var main = document.querySelector("main");
  var backoff = 1000;

  function refresh() {
    fetch("/fragment", { cache: "no-store" })
      .then(function (r) { return r.ok ? r.text() : null; })
      .then(function (html) {
        if (!html) return;
        var next = document.createElement("div");
        next.innerHTML = html;
        var replacement = next.querySelector("main");
        if (replacement && main) { main.replaceWith(replacement); main = replacement; }
      })
      .catch(function () { /* a failed refresh must not break the page */ });
  }

  function connect() {
    var source = new EventSource("/events");

    source.addEventListener("update", function () { backoff = 1000; refresh(); });
    source.addEventListener("open", function () { backoff = 1000; });

    source.addEventListener("error", function () {
      // The orchestrator restarting, or the server being stopped, is normal.
      // Back off rather than hammering a socket that is not there.
      source.close();
      setTimeout(connect, backoff);
      backoff = Math.min(backoff * 2, 30000);
    });
  }

  if (window.EventSource) connect();
})();
