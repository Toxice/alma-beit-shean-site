(function () {
  var section = document.getElementById('reviews');
  if (!section) return;

  var local = location.hostname === 'localhost' || location.hostname === '127.0.0.1';
  var API = local ? 'http://localhost:8000' : 'https://api.alma-hosting.co.il';
  var PAGE = 6;
  var grid = section.querySelector('[data-reviews-grid]');
  var more = section.querySelector('[data-reviews-more]');
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

  function avatar(review) {
    var fallback = el('span', 'review-avatar review-initials', initials(review.name));
    if (!review.avatar) return fallback;
    var img = el('img', 'review-avatar');
    img.alt = '';
    img.loading = 'lazy';
    img.referrerPolicy = 'no-referrer'; // Google photo URLs can 403 with a referrer
    img.addEventListener('error', function () { img.replaceWith(fallback); });
    img.src = review.avatar;
    return img;
  }

  function stayLabel(month, year) {
    return 'התארחו ב' + new Date(year, month - 1, 1).toLocaleDateString('he-IL', { month: 'long', year: 'numeric' });
  }

  function card(review) {
    var article = el('article', 'review-card');
    article.append(
      avatar(review),
      el('h3', 'review-name', review.name),
      el('p', 'review-meta', stayLabel(review.stay_month, review.stay_year)),
      el('p', 'review-text', review.text)
    );
    return article;
  }

  fetch(API + '/api/reviews/')
    .then(function (res) {
      if (!res.ok) throw new Error('reviews ' + res.status);
      return res.json();
    })
    .then(function (data) {
      var list = data.reviews;
      if (!list.length) empty.hidden = false;
      list.forEach(function (review, i) {
        var c = card(review);
        if (i >= PAGE) c.hidden = true;
        grid.append(c);
      });
      if (list.length > PAGE) {
        more.hidden = false;
        grid.classList.add('is-collapsed');
        more.addEventListener('click', function () {
          grid.querySelectorAll('.review-card[hidden]').forEach(function (c) { c.hidden = false; });
          grid.classList.remove('is-collapsed');
          more.hidden = true;
        });
      }
      section.hidden = false;
    })
    .catch(function () {
      section.hidden = true; // API down: hide the section, rest of the site unaffected
    });
})();
