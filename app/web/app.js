(function () {
  var $ = function (id) { return document.getElementById(id); };
  var form = $("start"), go = $("go"), problem = $("problem");
  var state = { answered: [], reviewId: null, parts: {}, passcode: "" };
  var calm = matchMedia("(prefers-reduced-motion: reduce)").matches;
  var NS = "http://www.w3.org/2000/svg";
  var runner = null;  // the running check, so going back can stop it

  // Answer encoding: a word, a mark and an underline style. Colour is never the only carrier.
  var STROKES = {
    tick: "M3.5 13.2C5.6 15 7.2 16.8 8.6 19.6 11.4 12.6 15.4 7.2 20.8 3.8",
    circle: "M12.4 3.1C6.8 2.4 2.7 7 3.3 12.5c.6 5.5 6.2 8.7 11.2 7.5 5-1.2 7.1-6 6-10.4-1-4-4.8-6.3-9.4-5.8",
    caret: "M3.8 19.6C7.2 14 9.6 9.6 12 5.4c2.6 4.6 5.2 9.2 8.2 14.2",
    bracket: "M15.4 3.6H8.6c-.7 0-1.1.3-1.1.9v15c0 .6.4.9 1.1.9h6.8",
    question: "M8.4 9.2C8.2 5.6 15.8 5.4 15.6 9.4c-.1 2.8-3.7 3-3.6 6.2M12 19.6v.1",
    clash: "M5 9h14M5 15h14M15 5L9 19"
  };
  var ANSWER = {
    supported: { word: "The claim is right", cls: "green", m: "tick" },
    contradicted: { word: "The claim is wrong", cls: "red", m: "circle" },
    not_found: { word: "Can’t be settled from these documents", cls: "clash", m: "clash" },
    unresolved: { word: "Can’t be settled from these documents", cls: "clash", m: "clash" },
    quoted: { word: "Quoted, not checked", cls: "slate", m: "bracket" },
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
  function esc(x) { var d = document.createElement("div"); d.textContent = x == null ? "" : x; return d.innerHTML; }
  // A problem message tied to its field: described-by, and focus moves to the field.
  function unflag(p) {
    if (!p._f) return;
    var ids = (p._f.getAttribute("aria-describedby") || "").split(" ").filter(function (i) { return i && i !== p.id; });
    if (ids.length) p._f.setAttribute("aria-describedby", ids.join(" ")); else p._f.removeAttribute("aria-describedby");
    p._f = null;
  }
  function flag(p, field, text) {
    unflag(p); p.textContent = text; p.hidden = false; say(text);
    if (field) { field.setAttribute("aria-describedby", ((field.getAttribute("aria-describedby") || "") + " " + p.id).trim()); p._f = field; field.focus(); }
  }
  var NET = "The server didn\u2019t answer. Nothing was decided; try again.";
  function say(text) { $("status").textContent = text; }
  function plural(n, w) { return n + " " + w + (n === 1 ? "" : "s"); }
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
  function tally() { return state.answered.join(", "); }
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
    $("review").removeAttribute("src"); $("opening").hidden = true; state.reviewId = null; $("after").hidden = true;
    bar.hidden = true; document.documentElement.classList.remove("running"); $("entrance").hidden = false; $("live").hidden = true; $("result").hidden = true;
    go.disabled = false; go.textContent = "Check this claim";
    if (/[?&]review=/.test(location.search)) history.replaceState(history.state, "", "/");
    if (text) { flag(problem, go, text); problem.scrollIntoView({ block: "center" }); }
    else { unflag(problem); var c = $("check"); if (c) c.scrollIntoView(); else window.scrollTo(0, 0); }
  }
  function reset(claim) {
    ["adm", "parts", "notes"].forEach(function (id) { $(id).textContent = ""; });
    $("read-sum").textContent = ""; $("parts-sum").textContent = ""; trip = { phase: 1, finished: false, sections: [], auto: false };
    $("result").classList.remove("auto"); $("j-sub").hidden = true; frame.style.height = ""; state.answered = [];
    setOpen($("sec-read"), true); setOpen($("sec-parts"), true); $("sec-parts").hidden = true;
    $("live").classList.remove("done");
    bar.hidden = false; document.documentElement.classList.add("running"); paint(1);
    state.parts = {};
    var c = $("claim-line"); c.textContent = claim; c.className = "claim reading";
    problem.hidden = true; unflag(problem); $("entrance").hidden = true; $("live").hidden = false; $("result").hidden = true;
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

  var on = {
    admitted: function (d) {
      var n = 0, docs = 0;
      $("adm").innerHTML = d.docs.map(function (x) {
        if (x.in_scope) { docs++; n += x.passages; }
        return '<tr class="' + (x.in_scope ? "in" : "out") + '"><td>' + esc(x.name) + '</td><td>' + esc(x.kind) + '</td><td><code>' + esc(x.policy) + '</code></td><td class="how-' +
          esc(x.strength || "none") + '">' + esc(x.how || "describes another policy") + '</td><td class="num-cell">' + (x.in_scope ? esc(String(x.passages)) : "not admitted") + '</td></tr>';
      }).join("");
      $("read-sum").textContent = plural(n, "passage") + " from " + plural(docs, "document") + " mapped to " + d.policy + (d.docs.length > docs ? "; " + plural(d.docs.length - docs, "other document") + " kept out." : ".");
      say($("read-sum").textContent);
    },
    parts: function (d) {
      underline(d.parts);
      d.parts.forEach(function (p) {
        state.parts[p.id] = p.text;
        var li = el("li"); li.dataset.key = p.id; li.textContent = "Checking: " + p.text; $("parts").appendChild(li);
      });
      phase(2);
      say("Checking " + plural(d.parts.length, "part") + " of the claim.");
    },
    partdone: function (d) {
      var a = ANSWER[d.status] || ANSWER.error, li = $("parts").querySelector('[data-key="' + d.part_id + '"]');
      var text = state.parts[d.part_id] || "";
      li.textContent = "";
      var st = el("strong", "st " + a.cls); st.appendChild(svg(STROKES[a.m], "mark m-" + a.m)); st.appendChild(document.createTextNode(a.word));
      li.appendChild(st); li.appendChild(document.createTextNode(text));
      if (d.reason) li.appendChild(el("span", "sub", d.reason));
      var u = document.querySelector('.u[data-part="' + d.part_id + '"]');
      if (u) u.className = "u " + a.cls;
      state.answered.push(a.word);
      say(a.word + ": " + text);
    },
    disagreement: function (d) { note("n" + d.part_id, d.text); },
    done: function (d) {
      state.reviewId = d.review_id;
      ["tc", "utc"].forEach(function (pre) {   // the typed panels start clean next time
        $(pre + "-out").textContent = ""; $(pre + "-out").hidden = true; $(pre + "-problem").hidden = true;
        var rb = $(pre + "-read"); rb.disabled = false; rb.textContent = "Find the lines";
      });
      var ru = "/?review=" + encodeURIComponent(d.review_id);
      if (location.pathname + location.search !== ru) {
        if (history.state && history.state.run) history.replaceState({ run: 1 }, "", ru); else history.pushState({ run: 1 }, "", ru);
      }
      (d.banners || []).forEach(function (b, i) { note("b" + i, b); });
      $("live").classList.add("done");
      trip.finished = true; phase(3); $("opening").hidden = false;
      frame.onload = function () { $("opening").hidden = true; };
      frame.src = "/api/review/" + d.review_id;
      $("result").hidden = false; showAfter(); say("Answer ready. The review is below.");
      $("live").hidden = true;  // the answer comes first; the chain is inside the report, collapsed
      window.scrollTo(0, 0);
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
      .then(function () { go.disabled = false; go.textContent = "Check this claim"; });
  }

  // The three-step form: packet, the person-written mapping, and a question from the registry.
  var pick = { packet: null, slot: null, claim: "" }, packs = [];
  function choice(name, value, title, sub, mono, checked, off) {
    return '<label class="choice' + (off ? ' off' : '') + '"><input type="radio" name="' + name + '" value="' + esc(value) + '"' +
      (checked ? ' checked' : '') + (off ? ' disabled' : '') + '><span class="c-t">' + esc(title) + '</span>' +
      (mono ? '<code class="c-k">' + esc(mono).replace(/\./g, ".<wbr>") + '</code>' : '') + (sub ? '<span class="c-s">' + esc(sub) + '</span>' : '') + '</label>';
  }
  function showPacket(id) {
    var p = packs.filter(function (x) { return x.id === id; })[0]; if (!p) return;
    pick.packet = id;
    $("pmap").innerHTML = p.docs.map(function (d) {
      var where = "";
      if (d.source) {
        var host = d.source.replace(/^https?:\/\/(www\.)?/, "").split("/")[0];
        var pg = d.pages && d.pages[0] === d.pages[1] ? "page " + d.pages[0] : "pages " + d.pages[0] + "\u2013" + d.pages[1];
        where = '<span class="src">' + esc(host === "sec.gov" ? "SEC EDGAR filing, Exhibit 10(e)" : host) + ', <span class="nw">' + esc(pg) + '</span></span>';
      }
      var name = d.source ? '<a href="' + esc(d.source) + '" target="_blank" rel="noopener">' + esc(d.name) + '<span class="sr"> (opens the original in a new tab)</span></a>' : esc(d.name);
      return '<tr><td>' + name + where + '</td><td>' + esc(d.kind) + '</td><td><code>' + esc(d.policy || "none recorded") + '</code></td><td class="how-' +
        esc(d.strength || "none") + '">' + esc(d.how || "no policy recorded, so the model does not see it") + '</td></tr>';
    }).join("");
    $("qs").innerHTML = p.questions.map(function (q) {
      var sub = !q.claim ? "No claim written for this question yet." : (q.kind === "wording" ? "Wording claim, quoted not checked: " : "Claim: ") + q.claim;
      return choice("slot", q.id, q.label, sub, q.slot, q.id === p.default, !q.claim);
    }).join("");
    showQuestion(p.default);
  }
  function showQuestion(slot) {
    var p = packs.filter(function (x) { return x.id === pick.packet; })[0];
    var q = p.questions.filter(function (x) { return x.id === slot; })[0];
    pick.slot = slot; pick.claim = q ? q.claim : "";
    Array.prototype.forEach.call($("qs").querySelectorAll(".choice"), function (l) {
      l.classList.toggle("on", l.querySelector("input").value === slot);
    });
  }
  fetch("/api/packets").then(function (r) { return r.json(); }).then(function (list) {
    packs = list; if (!list.length) return;
    $("pk").innerHTML = list.map(function (p, i) { return choice("packet", p.id, p.title, p.docs.length + (p.docs.length === 1 ? " document" : " documents"), null, i === 0, false); }).join("");
    showPacket(list[0].id);
  }).catch(function () {});
  $("pk").addEventListener("change", function (e) { if (e.target.name === "packet") showPacket(e.target.value); });
  $("qs").addEventListener("change", function (e) { if (e.target.name === "slot") showQuestion(e.target.value); });
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    if (!pick.packet || !pick.slot) return;
    state.passcode = $("passcode").value;
    var fd = new FormData(); fd.append("passcode", state.passcode);
    current = null;
    run("/api/run/" + encodeURIComponent(pick.packet) + "/" + encodeURIComponent(pick.slot), fd, pick.claim);
  });

  // Your documents: upload, the system proposes what each one is, a person confirms, then run.
  var up = { id: null, view: null, slot: null, claim: "" };
  function upSay(t, f) { var p = $("up-problem"); if (!t) { unflag(p); p.textContent = ""; p.hidden = true; return; } flag(p, f || null, t); }
  $("files").addEventListener("change", function () {
    var n = this.files.length; $("files-label").textContent = n ? plural(n, "file") + " chosen" : "Choose PDF files";
  });
  // Plain names for the document kinds. Only "amends another document" lets the endorsement rule apply.
  var KIND_LABEL = { policy_form: "Main document", declarations: "Schedule of amounts", endorsement: "Amends another document",
    binder: "Temporary cover (binder)", cover_note: "Cover note", correspondence: "Letter or notice" };
  function opts(list, cur) { return list.map(function (k) { return '<option value="' + esc(k) + '"' + (k === cur ? " selected" : "") + ">" + esc(KIND_LABEL[k] || k.replace(/_/g, " ")) + "</option>"; }).join(""); }
  function showProposal(v) {
    up.view = v; up.id = v.upload_id;
    var proposed = (v.rows.filter(function (r) { return r.policy; })[0] || {}).policy || "";
    $("up-policy").value = proposed;
    $("up-why").value = "";
    document.querySelector("#up-confirm .up-shared").hidden = true;
    try { $("up-who").value = $("up-who").value || localStorage.getItem("pg-who") || ""; } catch (e) {}
    $("up-split").checked = false;
    var rows = v.rows.map(function (r) {
      var printed = r.quotes.filter(function (q) { return q.field === "form_number" || q.field === "title"; })
        .map(function (q) { return q.text; }).filter(function (t, i, a) { return a.indexOf(t) === i; }).map(esc).join(" &middot; ");
      if (r.status === "unplaceable") return '<tr class="out"><td colspan="3"><b>' + esc(r.file) + '</b><br>Could not be placed: ' + esc(r.reason) + '</td></tr>';
      return '<tr data-row="' + esc(r.row_id) + '" data-how="' + esc(r.how || "judgment") + '" data-proposed-policy="' + esc(r.policy || "") +
        '" data-proposed-date="' + esc(r.effective_date || "") + '"><td><b>' + esc(r.file) + '</b>' +
        (printed ? '<small class="printed">Printed: ' + printed + '</small>' : '<small class="printed">Nothing printed it could verify</small>') +
        '<input type="text" class="row-policy" data-f="policy" value="' + esc(r.policy || "") + '" placeholder="Contract or rule it belongs to" aria-label="Contract or rule for ' + esc(r.file) + '" hidden></td>' +
        '<td><select data-f="kind" aria-label="Kind of document">' + opts(v.kinds, r.kind || "policy_form") + '</select></td><td>' +
        '<input type="text" data-f="effective_date" value="' + esc(r.effective_date || "") + '" placeholder="' + (r.effective_phrase ? "No day printed: type one if it applies" : "None printed") + '" aria-label="Effective date">' +
        (r.effective_phrase ? '<small class="printed">Printed: &ldquo;' + esc(r.effective_phrase) + '&rdquo;</small>' : "") +
        '<input type="text" data-f="effective_reason" placeholder="Why this date" aria-label="Why this effective date" hidden></td></tr>';
    });
    v.refused.forEach(function (r) { rows.push('<tr class="out"><td colspan="3"><b>' + esc(r.file) + '</b><br>Refused: ' + esc(r.refusal) + '</td></tr>'); });
    $("up-rows").innerHTML = rows.join("");
    $("up-confirm").hidden = false; $("up-question").hidden = true;
    $("up-confirm").scrollIntoView({ block: "start" });
  }
  // A typed or changed date needs a reason; the field appears only then.
  $("up-rows").addEventListener("input", function (e) {
    if (e.target.dataset.f !== "effective_date") return;
    var tr = e.target.closest("tr"), why = tr.querySelector('[data-f="effective_reason"]');
    why.hidden = e.target.value.trim() === "" || e.target.value.trim() === tr.dataset.proposedDate;
  });
  $("up-split").addEventListener("change", function () {
    var on = this.checked;
    document.querySelector("#up-confirm .up-shared").hidden = !on;
    Array.prototype.forEach.call($("up-rows").querySelectorAll(".row-policy"), function (i) { i.hidden = !on; });
  });
  $("up-go").addEventListener("click", function () {
    var f = $("files").files; if (!f.length) { upSay("Choose at least one PDF first.", $("files")); return; }
    var fd = new FormData(); Array.prototype.forEach.call(f, function (x) { fd.append("files", x); });
    upSay(""); this.disabled = true; this.textContent = "Reading…"; var btn = this;
    fetch("/api/upload", { method: "POST", body: fd }).then(function (r) { return r.json().then(function (j) { return [r.ok, j]; }); })
      .then(function (x) { if (!x[0]) upSay(x[1].refusal || "The upload could not be read.", $("files")); else showProposal(x[1]); })
      .catch(function () { upSay("The upload did not reach the server.", $("files")); })
      .then(function () { btn.disabled = false; btn.textContent = "Read the documents"; });
  });
  $("up-ok").addEventListener("click", function () {
    var who = $("up-who").value.trim(); if (!who) { upSay("Enter your name: who is confirming what these documents are.", $("up-who")); return; }
    var split = $("up-split").checked, shared = $("up-policy").value.trim(), why = $("up-why").value.trim();
    // No name given: the uploads are one set. The label only groups them; the result says it was grouped by default.
    // Default: the uploads are one set. A proposed policy number is kept as the label; otherwise "Uploaded set".
    if (!split) { shared = shared || "Uploaded set"; why = "Uploaded together and checked as one set."; }
    else if (!why) { upSay("Say why each document belongs where you put it.", $("up-why")); return; }
    var bad = 0;
    var rows = Array.prototype.map.call($("up-rows").querySelectorAll("tr[data-row]"), function (tr) {
      var o = { row_id: tr.dataset.row };
      Array.prototype.forEach.call(tr.querySelectorAll("[data-f]"), function (i) { o[i.dataset.f] = i.value.trim(); });
      if (!split) o.policy = shared;
      // "read" only where the proposal quoted this very policy from the page; anything else is the person's judgment, with the shared reason.
      o.how = tr.dataset.how === "read" && o.policy === tr.dataset.proposedPolicy ? "read" : "judgment";
      o.reason = o.how === "judgment" ? why : "";
      if (o.effective_date && o.effective_date !== tr.dataset.proposedDate && !o.effective_reason) bad++;
      return o;
    });
    if (split && rows.some(function (o) { return !o.policy; })) { upSay("Name the contract or rule for each document.", $("up-rows").querySelector(".row-policy:not([hidden])")); return; }
    if (rows.some(function (o) { return !o.kind; })) { upSay("Choose what kind each document is: it decides which rule can apply.", $("up-rows").querySelector("[data-f=kind]")); return; }
    if (bad) { upSay("Say why for each date you typed or changed.", $("up-rows").querySelector("[data-f=effective_reason]:not([hidden])")); return; }
    if (rows.some(function (o) { return o.how === "judgment"; }) && !why) { upSay("Say why these documents belong to that policy.", $("up-why")); return; }
    try { localStorage.setItem("pg-who", who); } catch (e) {}
    fetch("/api/upload/" + up.id + "/confirm", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ confirmed_by: who, rows: rows }) })
      .then(function (r) { return r.json().then(function (j) { return [r.ok, j]; }); })
      .then(function (x) {
        if (!x[0]) { upSay((x[1].refusal || "Not confirmed.") + (x[1].errors ? " " + x[1].errors.join(" ") : ""), $("up-who")); return; }
        upSay(""); var pol = {}; x[1].rows.forEach(function (r) { if (r.policy) pol[r.policy] = 1; });
        var qs = [], seen = {}; packs.forEach(function (p) { p.questions.forEach(function (q) { if (pol[q.slot.split(".")[0]] && !seen[q.slot]) { seen[q.slot] = 1; qs.push(q); } }); });
        $("up-qs").innerHTML = qs.length ? qs.map(function (q, i) { return choice("upslot", q.slot, q.label, q.claim ? "Claim: " + q.claim : "No claim written for this question yet.", q.slot, i === 0, !q.claim); }).join("")
          : '<p class="c-note">No question on the list is about the policies you confirmed (' + esc(Object.keys(pol).join(", ") || "none") + '). That is a refusal, not an error: the list is fixed, and nothing runs outside it.</p>';
        $("up-run").hidden = !qs.length; $("up-question").hidden = false; $("utc").hidden = false; $("up-confirm").querySelector("#up-ok").disabled = true;
        if (qs.length) { up.slot = qs[0].slot; up.claim = qs[0].claim || ""; }
      }).catch(function () { upSay(NET, $("up-who")); });
  });
  $("up-qs").addEventListener("change", function (e) {
    if (e.target.name !== "upslot") return; up.slot = e.target.value;
    up.claim = (e.target.closest(".choice").querySelector(".c-s") || {}).textContent.replace(/^Claim: /, "");
  });
  $("upload").addEventListener("submit", function (e) {
    e.preventDefault(); if (!up.id || !up.slot) return;
    current = null; run("/api/upload/" + up.id + "/run/" + encodeURIComponent(up.slot), new FormData(), up.claim);
  });

  fetch("/api/config").then(function (r) { return r.json(); }).then(function (c) {
    state.needPass = !!c.passcode_required; $("passcode-field").hidden = !state.needPass; $("passcode").required = state.needPass;
  }).catch(function () {});

  function runSample(s) {
    state.passcode = $("passcode").value;
    if (state.needPass && !state.passcode) { flag(problem, $("passcode"), "Enter the passcode to run a check."); return; }
    var fd = new FormData(); fd.append("passcode", state.passcode);
    current = s.id;
    run("/api/sample/" + s.id, fd, s.claim);
  }

  // Both examples, one click each: the case a rule decides, and the case it refuses to pick.
  var LABEL = { "endorsement-replaces-limit": "the claim that is right", "documents-disagree": "the example that can\u2019t be settled" };
  var samples = [], current = null;
  function sampleButton(s, cls) {
    var b = el("button", cls, LABEL[s.id] || s.title); b.type = "button"; b.title = s.title;
    b.addEventListener("click", function () { runSample(s); }); return b;
  }
  var NO_ISO = "This example's source documents could not be fetched on this server. It runs when you install ProofGraph yourself.";
  fetch("/api/samples").then(function (r) { return r.json(); }).then(function (list) {
    samples = list.filter(function (s) { return s.available !== false; });
    Array.prototype.forEach.call(document.querySelectorAll(".r-run"), function (b) {
      if (!sampleById(b.dataset.sample)) { var n = el("p", "r-note", NO_ISO); b.replaceWith(n); }
    });
    var q = new URLSearchParams(location.search), sid = q.get("sample"), rk = q.get("run");
    if (sid && sampleById(sid)) runSample(sampleById(sid));
    else if (rk && /^[\w-]+\/[\w.-]+$/.test(rk)) { current = null; run("/api/run/" + rk, new FormData(), ""); }
  }).catch(function () {});
  // The hero's result card: three real results, each with a button that runs it.
  function sampleById(id) { return samples.filter(function (x) { return x.id === id; })[0]; }
  Array.prototype.forEach.call(document.querySelectorAll(".r-run"), function (b) {
    b.addEventListener("click", function () { var x = sampleById(b.dataset.sample); if (x) runSample(x); });
  });
  var tabs = document.querySelector(".r-tabs");
  function showEx() {
    var on = (tabs.querySelector("input:checked") || {}).value;
    Array.prototype.forEach.call(document.querySelectorAll(".r-panel"), function (p) { p.hidden = p.dataset.ex !== on; });
  }
  Array.prototype.forEach.call(tabs.querySelectorAll("label[data-needs]"), function (l) {
    var panel = document.querySelector('.r-panel[data-ex="' + l.dataset.needs + '"]'); if (!panel || !panel.children.length) l.hidden = true;
  });
  tabs.addEventListener("change", showEx); showEx();
  // Pictures cropped from the ISO forms: a server without the forms says so instead of a broken image.
  Array.prototype.forEach.call(document.querySelectorAll("img.frame-pic"), function (img) {
    function gone() { var n = el("p", "r-note", "A crop of an ISO form. " + NO_ISO); img.replaceWith(n); }
    if (img.complete && !img.naturalWidth) gone(); else img.addEventListener("error", gone);
  });
  // Two doors: worked packets and your own documents, as tabs in the check section.
  function door(which) {
    var up = which === "upload";
    $("tab-worked").setAttribute("aria-selected", String(!up)); $("tab-upload").setAttribute("aria-selected", String(up));
    $("start").hidden = up; $("upload").hidden = !up;
  }
  $("tab-worked").addEventListener("click", function () { door("worked"); });
  $("tab-upload").addEventListener("click", function () { door("upload"); });
  Array.prototype.forEach.call(document.querySelectorAll("[data-door]"), function (a) {
    a.addEventListener("click", function () { door(a.dataset.door); });
  });

  function showAfter() {
    var box = $("after-btns"); box.textContent = "";
    var others = samples.filter(function (s) { return s.id !== current; });
    others.forEach(function (s, i) {
      if (i) box.appendChild(document.createTextNode(" \u00b7 "));
      var a = el("a", null, LABEL[s.id] || s.title); a.href = "/?sample=" + encodeURIComponent(s.id); a.title = s.title;
      a.addEventListener("click", function (e) { e.preventDefault(); runSample(s); }); box.appendChild(a);
    });
    $("after-more").hidden = !others.length;
    $("copy-status").textContent = ""; $("copy-fallback").hidden = true;
    $("after").hidden = false;
  }
  $("again").addEventListener("click", function () { showStart(); });
  $("copy-link").addEventListener("click", function () {
    if (!state.reviewId) return;
    var url = location.origin + "/api/review/" + state.reviewId, fb = $("copy-fallback"), st = $("copy-status");
    function manual() { fb.value = url; fb.hidden = false; fb.focus(); fb.select(); st.textContent = "Copy this link"; }
    if (!navigator.clipboard || !navigator.clipboard.writeText) return manual();
    navigator.clipboard.writeText(url).then(function () { fb.hidden = true; st.textContent = "Copied"; }, manual);
  });
  // A shared link: show that review directly.
  (function () {
    var m = /^\?review=([\w-]+)$/.exec(location.search);
    if (!m) return;
    reset(""); on.done({ review_id: m[1] });
  })();

  window.addEventListener("message", function (e) {
    if (e.origin !== location.origin || !e.data) return;
    if (e.data.type === "proofgraph-layout" && e.source === frame.contentWindow) {
      trip.auto = true; trip.sections = e.data.sections || []; $("result").classList.add("auto");
      frame.style.height = e.data.height + "px"; buildSub(trip.sections); spy(); return;
    }
  });

  // D11: type a claim. Code reads it, the reads find lines, a person confirms which are about it, then it is decided.
  function typed(pre, packetKey) {
    var out = $(pre + "-out"), problem = $(pre + "-problem"), state = {};
    function post(url, body) {
      return fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })
        .then(function (r) { return r.json().then(function (j) { return [r.ok, j]; }); })
        .catch(function () { return [false, { refusal: NET }]; });
    }
    function fail(t, field) { flag(problem, field || $(pre + "-text"), t); }
    function readBlock(r) {
      var bits = r.kind === "amount"
        ? "An amount. You wrote <b>" + esc(r.written) + "</b>; code read <b>" + esc(r.value) + "</b>. Basis: " + esc(r.basis || "not stated") + "."
        : "A claim about wording. It will be quoted with its page, not judged.";
      return '<p class="tc-read"><span class="q-label">Code read</span> ' + bits + "</p>";
    }
    function who() { try { return localStorage.getItem("pg-who") || ""; } catch (e) { return ""; } }
    function remember(v) { try { localStorage.setItem("pg-who", v); } catch (e) {} }
    // One click: code reads the claim, the policy is settled without a question when it can be, and the reads run.
    $(pre + "-read").addEventListener("click", function () {
      problem.hidden = true; unflag(problem); out.hidden = true;
      var text = $(pre + "-text").value, key = packetKey();
      if (!key) return fail("Choose the documents first.");
      post("/api/claim/read", { packet: key, text: text }).then(function (x) {
        var ok = x[0], r = x[1];
        if (!ok || r.refusal) return fail(r.refusal || "The claim could not be read.");
        state = { text: text, key: key, read: r };
        var m = r.policy_matches[0], only = r.policies.length === 1 ? r.policies[0] : null;
        out.innerHTML = readBlock(r) + '<div id="' + pre + '-scope"></div><div id="' + pre + '-lines"></div>';
        out.hidden = false;
        if (m || only) return find(m || only, m ? "matched_in_claim" : "only_in_packet");
        $(pre + "-scope").innerHTML = '<p class="tc-match">These documents cover more than one policy, and your claim names none. Which one is it about?</p>' +
          '<div class="tc-row"><select id="' + pre + '-policy" aria-label="Policy"><option value="">Choose…</option>' +
          r.policies.map(function (p) { return '<option value="' + esc(p) + '">' + esc(p) + "</option>"; }).join("") +
          '</select><button type="button" class="btn inv" id="' + pre + '-find">Find the lines</button></div>';
        $(pre + "-find").addEventListener("click", function () {
          var pol = $(pre + "-policy").value; if (!pol) return fail("Choose the policy the claim is about.", $(pre + "-policy"));
          find(pol, "chosen");
        });
      }).catch(function () { fail(NET); });
    });
    function find(pol, src) {
      problem.hidden = true; unflag(problem);
      var go = $(pre + "-read"); go.disabled = true; go.textContent = "Reading the documents…";
      var why = { matched_in_claim: "named in your claim", only_in_packet: "the only one in these documents", chosen: "chosen by you" }[src];
      $(pre + "-scope").innerHTML = pol === "Uploaded set" ? '<p class="tc-match">Checking against all the documents you uploaded.</p>'
        : '<p class="tc-match">Checking against <b>' + esc(pol) + "</b>, " + why + ".</p>";
      post("/api/claim/gather", { packet: state.key, text: state.text, policy: pol, policy_source: src }).then(function (x) {
        go.disabled = false; go.textContent = "Find the lines";
        var ok = x[0], g = x[1];
        if (!ok || g.refusal) return fail(g.refusal || "The documents could not be read.", $(pre + "-text"));
        state.gid = g.gather_id;
        var rows = g.lines.map(function (l, i) {
          return '<li class="tc-line"><p class="tc-where"><b>' + esc(l.doc) + "</b>, " + esc(l.where) + ' &middot; ' + (l.side === "against" ? "may count against the claim" : "may support the claim") +
            (l.value ? ' &middot; states <b>' + esc(l.value) + "</b>" + (l.basis ? " " + esc(l.basis) : "") : "") +
            (l.no_value ? ' &middot; ' + esc(l.no_value) : "") + "</p>" +
            '<blockquote class="says">' + esc(l.quote) + "</blockquote>" +
            // D13: several amounts and no pointer: the person may pick the figure the claim means; none picked, it stays unresolved
            (l.figures && l.figures.length ? '<label class="field narrow tc-figure"><span>Which figure is the claim&rsquo;s? Recorded as set here, not read by code.</span>' +
              '<select data-figure="' + esc(l.line_id) + '"><option value="">Leave unpicked (not compared)</option>' +
              l.figures.map(function (f, k) { return '<option value="' + k + '">' + esc(f) + "</option>"; }).join("") + "</select></label>" : "") +
            '<div class="tc-pick"><label><input type="checkbox" checked data-line="' + esc(l.line_id) + '"> About the claim</label>' +
            '<input type="text" class="tc-why" data-line="' + esc(l.line_id) + '" placeholder="Why it is set aside" aria-label="Why this line is set aside" hidden></div></li>';
        }).join("");
        var none = g.nothing_found.length ? '<p class="tc-none">Nothing found in: ' + g.nothing_found.map(esc).join(", ") + ".</p>" : "";
        var basis = g.ask_basis ? '<label class="field narrow"><span>The lines state a basis (' + g.basis_in_lines.map(esc).join(", ") +
          '); your claim does not. Set the claim&rsquo;s basis, or leave it unstated. Recorded as set here, not written by you.</span><select id="' + pre + '-basis"><option value="">Leave unstated</option>' +
          g.basis_options.map(function (b) { return '<option value="' + esc(b.id) + '">' + esc(b.label) + "</option>"; }).join("") + "</select></label>" : "";
        var currency = g.ask_currency ? '<label class="field narrow"><span>Your claim writes &ldquo;$&rdquo;, which names no country; the lines name ' +
          g.currency_in_lines.map(esc).join(", ") + '. Set the claim&rsquo;s currency, or leave it as written (then it is not compared). Recorded as set here, not written by you.</span><select id="' + pre + '-currency"><option value="">Leave as written</option>' +
          g.currency_in_lines.map(function (c) { return '<option value="' + esc(c) + '">' + esc(c) + "</option>"; }).join("") + "</select></label>" : "";
        $(pre + "-lines").innerHTML = '<p class="c-note">The lines it found. Untick any that is not about your claim and say why; nothing is compared until you check.</p>' +
          '<ol class="tc-list">' + rows + "</ol>" + none + basis + currency +
          '<div class="tc-row"><label class="field narrow"><span>Your name</span><input id="' + pre + '-who" type="text" autocomplete="name" value="' + esc(who()) + '"></label>' +
          '<button type="button" class="btn inv" id="' + pre + '-decide">Check this claim</button></div>';
        $(pre + "-lines").addEventListener("change", function (e) {
          if (e.target.type !== "checkbox") return;
          var why = $(pre + "-lines").querySelector('.tc-why[data-line="' + e.target.dataset.line + '"]');
          if (why) { why.hidden = e.target.checked; if (!e.target.checked) why.focus(); }
        });
        $(pre + "-decide").addEventListener("click", decide);
      }).catch(function () { go.disabled = false; go.textContent = "Find the lines"; fail(NET); });
    }
    function decide() {
      problem.hidden = true; unflag(problem);
      var confirmed = [], dropped = {}, missing = 0;
      Array.prototype.forEach.call($(pre + "-lines").querySelectorAll(".tc-line"), function (li) {
        var c = li.querySelector("input[type=checkbox]");
        if (c.checked) { confirmed.push(c.dataset.line); return; }
        var r = li.querySelector(".tc-why").value.trim();
        if (!r) missing++;
        dropped[c.dataset.line] = r;
      });
      if (missing) return fail("Say why each unticked line is set aside (" + missing + " without a reason).", $(pre + "-lines").querySelector(".tc-why:not([hidden])"));
      var name = $(pre + "-who").value.trim();
      if (!name) return fail("Add your name: the check records who confirmed the lines.", $(pre + "-who"));
      remember(name);
      var b = $(pre + "-basis"), cu = $(pre + "-currency"), figures = {};
      Array.prototype.forEach.call($(pre + "-lines").querySelectorAll("select[data-figure]"), function (s) {
        if (s.value !== "" && confirmed.indexOf(s.dataset.figure) >= 0) figures[s.dataset.figure] = parseInt(s.value, 10);
      });
      var dbtn = $(pre + "-decide"); dbtn.disabled = true; dbtn.textContent = "Checking\u2026";
      function unbusy() { dbtn.disabled = false; dbtn.textContent = "Check this claim"; }
      post("/api/claim/" + state.gid + "/decide", { confirmed: confirmed, dropped: dropped, confirmed_by: $(pre + "-who").value, basis: b ? b.value : "",
        currency: cu ? cu.value : "", figures: figures })
        .then(function (x) {
          var ok = x[0], d = x[1];
          if (!ok || d.refusal) { unbusy(); return fail(d.refusal || "The check could not run.", dbtn); }
          current = null; reset(state.text); on.done({ review_id: d.review_id, status: d.status });
        }).catch(function () { unbusy(); fail(NET, dbtn); });
    }
  }
  typed("tc", function () { return pick.packet; });
  typed("utc", function () { return up && up.id ? "upload:" + up.id : null; });
})();
