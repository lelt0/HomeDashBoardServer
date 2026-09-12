(function () {
  var root = document.querySelector('[data-feature="interaction"]');
  if (!root) return;

  var counter = root.querySelector('[data-role="counter"]');
  var slider = root.querySelector('[data-action="slider"]');
  var sliderValue = root.querySelector('[data-role="slider-value"]');
  var value = 0;

  function renderCounter() {
    counter.textContent = String(value);
  }

  root.addEventListener('click', function (event) {
    var action = event.target.getAttribute('data-action');
    if (action === 'increment') {
      value += 1;
      renderCounter();
    } else if (action === 'decrement') {
      value -= 1;
      renderCounter();
    }
  });

  if (slider && sliderValue) {
    slider.addEventListener('input', function () {
      sliderValue.textContent = slider.value + '%';
    });
  }

  renderCounter();
})();
