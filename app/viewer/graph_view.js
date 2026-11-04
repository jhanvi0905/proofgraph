(function () {
  var live = document.getElementById("live");
  var cells = Array.prototype.slice.call(document.querySelectorAll(".cell"));
  function show(cell, quiet) {
    cells.forEach(function (c) { c.setAttribute("aria-pressed", String(c === cell)); });
    document.querySelectorAll(".box.active").forEach(function (b) { b.classList.remove("active"); });
    document.querySelectorAll(".page").forEach(function (p) {
      p.hidden = !(p.dataset.doc === cell.dataset.doc && p.dataset.page === cell.dataset.page);
    });
    var box = document.querySelectorAll('[data-box-for="' + cell.dataset.cardId + '"]');
    var rel = (cell.className.match(/\b(supports|weakens|contradicts|set_aside)\b/) || [])[1];
    box.forEach(function (b) { b.classList.add("active"); if (rel) b.dataset.rel = rel; });
    cells.forEach(function (c) {
      var go = c.querySelector(".go");
      if (go) go.textContent = (c === cell ? "Showing on page " : "Show on page ") + c.dataset.page;
    });
    var hint = document.getElementById("hint");
    if (hint) hint.hidden = true;
    var q = cell.querySelector("q");
    live.textContent = "Showing page " + cell.dataset.page + (q ? ": " + q.textContent : "");
    if (quiet) return;
    var target = box[0] || document.querySelector(".page:not([hidden])");
    if (target && target.scrollIntoView) target.scrollIntoView({ block: "nearest", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  }
  // On a narrow screen the page opens inline under the tapped quote; on a wide one it stays in its own column.
  var pane = document.querySelector(".pane"), home = pane && pane.parentNode, anchor = pane && pane.nextSibling;
  var narrow = matchMedia("(max-width: 1099px)");
  if (pane && narrow.addEventListener) narrow.addEventListener("change", function (e) { if (!e.matches) home.insertBefore(pane, anchor); });
  cells.forEach(function (c) {
    c.addEventListener("click", function () {
      if (pane && narrow.matches) { c.after(pane); pane.classList.add("open"); }
      show(c);
    });
  });
  var paneclose = document.getElementById("paneclose");
  if (paneclose) paneclose.addEventListener("click", function () {
    var was = cells.filter(function (c) { return c.getAttribute("aria-pressed") === "true"; })[0];
    pane.classList.remove("open");
    cells.forEach(function (c) { c.setAttribute("aria-pressed", "false"); var go = c.querySelector(".go"); if (go) go.textContent = "Show on page " + c.dataset.page; });
    if (was) was.focus();
  });
  Array.prototype.forEach.call(document.querySelectorAll(".side-go"), function (b) {
    b.addEventListener("click", function () {
      var c = document.querySelector('.cell[data-card-id="' + b.getAttribute("data-for") + '"]');
      if (c) { c.click(); c.focus({ preventScroll: true }); }
    });
  });
  document.querySelectorAll(".page").forEach(function (p) { p.hidden = true; });
  var first = document.querySelector(".cell.decides") || cells[0];
  if (first) show(first, true);
  var framed = window.parent !== window, ask = document.getElementById("ask");
  var askLink = document.querySelector('.toc a[href="#ask"]');
  if (askLink && !framed) askLink.remove();  // the form only shows inside the app
  if (ask && framed) {
    ask.hidden = false;
    ask.addEventListener("submit", function (e) {
      e.preventDefault();
      var v = document.getElementById("ask-claim").value.trim();
      if (v) window.parent.postMessage({ type: "proofgraph-ask", claim: v }, location.origin);
    });
  }
  // Framed by the app: tell the page above how tall this is and where each section starts, so it can draw the one
  // contents bar and keep one scrollbar. It also says where the visible edge is, so the page column can follow it.
  if (framed) {
    var wrap = document.querySelector(".wrap"), offset = 0;
    var tell = function () {
      var sections = Array.prototype.map.call(document.querySelectorAll(".toc a"), function (a) {
        var t = document.getElementById(a.getAttribute("href").slice(1));
        return { id: a.getAttribute("href").slice(1), label: a.textContent, hint: a.getAttribute("data-hint") || "",
                 top: t ? Math.round(t.getBoundingClientRect().top + window.scrollY) : 0 };
      });
      window.parent.postMessage({ type: "proofgraph-layout", height: Math.ceil(wrap.getBoundingClientRect().height), sections: sections }, location.origin);
    };
    if (window.ResizeObserver) new ResizeObserver(tell).observe(wrap);
    window.addEventListener("load", tell);
    var wide = matchMedia("(min-width: 1100px)"), main = document.querySelector("main");
    window.addEventListener("message", function (e) {
      if (e.origin !== location.origin || !e.data || e.data.type !== "proofgraph-view" || !pane) return;
      if (!wide.matches || pane.parentNode !== home) { pane.style.transform = ""; offset = 0; return; }
      var natural = pane.getBoundingClientRect().top + window.scrollY - offset;
      var room = main.getBoundingClientRect().bottom + window.scrollY - natural - pane.offsetHeight;
      offset = Math.round(Math.max(0, Math.min(e.data.top + 16 - natural, room)));
      pane.style.transform = offset ? "translateY(" + offset + "px)" : "";
    });
  }
  var copyBtn = document.getElementById("copylink");
  if (copyBtn) copyBtn.addEventListener("click", function () {
    var url = location.origin + copyBtn.dataset.url;
    var done = function () { copyBtn.textContent = "Link copied"; live.textContent = "Link copied"; };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(url).then(done, function () { window.prompt("Copy this link", url); });
    else window.prompt("Copy this link", url);
  });
  // The page images are separate files on the server; the offline copy carries them inside itself.
  function inlineImages(root) {
    var imgs = Array.prototype.slice.call(root.querySelectorAll('img[src^="/api/review/"]'));
    return Promise.all(imgs.map(function (img) {
      return fetch(img.getAttribute("src")).then(function (r) { return r.blob(); }).then(function (b) {
        return new Promise(function (done) { var fr = new FileReader(); fr.onload = function () { img.setAttribute("src", fr.result); done(); }; fr.readAsDataURL(b); });
      });
    }));
  }
  document.getElementById("download").addEventListener("click", function () {
    var copy = document.documentElement.cloneNode(true);
    var f = copy.querySelector("#ask"); if (f) f.hidden = true;
    copy.classList.remove("framed"); var pn = copy.querySelector(".pane"); if (pn) pn.style.transform = "";
    inlineImages(copy).then(function () {
      var blob = new Blob(["<!doctype html>" + copy.outerHTML], { type: "text/html" });
      var a = document.createElement("a");
      a.href = URL.createObjectURL(blob); a.download = "proofgraph-review.html";
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
    });
  });
})();
