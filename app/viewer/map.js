  // Evidence map only (PROOFGRAPH_EVIDENCE_MAP): cards can sit inside closed <details>.
  function openAncestors(card) {
    for (var d = card.parentElement; d; d = d.parentElement) if (d.tagName === "DETAILS" && !d.open) d.open = true;
  }
  function reveal(card) {
    openAncestors(card);
    show(card);
    card.focus({ preventScroll: true });
    var b = document.querySelector('[data-box-for="' + card.dataset.cardId + '"]');
    (b || card).scrollIntoView({ block: "center", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  }
  // Same choice as go() above, made first (capture phase) so the card is open when go() focuses it.
  document.addEventListener("keydown", function (e) {
    if (e.ctrlKey || e.metaKey || e.altKey || typing(e.target)) return;
    var k = e.key, step = k === "j" || k === "]" ? 1 : k === "k" || k === "[" ? -1 : 0;
    if (!step) return;
    var list = k === "]" || k === "[" ? cards.filter(function (c) { return c.classList.contains("contradicts"); }) : cards;
    if (!list.length) return;
    var cur = current(), at = list.indexOf(cur), next;
    if (at < 0) {
      var from = cards.indexOf(cur), ahead = list.filter(function (c) { return step > 0 ? cards.indexOf(c) > from : cards.indexOf(c) < from; });
      next = ahead.length ? ahead[step > 0 ? 0 : ahead.length - 1] : list[step > 0 ? 0 : list.length - 1];
    } else next = list[(at + step + list.length) % list.length];
    openAncestors(next);
  }, true);
  document.addEventListener("click", function (e) {
    var link = e.target.closest && e.target.closest("[data-reveal]");
    var target = link && byId(link.dataset.reveal);
    if (!link) return;
    e.preventDefault();
    if (target) reveal(target);
  });
