(function () {
  var button = document.querySelector('[data-action="fullscreen"]');
  if (!button) return;

  function getFullscreenElement() {
    return document.fullscreenElement ||
      document.webkitFullscreenElement ||
      document.mozFullScreenElement ||
      document.msFullscreenElement ||
      null;
  }

  function requestFullscreen() {
    var element = document.documentElement;

    if (element.requestFullscreen) return element.requestFullscreen();
    if (element.webkitRequestFullscreen) return element.webkitRequestFullscreen();
    if (element.mozRequestFullScreen) return element.mozRequestFullScreen();
    if (element.msRequestFullscreen) return element.msRequestFullscreen();
    return null;
  }

  function exitFullscreen() {
    if (document.exitFullscreen) return document.exitFullscreen();
    if (document.webkitExitFullscreen) return document.webkitExitFullscreen();
    if (document.mozCancelFullScreen) return document.mozCancelFullScreen();
    if (document.msExitFullscreen) return document.msExitFullscreen();
    return null;
  }

  function updateButton() {
    var fullscreen = !!getFullscreenElement();
    button.textContent = fullscreen ? '全画面解除' : '全画面';
    button.setAttribute(
      'aria-label',
      fullscreen ? '全画面表示を解除' : '全画面表示'
    );
    if (fullscreen) {
      document.body.classList.add('is-fullscreen');
    } else {
      document.body.classList.remove('is-fullscreen');
    }
  }

  button.addEventListener('click', function () {
    if (getFullscreenElement()) {
      exitFullscreen();
    } else {
      requestFullscreen();
    }
  });

  document.addEventListener('fullscreenchange', updateButton);
  document.addEventListener('webkitfullscreenchange', updateButton);
  document.addEventListener('mozfullscreenchange', updateButton);
  document.addEventListener('MSFullscreenChange', updateButton);

  updateButton();
})();
