(function () {
  var detailButtons = document.querySelectorAll('[data-action="tile-detail"]');
  var backButtons = document.querySelectorAll('[data-action="tile-detail-back"]');

  function setDetailMode(tile, enabled) {
    if (!tile) return;

    var overview = tile.querySelector('[data-tile-view="overview"]');
    var detail = tile.querySelector('[data-tile-view="detail"]');
    if (!overview || !detail) return;

    overview.hidden = enabled;
    detail.hidden = !enabled;
    tile.setAttribute('data-tile-detail-open', enabled ? 'true' : 'false');

    if (enabled) {
      var back = detail.querySelector('[data-action="tile-detail-back"]');
      if (back) back.focus();
    }
  }

  detailButtons.forEach(function (button) {
    button.addEventListener('click', function () {
      var tile = button.closest('.tile');
      setDetailMode(tile, true);
    });
  });

  backButtons.forEach(function (button) {
    button.addEventListener('click', function () {
      var tile = button.closest('.tile');
      setDetailMode(tile, false);
    });
  });
})();
