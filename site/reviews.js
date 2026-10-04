(function () {
  var section = document.getElementById('reviews');
  if (!section) return;

  var local = location.hostname === 'localhost' || location.hostname === '127.0.0.1';
  var API = local ? 'http://localhost:8000' : 'https://api.alma-hosting.co.il';
  var grid = section.querySelector('[data-reviews-grid]');
  var empty = section.querySelector('[data-reviews-empty]');

  section.querySelectorAll('[data-reviews-write]').forEach(function (a) {
    a.href = API + '/reviews/write/';
  });

  // textContent only: review text comes from users (stored-XSS guard).
  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text) node.textContent = text;
    return node;
  }

  function initials(name) {
    return name.trim().split(/\s+/).slice(0, 2).map(function (w) { return w.charAt(0); }).join('');
  }

  function stayLabel(month, year) {
    return 'התארחו ב' + new Date(year, month - 1, 1).toLocaleDateString('he-IL', { month: 'long', year: 'numeric' });
  }

  function card(review) {
    var article = el('article', 'review-card');
    article.append(
      el('span', 'review-initials', initials(review.name)),
      el('h3', 'review-name', review.name),
      el('p', 'review-meta', stayLabel(review.stay_month, review.stay_year))
    );
    if (review.source === 'airbnb') article.append(el('span', 'review-source', 'מ-Airbnb'));
    article.append(el('p', 'review-text', review.text));
    var more = el('button', 'review-more', 'קרא עוד');
    more.type = 'button';
    article.append(more); // shown only on phones, and only when the text is cut (see markLong)
    return article;
  }

  // Phones clamp the text to a few lines; flag cards whose text is actually cut.
  function markLong() {
    grid.querySelectorAll('.review-card:not(.is-open)').forEach(function (c) {
      var t = c.querySelector('.review-text');
      c.classList.toggle('is-long', t.scrollHeight > t.clientHeight + 1);
    });
  }

  // Delegated: the carousel clones cards, and clones don't carry listeners.
  grid.addEventListener('click', function (e) {
    var button = e.target.closest('.review-more');
    if (!button) return;
    var open = button.closest('.review-card').classList.toggle('is-open');
    button.textContent = open ? 'הצג פחות' : 'קרא עוד';
  });

  fetch(API + '/api/reviews/')
    .then(function (res) {
      if (!res.ok) throw new Error('reviews ' + res.status);
      return res.json();
    })
    .then(function (data) {
      var list = data.reviews;
      list.forEach(function (review) { grid.append(card(review)); });
      section.hidden = false;
      // Same looping strip as the galleries; set up after unhiding so it can measure widths.
      if (list.length) window.initCarousel(section.querySelector('[data-reviews-carousel]'));
      else empty.hidden = false;
      markLong();
      window.addEventListener('resize', markLong);
    })
    .catch(function () {
      section.hidden = true; // API down: hide the section, rest of the site unaffected
    });
})();
