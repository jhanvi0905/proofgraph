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
    box.forEach(function (b) { b.classList.add("active"); });
    var hint = document.getElementById("hint");
    if (hint) hint.hidden = true;
    var q = cell.querySelector("q");
    live.textContent = "Showing page " + cell.dataset.page + (q ? ": " + q.textContent : "");
    if (quiet) return;
    var target = box[0] || document.querySelector(".page:not([hidden])");
    if (target && target.scrollIntoView) target.scrollIntoView({ block: "nearest", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  }
  cells.forEach(function (c) { c.addEventListener("click", function () { show(c); }); });
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
  document.getElementById("download").addEventListener("click", function () {
    var copy = document.documentElement.cloneNode(true);
    var f = copy.querySelector("#ask"); if (f) f.hidden = true;
    var blob = new Blob(["<!doctype html>" + copy.outerHTML], { type: "text/html" });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = "proofgraph-review.html";
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
  });
})();
