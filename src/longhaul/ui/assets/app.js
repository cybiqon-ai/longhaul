/* Longhaul — the interface.
 *
 * Vanilla, no framework, no build step. It renders from a single payload that
 * is either embedded in the page (a self-contained report, works offline) or
 * fetched from /api/data and refreshed over SSE (the live server). One
 * renderer, two delivery mechanisms — two would drift, and then one would lie.
 */
(function () {
  "use strict";

  var DATA = null;
  var VIEW = "overview";
  var FILTERS = { status: null, role: null, day: null, q: "" };
  var SORT = { key: "day", dir: 1 };
  var OPEN = {};

  var STATUSES = ["done", "in_progress", "failed", "parked", "halted", "pending", "skipped"];
  var LABEL = {
    done: "done", in_progress: "running", failed: "failed",
    parked: "parked", halted: "halted", pending: "pending", skipped: "skipped"
  };

  var VIEWS = [
    { group: "Delivery", items: [
      { id: "overview", label: "Overview", ico: "◧" },
      { id: "timeline", label: "Timeline", ico: "▤" },
      { id: "tasks", label: "Tasks", ico: "☰" }
    ]},
    { group: "Observability", items: [
      { id: "runs", label: "Agent runs", ico: "⟲" },
      { id: "spend", label: "Spend", ico: "$" }
    ]},
    { group: "Evidence", items: [
      { id: "proof", label: "Proof", ico: "▣" },
      { id: "risks", label: "Risks", ico: "!" }
    ]}
  ];

  /* ---------- helpers ---------- */
  function esc(v) {
    return String(v == null ? "" : v)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
  function el(id) { return document.getElementById(id); }
  function money(n) { return "$" + (Number(n) || 0).toFixed(2); }
  function dur(s) {
    s = Number(s) || 0;
    if (s < 60) return s.toFixed(0) + "s";
    return Math.floor(s / 60) + "m " + Math.round(s % 60) + "s";
  }
  function when(iso) { return iso ? String(iso).replace("T", " ").replace(/(\+.*|Z)$/, "") : "—"; }
  function statusCell(s) {
    return '<span class="status s-' + esc(s) + '"><i class="dot"></i>' + esc(LABEL[s] || s) + "</span>";
  }

  /* ---------- chrome ---------- */
  function renderSidebar() {
    var counts = DATA.counts || {};
    var badges = { tasks: DATA.tasks_total, runs: (DATA.runs || []).length, proof: (DATA.proof || []).length,
                   risks: (DATA.risk_flags || []).length };
    var html = '<div class="brand"><b>Longhaul</b><span>' + esc(DATA.profile || "") + "</span></div>";
    VIEWS.forEach(function (g) {
      html += '<div class="navgroup"><h3>' + esc(g.group) + "</h3>";
      g.items.forEach(function (v) {
        var n = badges[v.id];
        html += '<button class="nav" data-view="' + v.id + '" aria-current="' + (VIEW === v.id) + '">' +
          '<span class="ico">' + v.ico + "</span>" + esc(v.label) +
          (n ? '<span class="badge">' + n + "</span>" : "") + "</button>";
      });
      html += "</div>";
    });
    html += '<div class="sidefoot">' + esc(DATA.days_done) + " of " + esc(DATA.target_days) +
      " days · " + money(DATA.total_cost_usd) + "<br>updated " + esc(when(DATA.updated_at)) + "</div>";
    el("sidebar").innerHTML = html;
    void counts;
  }

  function renderTopbar() {
    var live = DATA.live;
    el("topbar").innerHTML =
      '<div class="crumbs"><b>' + esc(DATA.project) + '</b><span class="sep">/</span>' +
      '<span class="pill mono">day ' + esc(DATA.days_done) + "/" + esc(DATA.target_days) + "</span></div>" +
      '<div class="spacer"></div>' +
      '<span class="pill mono">' + money(DATA.total_cost_usd) + "</span>" +
      '<span class="pill"><i class="livedot' + (live ? " on" : "") + '"></i>' +
      (live ? "live" : "snapshot") + "</span>" +
      '<button class="pill" id="theme">theme</button>';
    el("theme").onclick = function () {
      var root = document.documentElement;
      var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try { localStorage.setItem("longhaul-theme", next); } catch (e) { /* private window */ }
    };
  }

  /* ---------- chart ---------- */
  function chart(series, key, label) {
    if (!series.length) return "";
    var max = Math.max.apply(null, series.map(function (d) { return d[key]; })) || 1;
    var w = 100 / series.length;
    var bars = series.map(function (d, i) {
      var h = (d[key] / max) * 78;
      var empty = d[key] === 0;
      return '<rect class="bar' + (empty ? " empty" : "") + '" x="' + (i * w + w * 0.18).toFixed(2) +
        '%" y="' + (86 - h).toFixed(1) + '" width="' + (w * 0.64).toFixed(2) + '%" height="' +
        Math.max(h, empty ? 2 : 1).toFixed(1) + '" rx="1.5"><title>day ' + d.day + ": " +
        (key === "cost_usd" ? money(d[key]) : d[key] + " runs") + "</title></rect>";
    }).join("");
    var ticks = series.filter(function (d, i) {
      return i === 0 || i === series.length - 1 || (i + 1) % 5 === 0;
    }).map(function (d) {
      var i = series.indexOf(d);
      return '<text class="axis" x="' + (i * w + w / 2).toFixed(2) + '%" y="99" text-anchor="middle">' +
        d.day + "</text>";
    }).join("");
    return '<div class="card chart"><svg viewBox="0 0 100 100" preserveAspectRatio="none" ' +
      'role="img" aria-label="' + esc(label) + '">' +
      '<line class="grid" x1="0" y1="86" x2="100" y2="86"/>' + bars + ticks + "</svg></div>";
  }

  /* ---------- filters ---------- */
  function chips(field, options) {
    return options.map(function (o) {
      var on = FILTERS[field] === o.value;
      return '<button class="chip" data-filter="' + field + '" data-value="' + esc(o.value) +
        '" aria-pressed="' + on + '">' + esc(o.label) +
        (o.n != null ? '<span class="n">' + o.n + "</span>" : "") + "</button>";
    }).join("");
  }

  function matches(task) {
    if (FILTERS.status && task.status !== FILTERS.status) return false;
    if (FILTERS.day && String(task.day) !== String(FILTERS.day)) return false;
    var q = FILTERS.q.trim().toLowerCase();
    if (!q) return true;
    return [task.id, task.title, task.kind, task.milestone, task.last_error]
      .join(" ").toLowerCase().indexOf(q) !== -1;
  }

  function sortRows(rows) {
    var k = SORT.key, d = SORT.dir;
    return rows.slice().sort(function (a, b) {
      var x = a[k], y = b[k];
      if (x == null) x = ""; if (y == null) y = "";
      if (typeof x === "number" && typeof y === "number") return (x - y) * d;
      return String(x).localeCompare(String(y)) * d;
    });
  }

  function headers(cols) {
    return cols.map(function (c) {
      var arrow = SORT.key === c.key ? (SORT.dir > 0 ? " ▲" : " ▼") : "";
      return '<th data-sort="' + c.key + '">' + esc(c.label) +
        '<span class="dir">' + arrow + "</span></th>";
    }).join("");
  }

  /* ---------- views ---------- */
  function viewOverview() {
    var c = DATA.counts;
    var tiles = [
      ["done", c.done], ["running", c.in_progress], ["failed", c.failed],
      ["parked", c.parked], ["halted", c.halted], ["to go", c.pending],
      ["agent runs", (DATA.runs || []).length], ["spent", money(DATA.total_cost_usd)]
    ].map(function (t) {
      var cls = { done: "done", failed: "failed", parked: "parked", halted: "halted" }[t[0]] || "";
      return '<div class="tile ' + cls + '"><b>' + esc(t[1]) + "</b><span>" + esc(t[0]) + "</span></div>";
    }).join("");

    var attention = DATA.tasks.filter(function (t) {
      return t.status === "parked" || t.status === "halted" || t.status === "failed";
    });

    return '<div class="head"><h1>Overview</h1></div>' +
      '<p class="sub">' + esc(DATA.tasks_total) + " tasks over " + esc(DATA.target_days) +
      " days · <code>" + esc(DATA.profile) + "</code></p>" +
      '<div class="tiles">' + tiles + "</div>" +
      "<h2>Spend per day</h2>" + chart(DATA.series, "cost_usd", "cost per day") +
      (attention.length
        ? "<h2>Needs you</h2>" + taskTable(attention, true)
        : '<h2>Needs you</h2><div class="card"><div class="empty">Nothing is waiting on a human.</div></div>');
  }

  function taskTable(rows, compact) {
    if (!rows.length) return '<div class="card"><div class="empty">Nothing matches.</div></div>';
    var cols = compact
      ? [{ key: "day", label: "Day" }, { key: "status", label: "Status" }, { key: "title", label: "Task" }]
      : [{ key: "day", label: "Day" }, { key: "id", label: "ID" }, { key: "status", label: "Status" },
         { key: "kind", label: "Kind" }, { key: "title", label: "Task" },
         { key: "attempts", label: "Try" }, { key: "cost_usd", label: "Cost" }];
    var body = sortRows(rows).map(function (t) {
      var open = OPEN[t.id];
      var cells = compact
        ? '<td class="num dim">day ' + t.day + "</td><td>" + statusCell(t.status) + "</td><td><b>" +
          esc(t.title) + "</b>" + (t.last_error ? '<div class="crit">' + esc(t.last_error.split("\n")[0]) + "</div>" : "") + "</td>"
        : '<td class="num dim">' + t.day + '</td><td class="num">' + esc(t.id) + "</td><td>" +
          statusCell(t.status) + '</td><td><span class="tag">' + esc(t.kind) + "</span>" +
          (t.needs_human ? ' <span class="tag warn">needs you</span>' : "") +
          (t.risk !== "low" ? ' <span class="tag risk">' + esc(t.risk) + "</span>" : "") +
          "</td><td><b>" + esc(t.title) + "</b></td>" +
          '<td class="num dim">' + (t.attempts || "—") + '</td><td class="num">' +
          (t.cost_usd ? money(t.cost_usd) : "—") + "</td>";
      var row = '<tr class="expandable" data-task="' + esc(t.id) + '">' + cells + "</tr>";
      if (!open) return row;
      return row + '<tr class="detail"><td colspan="' + cols.length + '">' + taskDetail(t) + "</td></tr>";
    }).join("");
    return '<div class="wrap"><table><thead><tr>' + headers(cols) + "</tr></thead><tbody>" +
      body + "</tbody></table></div>";
  }

  function taskDetail(t) {
    var dl = "<dl>";
    dl += "<dt>Acceptance criteria</dt><dd><ul class='crit'>" +
      t.criteria.map(function (c) { return "<li>" + esc(c) + "</li>"; }).join("") + "</ul></dd>";
    if (t.milestone) dl += "<dt>Milestone</dt><dd>" + esc(t.milestone) + "</dd>";
    if (t.depends_on.length) dl += "<dt>Depends on</dt><dd>" + esc(t.depends_on.join(", ")) + "</dd>";
    if (t.proof_expect) dl += "<dt>Proof must show</dt><dd>" + esc(t.proof_expect) + "</dd>";
    if (t.proof_detail) dl += "<dt>Proof result</dt><dd>" + esc(t.proof_detail) + "</dd>";
    if (t.branch) dl += "<dt>Branch</dt><dd><code>" + esc(t.branch) + "</code>" +
      (t.commit_sha ? " · <code>" + esc(t.commit_sha) + "</code>" : "") + "</dd>";
    if (t.pr_url) dl += '<dt>Pull request</dt><dd><a href="' + esc(t.pr_url) + '">#' +
      esc(t.pr_number) + "</a></dd>";
    if (t.started_at) dl += "<dt>Started</dt><dd>" + esc(when(t.started_at)) + "</dd>";
    if (t.finished_at) dl += "<dt>Finished</dt><dd>" + esc(when(t.finished_at)) + "</dd>";
    dl += "</dl>";
    if (t.findings.length) dl += "<pre>" + esc(t.findings.join("\n")) + "</pre>";
    if (t.last_error) dl += "<pre>" + esc(t.last_error) + "</pre>";
    return dl;
  }

  function viewTasks() {
    var counts = {};
    DATA.tasks.forEach(function (t) { counts[t.status] = (counts[t.status] || 0) + 1; });
    var opts = [{ value: "", label: "All", n: DATA.tasks.length }].concat(
      STATUSES.filter(function (s) { return counts[s]; })
        .map(function (s) { return { value: s, label: LABEL[s], n: counts[s] }; }));
    var rows = DATA.tasks.filter(matches);
    return '<div class="head"><h1>Tasks</h1></div>' +
      '<p class="sub">' + rows.length + " of " + DATA.tasks_total + " shown</p>" +
      '<div class="toolbar"><input class="search" id="q" placeholder="Search tasks — title, id, kind, error" value="' +
      esc(FILTERS.q) + '">' + chips("status", opts) + "</div>" + taskTable(rows, false);
  }

  function viewTimeline() {
    var byDay = {};
    DATA.tasks.forEach(function (t) { (byDay[t.day] = byDay[t.day] || []).push(t); });
    var rows = DATA.series.map(function (d) {
      var tasks = byDay[d.day] || [];
      if (!tasks.length) {
        return '<tr><td class="num dim">day ' + d.day + '</td><td class="dim">—</td>' +
          '<td class="dim">slack — no task planned</td><td class="num dim">—</td></tr>';
      }
      return tasks.map(function (t, i) {
        return "<tr>" + (i === 0
          ? '<td class="num dim" rowspan="' + tasks.length + '">day ' + d.day + "</td>" : "") +
          "<td>" + statusCell(t.status) + "</td><td><b>" + esc(t.title) + "</b>" +
          '<div class="crit">' + esc(t.milestone) + "</div></td>" +
          '<td class="num">' + (t.cost_usd ? money(t.cost_usd) : "—") + "</td></tr>";
      }).join("");
    }).join("");
    return '<div class="head"><h1>Timeline</h1></div>' +
      '<p class="sub">Every day from 1 to ' + esc(DATA.target_days) +
      ", so gaps show as gaps.</p>" + chart(DATA.series, "runs", "agent runs per day") +
      '<div class="wrap" style="margin-top:.75rem"><table><thead><tr><th>Day</th><th>Status</th>' +
      "<th>Task</th><th>Cost</th></tr></thead><tbody>" + rows + "</tbody></table></div>";
  }

  function viewRuns() {
    var runs = DATA.runs || [];
    var roles = {};
    runs.forEach(function (r) { roles[r.role] = (roles[r.role] || 0) + 1; });
    var opts = [{ value: "", label: "All roles", n: runs.length }].concat(
      Object.keys(roles).sort().map(function (r) { return { value: r, label: r, n: roles[r] }; }));
    var q = FILTERS.q.trim().toLowerCase();
    var rows = runs.filter(function (r) {
      if (FILTERS.role && r.role !== FILTERS.role) return false;
      if (!q) return true;
      return [r.task, r.role, r.title, r.session_id].join(" ").toLowerCase().indexOf(q) !== -1;
    });
    var body = rows.map(function (r) {
      return "<tr><td class='num dim'>" + esc(when(r.at)) + "</td>" +
        '<td><span class="tag">' + esc(r.role) + "</span></td>" +
        "<td class='num'>" + esc(r.task) + "</td>" +
        "<td>" + esc(r.title || "") + "</td>" +
        "<td class='num dim'>" + esc(r.attempt) + "</td>" +
        "<td class='num'>" + dur(r.duration_s) + "</td>" +
        "<td class='num'>" + money(r.cost_usd) + "</td>" +
        "<td>" + statusCell(r.ok ? "done" : "failed") + "</td>" +
        "<td class='num dim'>" + esc((r.session_id || "—").slice(0, 8)) + "</td></tr>";
    }).join("");
    return '<div class="head"><h1>Agent runs</h1></div>' +
      '<p class="sub">Every invocation, from <code>.longhaul/ledger.jsonl</code>. ' +
      "Append-only, so the bill is auditable after the fact.</p>" +
      '<div class="toolbar"><input class="search" id="q" placeholder="Search runs — task, role, session" value="' +
      esc(FILTERS.q) + '">' + chips("role", opts) + "</div>" +
      (rows.length
        ? '<div class="wrap"><table><thead><tr><th>Time</th><th>Role</th><th>Task</th><th>Title</th>' +
          "<th>Try</th><th>Duration</th><th>Cost</th><th>Result</th><th>Session</th>" +
          "</tr></thead><tbody>" + body + "</tbody></table></div>"
        : '<div class="card"><div class="empty">No agent has run yet.</div></div>');
  }

  function viewSpend() {
    var byRole = {};
    (DATA.runs || []).forEach(function (r) {
      byRole[r.role] = byRole[r.role] || { n: 0, cost: 0, secs: 0 };
      byRole[r.role].n++; byRole[r.role].cost += r.cost_usd; byRole[r.role].secs += r.duration_s;
    });
    var rows = Object.keys(byRole).sort(function (a, b) { return byRole[b].cost - byRole[a].cost; })
      .map(function (role) {
        var v = byRole[role];
        return '<tr><td><span class="tag">' + esc(role) + "</span></td>" +
          "<td class='num'>" + v.n + "</td><td class='num'>" + money(v.cost) + "</td>" +
          "<td class='num dim'>" + dur(v.secs) + "</td></tr>";
      }).join("");
    return '<div class="head"><h1>Spend</h1></div>' +
      '<p class="sub">Total ' + money(DATA.total_cost_usd) +
      " across " + (DATA.runs || []).length + " agent runs.</p>" +
      chart(DATA.series, "cost_usd", "cost per day") +
      "<h2>By role</h2>" +
      (rows
        ? '<div class="wrap"><table><thead><tr><th>Role</th><th>Runs</th><th>Cost</th>' +
          "<th>Time</th></tr></thead><tbody>" + rows + "</tbody></table></div>"
        : '<div class="card"><div class="empty">Nothing spent yet.</div></div>');
  }

  function viewProof() {
    var shots = (DATA.proof || []).filter(function (a) { return a.is_image; });
    var others = (DATA.proof || []).filter(function (a) { return !a.is_image; });
    var note = DATA.proof_linked
      ? '<div class="note">' + DATA.proof_linked + " image(s) too large to embed are linked " +
        "instead — they need this file's <code>.longhaul/</code> directory alongside it.</div>"
      : "";
    var tiles = shots.map(function (a) {
      return '<figure class="shot"><a href="' + esc(a.href) + '">' +
        '<img src="' + esc(a.src) + '" alt="day ' + esc(a.day) + " " + esc(a.task) + '" loading="lazy">' +
        "</a><figcaption><span>day " + esc(a.day) + " · " + esc(a.task) + "</span><span>" +
        Math.round(a.size / 1024) + " KB</span></figcaption></figure>";
    }).join("");
    var list = others.map(function (a) {
      return '<li><a href="' + esc(a.href) + '">day ' + esc(a.day) + " · " + esc(a.name) +
        "</a> <span class='tag'>" + Math.round(a.size / 1024) + " KB</span></li>";
    }).join("");
    return '<div class="head"><h1>Proof</h1></div>' +
      '<p class="sub">What each day actually produced. Tests passing is not evidence an ' +
      "application works.</p>" + note +
      (shots.length ? '<div class="gallery">' + tiles + "</div>"
        : '<div class="card"><div class="empty">No proof artefacts yet. ' +
          "A day's proof lands in <code>.longhaul/proof/day-NN/</code>.</div></div>") +
      (list ? "<h2>Other artefacts</h2><ul class='crit'>" + list + "</ul>" : "");
  }

  function viewRisks() {
    var flags = DATA.risk_flags || [];
    return '<div class="head"><h1>Risks</h1></div>' +
      '<p class="sub">Written by the Planner up front, not discovered later.</p>' +
      (flags.length
        ? flags.map(function (f) { return '<div class="note">' + esc(f) + "</div>"; }).join("")
        : '<div class="card"><div class="empty">The plan declared no risk flags.</div></div>');
  }

  /* ---------- routing ---------- */
  var RENDER = {
    overview: viewOverview, timeline: viewTimeline, tasks: viewTasks,
    runs: viewRuns, spend: viewSpend, proof: viewProof, risks: viewRisks
  };

  function render() {
    if (!DATA) return;
    renderSidebar();
    renderTopbar();
    el("main").innerHTML = (RENDER[VIEW] || viewOverview)() +
      '<div class="foot">Generated by <a href="https://github.com/cybiqon-ai/longhaul">Longhaul</a> ' +
      "from <code>.longhaul/</code>. No tracking, no network — " +
      (DATA.live ? "served from your own machine." : "this file is the whole page.") + "</div>";
    wire();
  }

  function wire() {
    document.querySelectorAll("[data-view]").forEach(function (b) {
      b.onclick = function () {
        VIEW = b.getAttribute("data-view");
        FILTERS.status = FILTERS.role = null; FILTERS.q = "";
        try { location.hash = VIEW; } catch (e) { /* file:// */ }
        render();
      };
    });
    document.querySelectorAll("[data-filter]").forEach(function (b) {
      b.onclick = function () {
        var f = b.getAttribute("data-filter"), v = b.getAttribute("data-value");
        FILTERS[f] = (v === "" || FILTERS[f] === v) ? null : v;
        render();
      };
    });
    document.querySelectorAll("[data-sort]").forEach(function (th) {
      th.onclick = function () {
        var k = th.getAttribute("data-sort");
        if (SORT.key === k) SORT.dir *= -1; else { SORT.key = k; SORT.dir = 1; }
        render();
      };
    });
    document.querySelectorAll("[data-task]").forEach(function (tr) {
      tr.onclick = function () {
        var id = tr.getAttribute("data-task");
        OPEN[id] = !OPEN[id];
        render();
      };
    });
    var q = el("q");
    if (q) {
      q.oninput = function () { FILTERS.q = q.value; render(); };
      if (FILTERS.q) { q.focus(); q.setSelectionRange(q.value.length, q.value.length); }
    }
  }

  /* ---------- boot ---------- */
  function applyTheme() {
    try {
      var saved = localStorage.getItem("longhaul-theme");
      if (saved) document.documentElement.setAttribute("data-theme", saved);
    } catch (e) { /* private window, or file:// with storage blocked */ }
  }

  function boot(payload) {
    DATA = payload;
    var hash = (location.hash || "").replace("#", "");
    if (RENDER[hash]) VIEW = hash;
    render();
    if (DATA.live) connect();
  }

  function connect() {
    if (!window.EventSource) return;
    var backoff = 1000;
    (function open() {
      var src = new EventSource("/events");
      src.addEventListener("open", function () { backoff = 1000; });
      src.addEventListener("update", function () {
        fetch("/api/data", { cache: "no-store" })
          .then(function (r) { return r.ok ? r.json() : null; })
          .then(function (next) { if (next) { DATA = next; render(); } })
          .catch(function () { /* a failed refresh must not break the page */ });
      });
      src.addEventListener("error", function () {
        src.close();
        setTimeout(open, backoff);
        backoff = Math.min(backoff * 2, 30000);
      });
    })();
  }

  applyTheme();
  var embedded = document.getElementById("longhaul-data");
  if (embedded) {
    boot(JSON.parse(embedded.textContent));
  } else {
    fetch("/api/data", { cache: "no-store" }).then(function (r) { return r.json(); }).then(boot);
  }
})();
