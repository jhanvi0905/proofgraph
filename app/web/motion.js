/* Entrances: each marked part rises once as its section enters, staggered. Content is visible without this
   script (the .js class is set by it inline) and without motion (prefers-reduced-motion keeps opacity only). */
(function () {
  var items = Array.prototype.slice.call(document.querySelectorAll("[data-rise]"));
  if (!("IntersectionObserver" in window)) { items.forEach(function (el) { el.classList.add("in"); }); return; }
  var seen = new WeakMap();
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (!e.isIntersecting) return;
      var el = e.target, parent = el.parentElement, n = seen.get(parent) || 0;
      seen.set(parent, n + 1);
      el.style.transitionDelay = Math.min(n, 5) * 75 + "ms";
      el.classList.add("in");
      io.unobserve(el);
    });
  }, { rootMargin: "0px 0px -8% 0px", threshold: 0.12 });
  items.forEach(function (el) { io.observe(el); });
})();
