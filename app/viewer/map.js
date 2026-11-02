  // Argument ledger only (PROOFGRAPH_EVIDENCE_MAP). A row opens its passage under itself. One passage is open at a time,
  // so the one page image sits in one place and carries exactly one box.
  var rows = Array.prototype.slice.call(document.querySelectorAll(".rowbtn"));
  function setExpanded(btn, open) {
    btn.setAttribute("aria-expanded", String(open));
    var target = document.getElementById(btn.getAttribute("aria-controls"));
    if (target) target.hidden = !open;
    var act = btn.querySelector(".act");
    if (act) act.textContent = open ? "Close" : "Open";
    if (btn.dataset.shut) btn.textContent = open ? btn.dataset.open : btn.dataset.shut;
    if (act && btn.dataset.shutAct) act.textContent = open ? "Close" : btn.dataset.shutAct;
  }
  // Unhide every closed group, list and panel above `el`, and mark the button that controls each one as expanded.
  function openAncestors(el) {
    for (var n = el.parentElement; n; n = n.parentElement) {
      if (!n.hidden || !n.id) continue;
      var c = document.querySelector('[aria-controls="' + n.id + '"]');
      if (c) setExpanded(c, true); else n.hidden = false;
    }
  }
  function reveal(card, stayOnRow, quiet) {
    var li = card.closest("li.row"), btn = li.querySelector(".rowbtn");
    rows.forEach(function (r) { if (r !== btn && r.getAttribute("aria-expanded") === "true") setExpanded(r, false); });
    openAncestors(card);
    setExpanded(btn, true);
    var page = document.querySelector('.page[data-doc="' + card.dataset.doc + '"][data-page="' + card.dataset.page + '"]');
    var slot = card.querySelector(".slot");
    if (page && slot) slot.appendChild(page);
    show(card);
    if (quiet) return;
    (stayOnRow ? btn : card).focus({ preventScroll: true });
    var b = document.querySelector('[data-box-for="' + card.dataset.cardId + '"]');
    (b || li).scrollIntoView({ block: "center", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  }
  function closeRow(li) {
    var btn = li.querySelector(".rowbtn");
    setExpanded(btn, false);
    btn.focus();
  }
  document.addEventListener("click", function (e) {
    var t = e.target.closest && e.target.closest("button, [data-reveal]");
    if (!t) return;
    if (t.classList.contains("rowbtn")) {
      e.preventDefault();
      if (t.getAttribute("aria-expanded") === "true") setExpanded(t, false);
      else reveal(t.parentElement.querySelector("[data-card-id]"), true);
    } else if (t.classList.contains("close")) closeRow(t.closest("li.row"));
    else if (t.hasAttribute("aria-controls")) setExpanded(t, t.getAttribute("aria-expanded") !== "true");
    else if (t.hasAttribute("data-reveal")) {
      e.preventDefault();
      var target = byId(t.dataset.reveal);
      if (target) reveal(target, false);
    }
  });
  // Made first (capture phase) and final: the shared handler would call preventDefault on Enter, which stops a button click.
  document.addEventListener("keydown", function (e) {
    if (e.ctrlKey || e.metaKey || e.altKey || typing(e.target)) return;
    var k = e.key;
    if ((k === "Enter" || k === " ") && e.target.closest && e.target.closest("button")) return e.stopImmediatePropagation();
    var li = document.activeElement && document.activeElement.closest && document.activeElement.closest("li.row");
    if (k === "Escape") {
      if (li && li.querySelector(".rowbtn").getAttribute("aria-expanded") === "true") closeRow(li);
      return;
    }
    var step = k === "j" || k === "]" ? 1 : k === "k" || k === "[" ? -1 : 0;
    if (!step) return;
    e.stopImmediatePropagation();
    e.preventDefault();
    var list = k === "]" || k === "[" ? rows.filter(function (r) { return r.parentElement.classList.contains("contradicts"); }) : rows;
    if (!list.length) return;
    var cur = li ? li.querySelector(".rowbtn") : null, at = list.indexOf(cur), next;
    if (at < 0) {
      var from = rows.indexOf(cur), ahead = list.filter(function (r) { return step > 0 ? rows.indexOf(r) > from : rows.indexOf(r) < from; });
      next = ahead.length ? ahead[step > 0 ? 0 : ahead.length - 1] : list[step > 0 ? 0 : list.length - 1];
    } else next = list[(at + step + list.length) % list.length];
    openAncestors(next);
    next.focus({ preventScroll: true });
    next.scrollIntoView({ block: "nearest" });
    announce(next.parentElement.querySelector("[data-card-id]"));
  }, true);
  // The deciding passage starts open. Quiet: no focus move and no scroll, so the page still opens at the top.
  var first = document.querySelector("[data-default-open]");
  if (first) reveal(first.parentElement.querySelector("[data-card-id]"), true, true);
