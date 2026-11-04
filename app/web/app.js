(function () {
  var $ = function (id) { return document.getElementById(id); };
  var form = $("start"), go = $("go"), problem = $("problem");
  var state = { reviewId: null, parts: {}, passcode: "", cols: {}, byId: {}, chips: {}, shown: {} };
  var calm = matchMedia("(prefers-reduced-motion: reduce)").matches;
  var NS = "http://www.w3.org/2000/svg";

  // Answer encoding: a word, a mark and an underline style. Colour is never the only carrier.
  var STROKES = {
    tick: "M3.5 13.2C5.6 15 7.2 16.8 8.6 19.6 11.4 12.6 15.4 7.2 20.8 3.8",
    circle: "M12.4 3.1C6.8 2.4 2.7 7 3.3 12.5c.6 5.5 6.2 8.7 11.2 7.5 5-1.2 7.1-6 6-10.4-1-4-4.8-6.3-9.4-5.8",
    caret: "M3.8 19.6C7.2 14 9.6 9.6 12 5.4c2.6 4.6 5.2 9.2 8.2 14.2",
    bracket: "M15.4 3.6H8.6c-.7 0-1.1.3-1.1.9v15c0 .6.4.9 1.1.9h6.8",
    question: "M8.4 9.2C8.2 5.6 15.8 5.4 15.6 9.4c-.1 2.8-3.7 3-3.6 6.2M12 19.6v.1"
  };
  var ANSWER = {
    supported: { word: "Supported", cls: "green", m: "tick" },
    contradicted: { word: "Contradicted", cls: "red", m: "circle" },
    weakened: { word: "Qualified", cls: "amber", m: "caret" },
    not_found: { word: "Not in these documents", cls: "slate", m: "bracket" },
    cannot_tell: { word: "Can't tell", cls: "grey", m: "question" },
    error: { word: "Could not check", cls: "grey", m: "question" }
  };
  var TICK = "M3.5 13.2C5.6 15 7.2 16.8 8.6 19.6 11.4 12.6 15.4 7.2 20.8 3.8";

  function el(tag, cls, text) { var n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; }
  function svg(d, cls) {
    var s = document.createElementNS(NS, "svg"), p = document.createElementNS(NS, "path");
    s.setAttribute("viewBox", "0 0 24 24"); s.setAttribute("width", "20"); s.setAttribute("height", "20"); s.setAttribute("aria-hidden", "true");
    if (cls) s.setAttribute("class", cls);
    p.setAttribute("d", d); p.setAttribute("fill", "none"); p.setAttribute("stroke", "currentColor");
    p.setAttribute("stroke-width", "2"); p.setAttribute("stroke-linecap", "round"); p.setAttribute("stroke-linejoin", "round");
    s.appendChild(p); return s;
  }
  function say(text) { $("status").textContent = text; }
  function plural(n, w) { return n + " " + w + (n === 1 ? "" : "s"); }
  function role(r) { r = (r || "").replace(/_/g, " "); return r ? r.charAt(0).toUpperCase() + r.slice(1) : "Document"; }
  function tidy(name) { return name.replace(/\.(pdf|png|jpe?g)$/i, "").replace(/[_]+/g, " "); }
  function latest(text) { $("latest").textContent = text; }
  function note(key, text, cls) {
    var ul = $("notes"), li = ul.querySelector('[data-key="' + key + '"]');
    if (!li) { li = el("li"); li.dataset.key = key; ul.appendChild(li); }
    li.textContent = text; li.className = cls || "";
  }

  function showStart(text) {
    $("entrance").hidden = false; $("live").hidden = true; $("result").hidden = true;
    if (text) { problem.textContent = text; problem.hidden = false; say(text); }
  }
  function reset(claim) {
    ["ticks", "cols", "shared", "parts", "notes"].forEach(function (id) { $(id).textContent = ""; });
    $("threads").textContent = ""; $("receipt").hidden = true; $("reopen").hidden = true; latest("");
    $("readgrid").classList.remove("collapsed"); $("map").classList.remove("deciding");
    state.parts = {}; state.cols = {}; state.byId = {}; state.chips = {}; state.shown = {};
    var c = $("claim-line"); c.textContent = claim; c.className = "claim reading";
    problem.hidden = true; $("entrance").hidden = true; $("live").hidden = false; $("result").hidden = true;
    window.scrollTo(0, 0);
  }
  function underline(parts) {
    var line = $("claim-line"), text = line.textContent, at = 0, out = document.createDocumentFragment();
    var sorted = parts.slice().sort(function (a, b) { return a.span[0] - b.span[0]; });
    for (var i = 0; i < sorted.length; i++) {
      var p = sorted[i];
      if (p.span[0] < at || p.span[1] > text.length || p.span[0] >= p.span[1]) return;
      out.appendChild(document.createTextNode(text.slice(at, p.span[0])));
      var s = el("span", "u checking", text.slice(p.span[0], p.span[1])); s.dataset.part = p.id; out.appendChild(s); at = p.span[1];
    }
    out.appendChild(document.createTextNode(text.slice(at)));
    line.textContent = ""; line.appendChild(out); line.className = "claim";
  }

  // Threads join the same thing across documents. Fixed columns, never force-directed.
  var queued = false;
  function drawThreads() {
    if (queued) return; queued = true;
    requestAnimationFrame(function () {
      queued = false;
      var map = $("map"), box = map.getBoundingClientRect(), t = $("threads"); t.textContent = "";
      Object.keys(state.chips).forEach(function (key) {
        var list = state.chips[key].slice().sort(function (a, b) { return a.getBoundingClientRect().left - b.getBoundingClientRect().left; });
        for (var i = 0; i + 1 < list.length; i++) {
          var a = list[i].getBoundingClientRect(), b = list[i + 1].getBoundingClientRect();
          var x1 = a.right - box.left, y1 = a.top + a.height / 2 - box.top, x2 = b.left - box.left, y2 = b.top + b.height / 2 - box.top;
          var mid = (x1 + x2) / 2, p = document.createElementNS(NS, "path");
          p.setAttribute("d", "M" + x1 + " " + y1 + "C" + mid + " " + y1 + " " + mid + " " + y2 + " " + x2 + " " + y2);
          t.appendChild(p);
        }
      });
    });
  }
  window.addEventListener("resize", drawThreads);

  var on = {
    files: function (d) {
      var pages = 0, n = 0;
      d.files.forEach(function (f, i) {
        if (!f.ok) { note("f" + i, f.name + ": " + f.note, "error"); return; }
        n++; pages += f.pages;
        var col = el("div", "col reading"), h = el("h3", null, tidy(f.name));
        var labels = el("ul", "labels");
        col.appendChild(h); col.appendChild(el("p", "role")); col.appendChild(labels); $("cols").appendChild(col);
        state.cols[f.name] = { col: col, ticks: {}, labels: labels };
        if (f.id) state.byId[f.id] = state.cols[f.name];  // same ids as DocRead.doc, so a cached graph still finds its columns
        var d1 = el("li", "d"); d1.appendChild(document.createTextNode(tidy(f.name)));
        var ul = el("ul");
        for (var k = 1; k <= f.pages; k++) {
          var li = el("li", "pg"); li.appendChild(svg(TICK, "tk")); li.appendChild(el("span", null, "Page " + k + " of " + f.pages));
          ul.appendChild(li); state.cols[f.name].ticks[k] = li;
        }
        d1.appendChild(ul); $("ticks").appendChild(d1);
        if (f.note) note("fn" + i, f.name + ": " + f.note);
      });
      latest("Reading each document once. Later claims on these documents skip this step.");
      say("Files accepted: " + plural(n, "document") + ", " + plural(pages, "page") + ".");
    },
    docstarted: function (d) {
      var c = state.cols[d.name]; if (c) state.byId[d.doc] = c;
      latest("Reading " + tidy(d.name) + "\u2026");
    },
    docread: function (d) {
      var c = state.cols[d.name]; if (!c) return;
      c.col.classList.remove("reading"); c.col.querySelector(".role").textContent = role(d.role) + (d.date ? ", " + d.date : "");
      state.byId[d.doc] = c;
      say(d.name + " read as " + role(d.role) + (d.date ? ", " + d.date : "") + ".");
    },
    pageread: function (d) {
      var c = state.cols[d.name]; if (!c || !c.ticks[d.page]) return;
      c.ticks[d.page].classList.add("ok");
      latest("Reading " + tidy(d.name) + ", page " + d.page + " of " + d.of);
    },
    entity: function (d) {
      var key = d.name.toLowerCase(), holders = (d.doc_ids || []).map(function (id) { return state.byId[id]; }).filter(Boolean);
      var made = [];
      if (holders.length) {
        holders.forEach(function (h) { var li = el("li"); li.appendChild(el("span", "pencil", d.name)); h.labels.appendChild(li); made.push(li.firstChild); });
      } else {
        var li = el("li"), chip = el("span", "pencil", d.name); chip.appendChild(el("span", "n", "in " + plural(d.docs, "document")));
        li.appendChild(chip); $("shared").appendChild(li); made.push(chip);
      }
      state.shown[key] = made; state.chips[key] = made.length > 1 ? made : (state.chips[key] || []);
      latest(d.name + ", in " + plural(d.docs, "document"));
    },
    graphready: function (d) {
      var r = $("receipt"); r.hidden = false;
      r.textContent = (d.cached ? "These documents were already read. " : "") + "Read " + plural(d.pages, "page") + ". Found " + plural(d.rules, "statement") + " about who must, may or must not do what, naming " + d.entities + " people, offices, sections and terms.";
      drawThreads(); say(r.textContent);
    },
    parts: function (d) {
      underline(d.parts);
      d.parts.forEach(function (p) {
        state.parts[p.id] = p.text;
        var li = el("li"); li.dataset.key = p.id; li.textContent = "Checking: " + p.text; $("parts").appendChild(li);
      });
      latest("Checking " + plural(d.parts.length, "part") + " of the claim.");
      say("Checking " + plural(d.parts.length, "part") + " of the claim.");
    },
    linked: function () {},
    path: function (d) {
      var li = $("parts").querySelector('[data-key="' + d.part_id + '"]');
      if (li && d.labels.length > 1) {
        var old = li.querySelector(".path"); if (old) old.remove();
        li.appendChild(el("span", "path", d.labels.join(" → ")));
      }
      var lit = 0;
      d.labels.forEach(function (name) { (state.shown[name.toLowerCase()] || []).forEach(function (c) { c.classList.add("on"); lit++; }); });
      if (lit) $("map").classList.add("deciding");
    },
    partdone: function (d) {
      var a = ANSWER[d.status] || ANSWER.error, li = $("parts").querySelector('[data-key="' + d.part_id + '"]');
      var path = li && li.querySelector(".path"), text = state.parts[d.part_id] || "";
      li.textContent = "";
      var st = el("strong", "st " + a.cls); st.appendChild(svg(STROKES[a.m], "mark m-" + a.m)); st.appendChild(document.createTextNode(a.word));
      li.appendChild(st); li.appendChild(document.createTextNode(text));
      if (d.reason) li.appendChild(el("span", "sub", d.reason));
      if (path) li.appendChild(path);
      var u = document.querySelector('.u[data-part="' + d.part_id + '"]');
      if (u) u.className = "u " + a.cls;
      say(a.word + ": " + text);
    },
    disagreement: function (d) { note("n" + d.part_id, d.text); },
    done: function (d) {
      state.reviewId = d.review_id;
      (d.banners || []).forEach(function (b, i) { note("b" + i, b); });
      $("review").src = "/api/review/" + d.review_id;
      $("result").hidden = false; say("Answer ready. The review page is below.");
      setTimeout(function () {
        $("readgrid").classList.add("collapsed"); $("reopen").hidden = false;
        $("result").scrollIntoView({ behavior: calm ? "auto" : "smooth", block: "start" });
      }, calm ? 0 : 900);
    },
    failed: function (d) { note("failed", d.text, "error"); say(d.text); }
  };

  $("reopen").addEventListener("click", function () {
    var g = $("readgrid"), shut = g.classList.toggle("collapsed");
    this.textContent = shut ? "Show what was read" : "Hide what was read"; drawThreads();
  });

  function dispatch(block) {
    var name = "message", data = "";
    block.split("\n").forEach(function (l) {
      if (l.indexOf("event: ") === 0) name = l.slice(7); else if (l.indexOf("data: ") === 0) data += l.slice(6);
    });
    if (data && on[name]) on[name](JSON.parse(data));
  }

  function run(url, body, claim) {
    go.disabled = true; go.textContent = "Checking…";
    reset(claim);
    return fetch(url, { method: "POST", body: body }).then(function (r) {
      if (!r.ok) return r.json().then(function (j) { showStart(j.refusal || "The check could not start."); });
      var reader = r.body.getReader(), dec = new TextDecoder(), buf = "";
      function pump() {
        return reader.read().then(function (x) {
          if (x.done) { if (buf.trim()) dispatch(buf); return; }
          buf += dec.decode(x.value, { stream: true });
          var i; while ((i = buf.indexOf("\n\n")) >= 0) { dispatch(buf.slice(0, i)); buf = buf.slice(i + 2); }
          return pump();
        });
      }
      return pump();
    }).catch(function () { note("failed", "The connection dropped. Nothing after this point was read.", "error"); })
      .then(function () { go.disabled = false; go.textContent = "Check claim"; });
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    state.passcode = $("passcode").value;
    run("/api/review", new FormData(form), $("claim").value.trim());
  });

  var drop = $("drop");
  ["dragenter", "dragover"].forEach(function (n) { drop.addEventListener(n, function () { drop.classList.add("over"); }); });
  ["dragleave", "drop"].forEach(function (n) { drop.addEventListener(n, function () { drop.classList.remove("over"); }); });
  $("files").addEventListener("change", function () {
    var f = this.files; $("drop-text").textContent = f.length ? Array.prototype.map.call(f, function (x) { return x.name; }).join(", ") : "Drop contracts, bylaws, resolutions or memos here, or choose files. PDF, PNG or JPG, up to 10.";
  });

  fetch("/api/config").then(function (r) { return r.json(); }).then(function (c) {
    state.needPass = !!c.passcode_required; $("passcode-field").hidden = !state.needPass; $("passcode").required = state.needPass;
  }).catch(function () {});

  function runSample(s) {
    state.passcode = $("passcode").value;
    if (state.needPass && !state.passcode) { $("passcode").focus(); problem.textContent = "Enter the passcode to open a packet."; problem.hidden = false; return; }
    var fd = new FormData(); fd.append("passcode", state.passcode);
    run("/api/sample/" + s.id, fd, s.claim);
  }

  fetch("/api/samples").then(function (r) { return r.json(); }).then(function (list) {
    if (!list.length) return;
    $("try-what").textContent = list[0].title;
    $("try").hidden = false;
    $("try-btn").addEventListener("click", function () { runSample(list[0]); });
    list.forEach(function (s) {
      var li = el("li"), slip = el("div", "slip");
      slip.appendChild(el("h3", null, s.title));
      slip.appendChild(el("q", null, s.claim));
      slip.appendChild(el("p", "docs", s.docs.map(tidy).join(", ")));
      var b = el("button", "btn quiet", "Check it"); b.type = "button";
      b.addEventListener("click", function () { runSample(s); });
      slip.appendChild(b); li.appendChild(slip); $("sample-list").appendChild(li);
    });
    $("samples").hidden = false;
  }).catch(function () {});

  window.addEventListener("message", function (e) {
    if (e.origin !== location.origin || !e.data || e.data.type !== "proofgraph-ask" || !state.reviewId) return;
    var fd = new FormData(); fd.append("claim", e.data.claim); fd.append("passcode", state.passcode);
    run("/api/review/" + state.reviewId + "/ask", fd, e.data.claim);
  });
})();
