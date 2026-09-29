(function () {
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  document.querySelectorAll('[data-carousel]').forEach(function (car) {
    var track = car.querySelector('.carousel-track');
    var originals = Array.prototype.slice.call(track.children);
    var n = originals.length;

    // Infinite loop: [copy][originals][copy]. When scrolling stops on a copy,
    // jump invisibly to the matching original so there is always a neighbour.
    function copy(el) {
      var c = el.cloneNode(true);
      c.setAttribute('aria-hidden', 'true');
      return c;
    }
    originals.forEach(function (el) { track.insertBefore(copy(el), originals[0]); });
    originals.forEach(function (el) { track.appendChild(copy(el)); });
    var slides = Array.prototype.slice.call(track.children);
    var active = null;

    function offsetFor(el) {
      return el.offsetLeft - (track.clientWidth - el.offsetWidth) / 2;
    }
    function center(el, smooth) {
      track.scrollTo({ left: offsetFor(el), behavior: smooth && !reduce ? 'smooth' : 'auto' });
    }

    // Active = slide whose midpoint is closest to the strip's midpoint.
    function markActive() {
      var mid = track.scrollLeft + track.clientWidth / 2;
      var best = null, bestDist = Infinity;
      slides.forEach(function (el) {
        var d = Math.abs(el.offsetLeft + el.offsetWidth / 2 - mid);
        if (d < bestDist) { bestDist = d; best = el; }
      });
      slides.forEach(function (el) { el.classList.toggle('is-active', el === best); });
      active = best;
    }

    function recenterIfCopy() {
      var i = slides.indexOf(active);
      if (i >= n && i < 2 * n) return;
      var twin = slides[(i % n) + n];
      track.classList.add('no-anim');
      track.scrollLeft += twin.offsetLeft - active.offsetLeft;
      markActive();
      requestAnimationFrame(function () {
        requestAnimationFrame(function () { track.classList.remove('no-anim'); });
      });
    }

    var queued = false, idle;
    track.addEventListener('scroll', function () {
      clearTimeout(idle);
      idle = setTimeout(recenterIfCopy, 150);
      if (queued) return;
      queued = true;
      requestAnimationFrame(function () { queued = false; markActive(); });
    }, { passive: true });

    slides.forEach(function (el, i) {
      el.tabIndex = i >= n && i < 2 * n ? 0 : -1;
      el.addEventListener('click', function () { if (el !== active) center(el, true); });
      el.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); center(el, true); }
      });
    });

    center(slides[n], false);
    markActive();
  });
})();

(function () {
  if (!('IntersectionObserver' in window)) return;
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (e.isIntersecting) { e.target.classList.add('is-in'); io.unobserve(e.target); }
    });
  }, { rootMargin: '0px 0px -8% 0px' });
  // Siblings in a group cascade via --i; JS-only class so content shows without JS.
  document.querySelectorAll('.section-head, .feature, .gal-group, .attractions-carousel, .faq-item, .cta-band, .fact').forEach(function (el) {
    el.classList.add('reveal');
    el.style.setProperty('--i', Array.prototype.indexOf.call(el.parentNode.children, el) % 5);
    io.observe(el);
  });
})();

(function () {
  var root = document.documentElement;
  var toggle = document.getElementById('a11yToggle');
  var panel = document.getElementById('a11yPanel');
  if (!toggle || !panel) return;

  var FONT_CLASSES = ['a11y-font-1', 'a11y-font-2', 'a11y-font-3'];
  var TOGGLE_CLASSES = ['a11y-contrast', 'a11y-grayscale', 'a11y-underline'].concat(FONT_CLASSES);
  var fontStep = 0;

  function save() {
    localStorage.setItem('a11y', JSON.stringify({
      classes: TOGGLE_CLASSES.filter(function (c) { return root.classList.contains(c); }),
      fontStep: fontStep
    }));
  }

  function load() {
    try {
      var saved = JSON.parse(localStorage.getItem('a11y'));
      if (!saved) return;
      saved.classes.forEach(function (c) { root.classList.add(c); });
      fontStep = saved.fontStep || 0;
    } catch (e) {}
  }

  function setFontStep(step) {
    fontStep = Math.max(0, Math.min(FONT_CLASSES.length, step));
    FONT_CLASSES.forEach(function (c, i) { root.classList.toggle(c, i < fontStep); });
  }

  function openPanel(open) {
    panel.hidden = !open;
    toggle.setAttribute('aria-expanded', String(open));
  }

  toggle.addEventListener('click', function () {
    openPanel(panel.hidden);
  });

  document.addEventListener('click', function (e) {
    if (!panel.hidden && !panel.contains(e.target) && !toggle.contains(e.target)) openPanel(false);
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') openPanel(false);
  });

  panel.addEventListener('click', function (e) {
    var action = e.target.getAttribute('data-a11y');
    if (!action) return;
    if (action === 'font-up') setFontStep(fontStep + 1);
    else if (action === 'font-down') setFontStep(fontStep - 1);
    else if (action === 'contrast') root.classList.toggle('a11y-contrast');
    else if (action === 'grayscale') root.classList.toggle('a11y-grayscale');
    else if (action === 'underline') root.classList.toggle('a11y-underline');
    else if (action === 'reset') {
      TOGGLE_CLASSES.forEach(function (c) { root.classList.remove(c); });
      setFontStep(0);
    }
    save();
  });

  load();
})();
