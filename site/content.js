(function () {
  var gallery = document.querySelector('[data-content="gallery"]');
  var faq = document.querySelector('[data-content="faq"]');
  if (!gallery && !faq) return;

  var local = location.hostname === 'localhost' || location.hostname === '127.0.0.1';
  var API = local ? 'http://localhost:8000' : 'https://api.alma-hosting.co.il';

  // textContent only: all text comes from the admin, never parsed as HTML.
  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text) node.textContent = text;
    return node;
  }

  function galleryGroup(tab) {
    var track = el('div', 'carousel-track');
    tab.photos.forEach(function (p) {
      var img = document.createElement('img');
      img.src = p.url;
      img.alt = p.alt;
      img.loading = 'lazy';
      img.decoding = 'async';
      track.append(img);
    });
    var viewport = el('div', 'carousel-viewport');
    viewport.append(track);
    var carousel = el('div', 'carousel');
    carousel.setAttribute('data-carousel', '');
    carousel.append(viewport);
    var group = el('div', 'gal-group');
    group.append(el('h3', null, tab.title), carousel);
    return group;
  }

  function faqItem(item) {
    var node = el('div', 'faq-item');
    node.append(el('h3', null, item.q), el('p', null, item.a));
    return node;
  }

  function replace(container, nodes) {
    container.replaceChildren.apply(container, nodes);
    if (window.initReveal) window.initReveal(nodes);
  }

  var ctrl = 'AbortController' in window ? new AbortController() : null;
  var timer = ctrl && setTimeout(function () { ctrl.abort(); }, 5000);

  fetch(API + '/api/content/', ctrl ? { signal: ctrl.signal } : {})
    .then(function (res) {
      if (!res.ok) throw new Error('content ' + res.status);
      return res.json();
    })
    .then(function (data) {
      clearTimeout(timer);
      if (gallery && data.gallery && data.gallery.length) {
        var groups = data.gallery.map(galleryGroup);
        replace(gallery, groups);
        if (window.initCarousel) {
          groups.forEach(function (g) { window.initCarousel(g.querySelector('[data-carousel]')); });
        }
      }
      if (faq && data.faq && data.faq.length) replace(faq, data.faq.map(faqItem));
    })
    .catch(function () {
      clearTimeout(timer); // API down or slow: the static gallery and FAQ stay as they are
    });
})();
