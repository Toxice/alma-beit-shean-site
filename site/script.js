(function () {
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Exposed so content.js can set up carousels it inserts after load.
  window.initCarousel = function (car) {
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
  };

  document.querySelectorAll('[data-carousel]').forEach(window.initCarousel);
})();

(function () {
  var io = 'IntersectionObserver' in window && new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (e.isIntersecting) { e.target.classList.add('is-in'); io.unobserve(e.target); }
    });
  }, { rootMargin: '0px 0px -8% 0px' });
  // Siblings in a group cascade via --i; JS-only class so content shows without JS.
  // Exposed so content.js can animate elements it inserts after load.
  window.initReveal = function (elements) {
    if (!io) return;
    Array.prototype.forEach.call(elements, function (el) {
      el.classList.add('reveal');
      el.style.setProperty('--i', Array.prototype.indexOf.call(el.parentNode.children, el) % 5);
      io.observe(el);
    });
  };
  window.initReveal(document.querySelectorAll('.section-head, .feature, .gal-group, .attractions-carousel, .faq-item, .cta-band, .fact'));
})();

(function () {
  var root = document.documentElement;
  var toggle = document.getElementById('a11yToggle');
  var panel = document.getElementById('a11yPanel');
  var closeBtn = document.getElementById('a11yClose');
  if (!toggle || !panel) return;

  var TOGGLES = ['contrast', 'invert', 'grayscale', 'links', 'font', 'still'];
  var STEPS = { scale: 5, word: 5, letter: 5 }; // max step for each stepper
  var state;

  function fresh() {
    return { contrast: false, invert: false, grayscale: false, links: false, font: false, still: false, scale: 0, word: 0, letter: 0 };
  }

  function apply() {
    TOGGLES.forEach(function (k) {
      root.classList.toggle('a11y-' + k, state[k]);
      var tile = panel.querySelector('[data-a11y="' + k + '"]');
      if (tile) tile.setAttribute('aria-pressed', String(state[k]));
    });
    var filters = [];
    if (state.contrast) filters.push('contrast(1.35)');
    if (state.invert) filters.push('invert(1) hue-rotate(180deg)');
    if (state.grayscale) filters.push('grayscale(1)');
    root.style.filter = filters.join(' ');
    root.style.fontSize = state.scale ? (100 + state.scale * 10) + '%' : '';
    root.classList.toggle('a11y-spacing', state.word > 0 || state.letter > 0);
    root.style.setProperty('--a11y-word', (state.word * 0.12) + 'em');
    root.style.setProperty('--a11y-letter', (state.letter * 0.03) + 'em');
    panel.querySelectorAll('[data-step]').forEach(function (el) {
      var k = el.getAttribute('data-step');
      el.querySelector('output').textContent = k === 'scale' ? (100 + state.scale * 10) + '%' : String(state[k]);
    });
  }

  function save() {
    try { localStorage.setItem('a11y-v2', JSON.stringify(state)); } catch (e) {}
  }

  function load() {
    state = fresh();
    try {
      var saved = JSON.parse(localStorage.getItem('a11y-v2'));
      if (saved) Object.keys(state).forEach(function (k) { if (k in saved) state[k] = saved[k]; });
    } catch (e) {}
    apply();
  }

  function openPanel(open) {
    panel.hidden = !open;
    toggle.setAttribute('aria-expanded', String(open));
    (open ? closeBtn : toggle).focus();
  }

  toggle.addEventListener('click', function () { openPanel(panel.hidden); });
  closeBtn.addEventListener('click', function () { openPanel(false); });

  document.addEventListener('click', function (e) {
    if (!panel.hidden && !panel.contains(e.target) && !toggle.contains(e.target)) openPanel(false);
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && !panel.hidden) openPanel(false);
  });

  panel.addEventListener('click', function (e) {
    var btn = e.target.closest('button');
    if (!btn) return;
    var action = btn.getAttribute('data-a11y');
    var step = btn.closest('[data-step]');
    if (action === 'reset') state = fresh();
    else if (TOGGLES.indexOf(action) !== -1) state[action] = !state[action];
    else if (step) {
      var k = step.getAttribute('data-step');
      state[k] = Math.max(0, Math.min(STEPS[k], state[k] + Number(btn.getAttribute('data-dir'))));
    } else return;
    apply();
    save();
  });

  load();
})();
