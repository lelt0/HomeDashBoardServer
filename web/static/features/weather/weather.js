(function () {
  var roots = document.querySelectorAll('[data-feature-root="weather"]');
  var GRAPH_MAX_MM_PER_HOUR = 10.0;

  function formatDateTime(isoString) {
    var date = new Date(isoString);
    if (isNaN(date.getTime())) return '--';
    return (
      (date.getMonth() + 1) + '月' +
      date.getDate() + '日 ' +
      ('0' + date.getHours()).slice(-2) + ':' +
      ('0' + date.getMinutes()).slice(-2)
    );
  }

  function formatPrecipitation(value) {
    if (value === null || typeof value === 'undefined') return '--';
    return Number(value).toFixed(1) + ' mm/h';
  }

  function formatProbability(value) {
    if (value === null || typeof value === 'undefined') return '--';
    return Math.round(Number(value)) + '%';
  }

  function setBackgroundColor(root, backgroundState) {
    var colors = {
      sunny: root.getAttribute('data-bg-sunny'),
      light_rain: root.getAttribute('data-bg-light-rain'),
      rain: root.getAttribute('data-bg-rain')
    };
    var color = colors[backgroundState];
    if (color) root.style.backgroundColor = color;
    else root.style.removeProperty('background-color');
  }

  function precipitationBarHeight(value) {
    var amount = Number(value);
    if (!isFinite(amount) || amount <= 0) return 0;
    return Math.min(amount, GRAPH_MAX_MM_PER_HOUR) / GRAPH_MAX_MM_PER_HOUR * 100;
  }

  function precipitationBarOpacity(value) {
    var probability = Number(value);
    if (!isFinite(probability)) return 0.5;
    probability = Math.max(0, Math.min(100, probability));
    return 0.18 + 0.82 * probability / 100;
  }

  function setGraphThreshold(thresholdElement, labelElement, thresholdValue) {
    var threshold = Number(thresholdValue);
    if (!isFinite(threshold)) {
      thresholdElement.hidden = true;
      return;
    }

    var clamped = Math.max(0, Math.min(GRAPH_MAX_MM_PER_HOUR, threshold));
    thresholdElement.style.setProperty(
      '--weather-threshold-position',
      (100 - clamped / GRAPH_MAX_MM_PER_HOUR * 100) + '%'
    );
    thresholdElement.style.removeProperty('top');
    thresholdElement.style.removeProperty('bottom');
    labelElement.textContent = threshold.toFixed(1);
    thresholdElement.hidden = false;
  }

  function renderHours(hoursElement, hours) {
    hoursElement.innerHTML = '';
    for (var i = 0; i < hours.length; i += 1) {
      var item = hours[i];
      var hour = document.createElement('div');
      hour.className = 'feature-weather__hour';

      var label = document.createElement('div');
      label.className = 'feature-weather__hour-label';
      label.textContent = item.label;

      var icon = document.createElement('div');
      icon.className = 'feature-weather__hour-icon';
      icon.textContent = item.icon;
      icon.setAttribute('aria-hidden', 'true');

      var plot = document.createElement('div');
      plot.className = 'feature-weather__hour-plot';

      var bar = document.createElement('div');
      bar.className = 'feature-weather__hour-bar';
      bar.style.height = precipitationBarHeight(item.precipitation_mm_per_hour) + '%';
      bar.style.opacity = precipitationBarOpacity(item.precipitation_probability);
      bar.setAttribute('aria-hidden', 'true');

      var value = document.createElement('div');
      value.className = 'feature-weather__hour-value';
      value.textContent = item.precipitation_mm_per_hour === null ||
        typeof item.precipitation_mm_per_hour === 'undefined'
        ? '--'
        : Number(item.precipitation_mm_per_hour).toFixed(1) +
          'mm/' + formatProbability(item.precipitation_probability);

      plot.appendChild(bar);

      hour.appendChild(label);
      hour.appendChild(icon);
      hour.appendChild(plot);
      hour.appendChild(value);
      hoursElement.appendChild(hour);
    }
  }

  roots.forEach(function (root) {
    var overview = root.querySelector('[data-weather-view="overview"]');
    var detail = root.querySelector('[data-weather-view="detail"]');
    var period = root.querySelector('[data-role="period"]');
    var umbrella = root.querySelector('[data-role="umbrella"]');
    var maxProbability = root.querySelector('[data-role="max-probability"]');
    var maxPrecipitation = root.querySelector('[data-role="max-precipitation"]');
    var error = root.querySelector('[data-role="error"]');
    var detailTitle = root.querySelector('[data-role="detail-title"]');
    var hours = root.querySelector('[data-role="hours"]');
    var graphThreshold = root.querySelector('[data-role="graph-threshold"]');
    var graphThresholdLabel = root.querySelector('[data-role="graph-threshold-label"]');

    var detailTimer = null;
    var retryTimer = null;
    var hourlyTimer = null;
    var staleTimer = null;
    var lastFetchedAt = null;
    var hasData = false;
    var fetching = false;

    function showOverviewError(message) {
      if (message) {
        error.textContent = message;
        error.hidden = false;
      } else {
        error.textContent = '';
        error.hidden = true;
      }
    }

    function renderData(data, fetchedAt) {
      var current = data.current;
      var periodData = data.period;

      period.textContent = data.region + 'の ' + periodData.label + ' の天気予報';
      umbrella.textContent = current.icon;
      maxProbability.textContent = formatProbability(current.max_precipitation_probability);
      maxPrecipitation.textContent = formatPrecipitation(current.max_precipitation_mm_per_hour);
      setBackgroundColor(root, current.background_state);
      setGraphThreshold(
        graphThreshold,
        graphThresholdLabel,
        root.getAttribute('data-light-rain-threshold')
      );
      renderHours(hours, data.hours);
      lastFetchedAt = new Date(fetchedAt);
      hasData = true;
      updateStaleState();
    }

    function updateStaleState() {
      if (!hasData || !lastFetchedAt) return;
      var ageMs = new Date().getTime() - lastFetchedAt.getTime();
      if (ageMs >= 2 * 60 * 60 * 1000) {
        showOverviewError('天気予報を更新できません（最終取得から2時間以上経過）');
      } else {
        showOverviewError('');
      }
    }

    function refresh() {
      if (fetching) return;
      fetching = true;

      fetch('/api/features/weather', { cache: 'no-store' })
        .then(function (response) {
          if (!response.ok) throw new Error('HTTP ' + response.status);
          return response.json();
        })
        .then(function (result) {
          if (!result || !result.data || !result.fetched_at) {
            throw new Error('Invalid weather response');
          }
          renderData(result.data, result.fetched_at);
          if (retryTimer !== null) {
            window.clearTimeout(retryTimer);
            retryTimer = null;
          }

          if (result.ok === false) scheduleRetry();
        })
        .catch(function () {
          if (!hasData) showOverviewError('天気予報を取得できません');
          else updateStaleState();
          scheduleRetry();
        })
        .finally(function () {
          fetching = false;
        });
    }

    function scheduleRetry() {
      if (retryTimer !== null) return;
      retryTimer = window.setTimeout(function () {
        retryTimer = null;
        refresh();
      }, 10 * 60 * 1000);
    }

    function scheduleHourlyUpdate() {
      if (hourlyTimer !== null) window.clearTimeout(hourlyTimer);

      var now = new Date();
      var next = new Date(
        now.getFullYear(),
        now.getMonth(),
        now.getDate(),
        now.getHours() + 1,
        0,
        0,
        100
      );

      hourlyTimer = window.setTimeout(function () {
        hourlyTimer = null;
        refresh();
        scheduleHourlyUpdate();
      }, Math.max(100, next.getTime() - now.getTime()));
    }

    function openDetail() {
      var now = new Date();
      detailTitle.textContent =
        ('0' + now.getHours()).slice(-2) + ':' +
        ('0' + now.getMinutes()).slice(-2) + 'から1時間ごと';
      overview.hidden = true;
      detail.hidden = false;
      root.setAttribute('data-detail-open', 'true');
      if (detailTimer !== null) window.clearTimeout(detailTimer);
      detailTimer = window.setTimeout(closeDetail, 10000);
    }

    function closeDetail() {
      overview.hidden = false;
      detail.hidden = true;
      root.setAttribute('data-detail-open', 'false');
      if (detailTimer !== null) {
        window.clearTimeout(detailTimer);
        detailTimer = null;
      }
    }

    root.addEventListener('click', function () {
      if (root.getAttribute('data-detail-open') === 'true') closeDetail();
      else openDetail();
    });

    root.addEventListener('keydown', function (event) {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        if (root.getAttribute('data-detail-open') === 'true') closeDetail();
        else openDetail();
      }
    });

    staleTimer = window.setInterval(updateStaleState, 60 * 1000);
    root.setAttribute('data-detail-open', 'false');
    refresh();
    scheduleHourlyUpdate();

    window.addEventListener('beforeunload', function () {
      if (detailTimer !== null) window.clearTimeout(detailTimer);
      if (retryTimer !== null) window.clearTimeout(retryTimer);
      if (hourlyTimer !== null) window.clearTimeout(hourlyTimer);
      if (staleTimer !== null) window.clearInterval(staleTimer);
    });
  });
})();
