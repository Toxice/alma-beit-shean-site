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
