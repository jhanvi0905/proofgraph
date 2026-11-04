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
  document.querySelectorAll(".page").forEach(function (p) { p.hidden = true; });
  var first = document.querySelector(".cell.decides") || cells[0];
  if (first) show(first, true);
  var framed = window.parent !== window, ask = document.getElementById("ask");
  if (ask && framed) {
    ask.hidden = false;
    ask.addEventListener("submit", function (e) {
      e.preventDefault();
      var v = document.getElementById("ask-claim").value.trim();
      if (v) window.parent.postMessage({ type: "proofgraph-ask", claim: v }, location.origin);
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
    inlineImages(copy).then(function () {
      var blob = new Blob(["<!doctype html>" + copy.outerHTML], { type: "text/html" });
      var a = document.createElement("a");
      a.href = URL.createObjectURL(blob); a.download = "proofgraph-review.html";
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
    });
  });
})();
