(function () {
  var calendar = document.querySelector('[data-role="trash-calendar"]');
  if (!calendar) {
    return;
  }

  var delaySeconds = Number(calendar.getAttribute('data-refresh-after-seconds'));
  if (!isFinite(delaySeconds) || delaySeconds <= 0) {
    return;
  }

  window.setTimeout(function () {
    window.location.reload();
  }, delaySeconds * 1000);
})();
