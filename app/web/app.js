(function () {
  var $ = function (id) { return document.getElementById(id); };
  var form = $("start"), go = $("go"), problem = $("problem");
  var live = $("live"), result = $("result"), frame = $("review");
  var state = { reviewId: null, parts: {}, passcode: "" };
  var STATUS = { contradicted: "Contradicted", weakened: "Qualified", supported: "Supported", not_found: "Not found", cannot_tell: "Unknown", error: "Error", checking: "Checking" };
  var COLOUR = { contradicted: "red", supported: "blue", weakened: "ochre" };

  function el(tag, cls, text) { var n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; }
  function say(text) { $("status").textContent = text; }
  function fail(text) { problem.textContent = text; problem.hidden = false; say(text); }
  function role(r) { r = (r || "").replace(/_/g, " "); return r ? r.charAt(0).toUpperCase() + r.slice(1) : "Document"; }
  function plural(n, w) { return n + " " + w + (n === 1 ? "" : "s"); }
  function line(listId, key, text, cls) {
    var ul = $(listId), li = ul.querySelector('[data-key="' + key + '"]');
    if (!li) { li = el("li"); li.dataset.key = key; ul.appendChild(li); }
    li.textContent = ""; if (cls) li.className = cls;
    li.appendChild(text instanceof Node ? text : document.createTextNode(text));
    return li;
  }
  function reset(claim) {
    ["docs", "found", "parts", "notes"].forEach(function (id) { $(id).textContent = ""; });
    $("receipt").hidden = true; state.parts = {};
    $("claim-line").textContent = claim;
    problem.hidden = true; live.hidden = false; result.hidden = true;
  }
  function underline(parts) {
    var text = $("claim-line").textContent, at = 0, out = document.createDocumentFragment(), ok = true;
    parts.slice().sort(function (a, b) { return a.span[0] - b.span[0]; }).forEach(function (p) {
      if (p.span[0] < at || p.span[1] > text.length || p.span[0] >= p.span[1]) { ok = false; return; }
      out.appendChild(document.createTextNode(text.slice(at, p.span[0])));
      var s = el("span", "u checking", text.slice(p.span[0], p.span[1])); s.dataset.part = p.id; out.appendChild(s); at = p.span[1];
    });
    if (!ok) return;
    out.appendChild(document.createTextNode(text.slice(at)));
    $("claim-line").textContent = ""; $("claim-line").appendChild(out);
  }

  var on = {
    files: function (d) {
      var pages = 0, n = 0;
      d.files.forEach(function (f, i) {
        if (f.ok) { n++; pages += f.pages; }
        var li = line("docs", "f" + i, f.name + (f.ok ? ": " + plural(f.pages, "page") : ": " + f.note));
        li.dataset.name = f.name;
        if (f.ok && f.note) { var s = el("span", "sub", f.note); li.appendChild(s); }
        if (!f.ok) li.className = "error";
      });
      say("Files accepted: " + plural(n, "document") + ", " + plural(pages, "page") + ".");
    },
    docread: function (d) {
      var li = line("docs", "d" + d.doc, d.name + ": " + role(d.role) + (d.date ? ", " + d.date : ""));
      say(d.name + " read as: " + role(d.role) + (d.date ? ", " + d.date : "") + ".");
    },
    pageread: function (d) {
      line("found", "p" + d.doc, "Reading " + d.name + ", page " + d.page + " of " + d.of);
    },
    entity: function (d) { line("found", "e" + d.name, d.name + ", in " + plural(d.docs, "document")); },
    graphready: function (d) {
      $("found").textContent = "";
      var r = $("receipt"); r.hidden = false;
      r.textContent = "Read " + plural(d.pages, "page") + ": " + d.rules + " rules about " + plural(d.entities, "thing") + (d.cached ? " (packet read before)" : "") + ".";
      say(r.textContent);
    },
    parts: function (d) {
      underline(d.parts);
      d.parts.forEach(function (p) { state.parts[p.id] = p.text; line("parts", p.id, "Checking: " + p.text); });
      say("Checking " + plural(d.parts.length, "part") + ".");
    },
    linked: function (d) { /* the part line already says Checking; entities are shown on the review */ },
    path: function (d) {
      var li = $("parts").querySelector('[data-key="' + d.part_id + '"]');
      if (li && d.labels.length > 1) {
        var old = li.querySelector(".path"); if (old) old.remove();
        li.appendChild(el("span", "path", d.labels.join(" → ")));
      }
    },
    partdone: function (d) {
      var text = state.parts[d.part_id] || "", word = STATUS[d.status] || d.status, c = COLOUR[d.status] || "";
      var li = $("parts").querySelector('[data-key="' + d.part_id + '"]'), path = li && li.querySelector(".path");
      var wrap = el("span"); wrap.appendChild(el("span", "mk " + c, d.status === "supported" || d.status === "contradicted" || d.status === "weakened" ? "✓" : "–"));
      wrap.appendChild(el("span", "done", word + ". ")); wrap.appendChild(document.createTextNode(text));
      if (d.reason) wrap.appendChild(el("span", "sub", d.reason));
      line("parts", d.part_id, wrap);
      if (path) $("parts").querySelector('[data-key="' + d.part_id + '"]').appendChild(path);
      var u = document.querySelector('.u[data-part="' + d.part_id + '"]');
      if (u) u.className = "u " + c;
      say(word + ": " + text);
    },
    disagreement: function (d) { line("notes", "n" + d.part_id, d.text); },
    done: function (d) {
      state.reviewId = d.review_id;
      (d.banners || []).forEach(function (b, i) { line("notes", "b" + i, b); });
      frame.src = "/api/review/" + d.review_id;
      result.hidden = false; say("Answer ready. The review page is below.");
      frame.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
    },
    failed: function (d) { line("notes", "failed", d.text, "error"); say(d.text); }
  };

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
      if (!r.ok) return r.json().then(function (j) { live.hidden = true; fail(j.refusal || "The check could not start."); });
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
    }).catch(function () { live.hidden = false; line("notes", "failed", "The connection dropped. Nothing after this point was read.", "error"); })
      .then(function () { go.disabled = false; go.textContent = "Check claim"; });
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    state.passcode = $("passcode").value;
    run("/api/review", new FormData(form), $("claim").value.trim());
  });

  window.addEventListener("message", function (e) {
    if (e.origin !== location.origin || !e.data || e.data.type !== "proofgraph-ask" || !state.reviewId) return;
    var fd = new FormData(); fd.append("claim", e.data.claim); fd.append("passcode", state.passcode);
    $("claim").value = e.data.claim;
    run("/api/review/" + state.reviewId + "/ask", fd, e.data.claim);
  });
})();
