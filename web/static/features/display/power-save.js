(function () {
  var overlay = document.querySelector('[data-role="display-power-save"]');
  var marquee = document.querySelector('[data-role="display-power-save-marquee"]');
  if (!overlay || !marquee) return;

  var timeoutSeconds = Number(overlay.getAttribute('data-idle-timeout-seconds'));
  var messageTemplate = overlay.getAttribute('data-idle-message') || '{date}';
  var speed = Number(overlay.getAttribute('data-idle-marquee-speed'));

  if (!isFinite(timeoutSeconds) || timeoutSeconds <= 0) return;
  if (!isFinite(speed) || speed <= 0) speed = 20;

  var timeoutMs = timeoutSeconds * 1000;
  var timerId = null;
  var sleeping = false;

  function formatTime(date) {
    var hours = String(date.getHours());
    var minutes = String(date.getMinutes());

    if (hours.length < 2) hours = '0' + hours;
    if (minutes.length < 2) minutes = '0' + minutes;

    return hours + ':' + minutes;
  }

  function formatDate(date) {
    const days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

    var year = String(date.getFullYear());
    var month = String(date.getMonth() + 1);
    var date_count = String(date.getDate());
    var dayString = days[date.getDay()];
    
    if (month.length < 2) month = ' ' + month;
    if (date_count.length < 2) date_count = ' ' + date_count;

    return year + '.' + month + '.' + date_count + '(' + dayString + ')';
  }

  function createMessage() {
    return messageTemplate.replace('{time}', formatTime(new Date())).replace('{date}', formatDate(new Date()));
  }

  function updateMessage() {
    marquee.textContent = createMessage();
  }

  function updateAnimationDuration() {
    var width = marquee.offsetWidth;
    var viewportWidth = overlay.clientWidth;
    var distance = viewportWidth + width;
    var duration = distance / speed;

    if (!isFinite(duration) || duration <= 0) duration = 8;
    marquee.style.animationDuration = duration + 's';
  }

  function restartMarquee() {
    marquee.style.animation = 'none';
    marquee.offsetWidth;
    updateMessage();
    updateAnimationDuration();
    marquee.style.animation = '';
  }

  function wake() {
    if (sleeping) {
      sleeping = false;
      document.body.classList.remove('is-display-sleeping');
    }
    resetTimer();
  }

  function sleep() {
    sleeping = true;
    updateMessage();
    document.body.classList.add('is-display-sleeping');
    restartMarquee();
  }

  function resetTimer() {
    if (timerId !== null) {
      window.clearTimeout(timerId);
    }
    timerId = window.setTimeout(sleep, timeoutMs);
  }

  function onActivity() {
    wake();
  }

  overlay.addEventListener('touchstart', onActivity, false);
  overlay.addEventListener('mousedown', onActivity, false);
  document.addEventListener('touchstart', onActivity, false);
  document.addEventListener('mousedown', onActivity, false);
  document.addEventListener('keydown', onActivity, false);
  document.addEventListener('scroll', onActivity, true);

  window.addEventListener('resize', function () {
    if (sleeping) updateAnimationDuration();
  });

  updateMessage();
  resetTimer();
})();
