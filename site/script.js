(function () {
  document.querySelectorAll('[data-carousel]').forEach(function (car) {
    var track = car.querySelector('.carousel-track');
    var slides = track.querySelectorAll('img');
    var prevBtn = car.querySelector('[data-car-prev]');
    var nextBtn = car.querySelector('[data-car-next]');
    var counter = car.querySelector('[data-car-counter]');
    var total = slides.length;
    var index = 0;

    function render() {
      track.style.transform = 'translateX(-' + (index * 100) + '%)';
      if (counter) counter.textContent = (index + 1) + ' / ' + total;
    }
    prevBtn.addEventListener('click', function () {
      index = (index - 1 + total) % total;
      render();
    });
    nextBtn.addEventListener('click', function () {
      index = (index + 1) % total;
      render();
    });
    render();
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
