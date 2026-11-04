(function () {
  var $ = function (id) { return document.getElementById(id); };
  var form = $("start"), go = $("go"), problem = $("problem");
  var state = { answered: [], reviewId: null, parts: {}, passcode: "", cols: {}, byId: {}, chips: {}, shown: {} };
  var calm = matchMedia("(prefers-reduced-motion: reduce)").matches;
  var NS = "http://www.w3.org/2000/svg";
  var runner = null;  // the running check, so going back can stop it

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
  function role(r) { r = (r || "").replace(/_/g, " "); return !r || r === "other" ? "Document" : r.charAt(0).toUpperCase() + r.slice(1); }
  function day(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || ""); if (!m) return iso || "";
    return new Date(Date.UTC(+m[1], +m[2] - 1, +m[3])).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
  }
  function tidy(name) { return name.replace(/\.(pdf|png|jpe?g)$/i, "").replace(/[_]+/g, " "); }
  function latest(text) { $("latest").textContent = text; }
  function note(key, text, cls) {
    var ul = $("notes"), li = ul.querySelector('[data-key="' + key + '"]');
    if (!li) { li = el("li"); li.dataset.key = key; ul.appendChild(li); }
    li.textContent = text; li.className = cls || "";
  }

  // The journey: three steps, each a section of the page. A step is a link to its section once it exists.
  var STEPS = ["sec-read", "sec-parts", "result"], bar = $("runbar"), frame = $("review");
  var trip = { phase: 1, finished: false, sections: [], auto: false };
  function barH() { return bar.hidden ? 0 : Math.ceil(bar.getBoundingClientRect().height); }
  function scrollTo(y) { window.scrollTo({ top: Math.max(0, y), behavior: calm ? "auto" : "smooth" }); }
  function phase(n) {
    trip.phase = n;
    $("sec-parts").hidden = n < 2;
    spy();
  }
  function paint(cur) {
    STEPS.forEach(function (_, i) {
      var b = $("st" + (i + 1)), reached = i + 1 <= trip.phase, passed = i + 1 < trip.phase;
      b.setAttribute("aria-disabled", String(!reached));
      b.classList.toggle("passed", passed);
      b.classList.toggle("here", i + 1 === cur);
      if (i + 1 === cur) b.setAttribute("aria-current", "step"); else b.removeAttribute("aria-current");
      var n = b.querySelector(".num");
      if (passed && !n.firstChild.tagName) { n.textContent = ""; n.appendChild(svg(TICK, "tk")); } else if (!passed && n.firstChild.tagName) n.textContent = String(i + 1);
    });
  }
  function setOpen(sec, open) {
    sec.classList.toggle("collapsed", !open);
    var t = sec.querySelector(".sec-toggle"); t.setAttribute("aria-expanded", String(open)); t.textContent = open ? "Hide details" : "Show details";
    if (open && sec.id === "sec-read") drawThreads();
  }
  function goTo(id) {
    var sec = $(id); if (!sec || sec.hidden) return;
    if (sec.classList.contains("collapsed")) setOpen(sec, true);
    scrollTo(window.scrollY + sec.getBoundingClientRect().top - barH());
    sec.querySelector("h2").focus({ preventScroll: true });
  }
  // Which section is under the bar now: it lights up its step, and inside the answer its sub-section.
  var spying = false;
  function spy() {
    if (spying) return; spying = true;
    requestAnimationFrame(function () {
      spying = false;
      if (bar.hidden) return;
      var line = barH() + 24, cur = trip.phase;
      if (trip.finished) {
        cur = 1;
        STEPS.forEach(function (id, i) { var n = $(id); if (!n.hidden && n.getBoundingClientRect().top <= line) cur = i + 1; });
        if (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 2) cur = 3;
      }
      paint(cur);
      var sub = $("j-sub"), fr = frame.getBoundingClientRect();
      sub.hidden = !(trip.auto && cur === 3 && trip.sections.length);
      if (!sub.hidden) {
        var y = line - fr.top, at = trip.sections[0].id;
        trip.sections.forEach(function (s) { if (s.top <= y + 8) at = s.id; });
        if (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 2) at = trip.sections[trip.sections.length - 1].id;
        Array.prototype.forEach.call(sub.querySelectorAll("button"), function (b) {
          if (b.dataset.id === at) b.setAttribute("aria-current", "true"); else b.removeAttribute("aria-current");
        });
      }
      if (trip.auto && frame.contentWindow) frame.contentWindow.postMessage({ type: "proofgraph-view", top: Math.max(0, barH() - fr.top), height: window.innerHeight - barH() }, location.origin);
    });
  }
  function buildSub(sections) {
    var sub = $("j-sub"); sub.textContent = "";
    sub.appendChild(el("span", "j-in", "In the answer"));
    sections.forEach(function (s) {
      var b = el("button", "j-link", s.label); b.type = "button"; b.dataset.id = s.id; if (s.hint) b.title = s.hint;
      b.addEventListener("click", function () { scrollTo(window.scrollY + frame.getBoundingClientRect().top + s.top - barH()); });
      sub.appendChild(b);
    });
  }
  function tally() {
    var words = state.answered.map(function (w) { return w; });
    return plural(words.length, "part") + (words.length ? ": " + words.join(", ") : "");
  }
  window.addEventListener("scroll", spy, { passive: true });
  window.addEventListener("resize", spy);
  if (window.ResizeObserver) new ResizeObserver(function () { document.documentElement.style.setProperty("--bar-h", barH() + "px"); spy(); }).observe(bar);
  STEPS.forEach(function (id, i) {
    $("st" + (i + 1)).addEventListener("click", function () { if (this.getAttribute("aria-disabled") !== "true") goTo(id); });
  });
  Array.prototype.forEach.call(document.querySelectorAll(".sec-toggle"), function (t) {
    t.addEventListener("click", function () { var sec = t.closest(".sec"); setOpen(sec, sec.classList.contains("collapsed")); });
  });

  function showStart(text) {
    if (runner) { runner.abort(); runner = null; }
    $("review").removeAttribute("src"); $("opening").hidden = true; state.reviewId = null;
    bar.hidden = true; document.documentElement.classList.remove("running"); $("entrance").hidden = false; $("live").hidden = true; $("result").hidden = true;
    go.disabled = false; go.textContent = "Check claim"; window.scrollTo(0, 0);
    if (text) { problem.textContent = text; problem.hidden = false; say(text); }
  }
  function reset(claim) {
    ["ticks", "cols", "shared", "parts", "notes"].forEach(function (id) { $(id).textContent = ""; });
    $("threads").textContent = ""; $("receipt").hidden = true; latest("");
    $("read-sum").textContent = ""; $("parts-sum").textContent = ""; trip = { phase: 1, finished: false, sections: [], auto: false };
    $("result").classList.remove("auto"); $("j-sub").hidden = true; frame.style.height = ""; state.answered = [];
    setOpen($("sec-read"), true); setOpen($("sec-parts"), true); $("sec-parts").hidden = true;
    $("live").classList.remove("done"); $("read-name").textContent = "Reading the documents";
$("readgrid").classList.remove("read"); $("map-key").hidden = true;
    bar.hidden = false; document.documentElement.classList.add("running"); paint(1); $("map").classList.remove("deciding");
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

  function finishReading() {
    Array.prototype.forEach.call(document.querySelectorAll(".col.reading"), function (c) {
      c.classList.remove("reading");
      var r = c.querySelector(".role"); if (r && !r.textContent) r.textContent = "Read";
    });
    $("read-name").textContent = "How the documents were read"; $("readgrid").classList.add("read"); $("map-key").hidden = false;
  }

  var on = {
    files: function (d) {
      var pages = 0, n = 0;
      d.files.forEach(function (f, i) {
        if (!f.ok) { note("f" + i, f.name + ": " + f.note, "error"); return; }
        n++; pages += f.pages;
        var col = el("div", "col reading"), h = el("h3", null, tidy(f.name));
        var labels = el("ul", "labels");
        col.appendChild(h); col.appendChild(el("p", "role")); col.appendChild(el("div", "proof")); col.appendChild(labels); $("cols").appendChild(col);
        state.cols[f.name] = { col: col, ticks: {}, labels: labels, pages: f.pages, scan: f.note || "" };
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
    docsummary: function (d) {
      var c = state.byId[d.doc]; if (!c) return;
      c.col.classList.remove("reading");
      c.col.querySelector(".role").textContent = role(d.role) + (d.date ? ", " + day(d.date) : "");
      var box = c.col.querySelector(".proof"); box.textContent = "";
      box.appendChild(el("p", "stat", plural(c.pages, "page") + " read. " + plural(d.rules, "statement") + " kept, " + plural(d.names, "name") + " found."));
      if (d.rules) {
        var how = [];
        if (d.exact) how.push(d.exact + " word for word");
        if (d.tidied) how.push(d.tidied + " after tidying spacing and punctuation");
        if (d.close) how.push(d.close + " as a close match");
        box.appendChild(el("p", "ok", "Each one is a quote found on the page: " + how.join(", ") + "."));
      } else box.appendChild(el("p", "ok", "Nothing in it stated who must, may or must not do something."));
      if (c.scan) box.appendChild(el("p", "warn", c.scan.replace(/ will be transcribed;/, " was transcribed by the model;")));
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
      r.textContent = (d.cached ? "These documents were already read, so this step was not repeated. " : "") + "ProofGraph read " + plural(d.pages, "page") + " and kept " + plural(d.rules, "statement") + " (who must, may or must not do what), each one a quote found on its page. It named " + plural(d.entities, "name") + " (people, offices, sections and terms)" + (d.entities > 12 ? "; the map above shows the 12 named in the most documents." : ".");
      finishReading(); drawThreads(); say(r.textContent);
    },
    parts: function (d) {
      underline(d.parts);
      d.parts.forEach(function (p) {
        state.parts[p.id] = p.text;
        var li = el("li"); li.dataset.key = p.id; li.textContent = "Checking: " + p.text; $("parts").appendChild(li);
      });
      phase(2);
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
      state.answered.push(a.word);
      say(a.word + ": " + text);
    },
    disagreement: function (d) { note("n" + d.part_id, d.text); },
    done: function (d) {
      state.reviewId = d.review_id;
      (d.banners || []).forEach(function (b, i) { note("b" + i, b); });
      finishReading(); latest("Done."); $("live").classList.add("done");
      trip.finished = true; phase(3); $("opening").hidden = false;
      frame.onload = function () { $("opening").hidden = true; };
      frame.src = "/api/review/" + d.review_id;
      $("result").hidden = false; say("Answer ready. The review is below.");
      setTimeout(function () {
        $("read-sum").textContent = $("receipt").textContent; $("parts-sum").textContent = tally();
        setOpen($("sec-read"), false); setOpen($("sec-parts"), false);
        scrollTo(window.scrollY + $("result").getBoundingClientRect().top - barH());
      }, calm ? 0 : 400);
    },
    failed: function (d) { note("failed", d.text, "error"); say(d.text); }
  };

  $("back").addEventListener("click", function () {
    if (history.state && history.state.run) history.back(); else showStart();
  });
  window.addEventListener("popstate", function () { if (!(history.state && history.state.run)) showStart(); });

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
    if (runner) runner.abort();
    runner = new AbortController();
    if (!(history.state && history.state.run)) history.pushState({ run: 1 }, "", "#check");  // so the browser's Back button returns to the start
    return fetch(url, { method: "POST", body: body, signal: runner.signal }).then(function (r) {
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
    }).catch(function (e) { if (e && e.name === "AbortError") return; note("failed", "The connection dropped. Nothing after this point was read.", "error"); })
      .then(function () { go.disabled = false; go.textContent = "Check claim"; });
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    state.passcode = $("passcode").value;
    run("/api/review", addKeys(new FormData(form)), $("claim").value.trim());
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

  // The optional keys live only in the two password fields (never in storage) and go out with the one request.
  function addKeys(fd) {
    fd.delete("meta_api_key"); fd.delete("baseten_api_key");
    if ($("meta-key").value.trim()) fd.append("meta_api_key", $("meta-key").value.trim());
    if ($("baseten-key").value.trim()) fd.append("baseten_api_key", $("baseten-key").value.trim());
    return fd;
  }

  function runSample(s) {
    state.passcode = $("passcode").value;
    if (state.needPass && !state.passcode) { $("passcode").focus(); problem.textContent = "Enter the passcode to open a packet."; problem.hidden = false; return; }
    var fd = new FormData(); fd.append("passcode", state.passcode); addKeys(fd);
    run("/api/sample/" + s.id, fd, s.claim);
  }

  fetch("/api/samples").then(function (r) { return r.json(); }).then(function (list) {
    if (!list.length) return;
    $("try-what").textContent = list[0].title;
    $("try").hidden = false;
    $("try-btn").addEventListener("click", function () { runSample(list[0]); });
    $("sheet-run").hidden = false; $("sheet-run").addEventListener("click", function () { runSample(list[0]); });
  }).catch(function () {});

  window.addEventListener("message", function (e) {
    if (e.origin !== location.origin || !e.data) return;
    if (e.data.type === "proofgraph-layout" && e.source === frame.contentWindow) {
      trip.auto = true; trip.sections = e.data.sections || []; $("result").classList.add("auto");
      frame.style.height = e.data.height + "px"; buildSub(trip.sections); spy(); return;
    }
    if (e.data.type !== "proofgraph-ask" || !state.reviewId) return;
    var fd = new FormData(); fd.append("claim", e.data.claim); fd.append("passcode", state.passcode); addKeys(fd);
    run("/api/review/" + state.reviewId + "/ask", fd, e.data.claim);
  });
})();
