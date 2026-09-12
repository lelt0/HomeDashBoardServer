(function () {
  const clock = document.querySelector('[data-feature="clock"] [data-role="value"]');
  if (!clock) return;

  function updateClock() {
    const now = new Date();
    clock.textContent = now.toLocaleTimeString('ja-JP', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    });
  }

  updateClock();
  window.setInterval(updateClock, 1000);
})();
