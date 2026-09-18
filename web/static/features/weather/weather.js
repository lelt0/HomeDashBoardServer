(function () {
  var roots = document.querySelectorAll('[data-feature-root="weather"]');

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

  function formatDay(item) {
    return item.month + '月' + item.day + '日 ' + item.weekday;
  }

  function setRainClass(root, icon) {
    root.className = root.className
      .replace(/\sfeature-weather--(?:sunny|cloudy|light-rain|rain)\b/g, '');
    if (icon === '☀') root.classList.add('feature-weather--sunny');
    else if (icon === '☁') root.classList.add('feature-weather--cloudy');
    else if (icon === '🌂') root.classList.add('feature-weather--light-rain');
    else if (icon === '☂') root.classList.add('feature-weather--rain');
  }

  function setBackgroundColor(root, icon) {
    var colors = {
      '☀': root.getAttribute('data-bg-sunny'),
      '☁': root.getAttribute('data-bg-cloudy'),
      '🌂': root.getAttribute('data-bg-light-rain'),
      '☂': root.getAttribute('data-bg-rain')
    };
    var color = colors[icon];
    if (color) root.style.backgroundColor = color;
    else root.style.removeProperty('background-color');
  }

  function renderDays(daysElement, days) {
    daysElement.innerHTML = '';
    for (var i = 0; i < days.length; i += 1) {
      var item = days[i];
      var day = document.createElement('div');
      day.className = 'feature-weather__day';

      var date = document.createElement('div');
      date.className = 'feature-weather__day-date';
      if (item.weekday === '土') date.classList.add('feature-weather__day-date--sat');
      else if (item.weekday === '日') date.classList.add('feature-weather__day-date--sun');
      date.textContent = formatDay(item);

      var icon = document.createElement('div');
      icon.className = 'feature-weather__day-icon';
      icon.textContent = item.icon;
      icon.setAttribute('aria-hidden', 'true');

      day.appendChild(date);
      day.appendChild(icon);
      daysElement.appendChild(day);
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
    var days = root.querySelector('[data-role="days"]');
    var fetched = root.querySelector('[data-role="fetched"]');

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

      period.textContent = data.region + 'の ' + periodData.label + ' の雨予想';
      umbrella.textContent = current.icon;
      maxProbability.textContent = formatProbability(current.max_precipitation_probability);
      maxPrecipitation.textContent = formatPrecipitation(current.max_precipitation_mm_per_hour);
      setRainClass(root, current.icon);
      setBackgroundColor(root, current.icon);
      renderDays(days, data.daily);
      fetched.textContent = '最終取得: ' + formatDateTime(fetchedAt);
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
