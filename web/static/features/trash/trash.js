(function () {
  var roots = document.querySelectorAll('[data-feature-root="trash"]');

  roots.forEach(function (root) {
    var overview = root.querySelector('[data-trash-view="overview"]');
    var detail = root.querySelector('[data-trash-view="detail"]');
    var dateElement = root.querySelector('[data-role="date"]');
    var collectionsElement = root.querySelector('[data-role="collections"]');
    if (!overview || !detail || !dateElement || !collectionsElement) return;

    var switchTime = root.getAttribute('data-switch-time') || '08:00';
    var calendar = readJsonAttribute(root, 'data-calendar', { types: [], exclusions: [] });
    var detailTimer = null;
    var boundaryTimer = null;

    function readJsonAttribute(element, name, fallback) {
      var value = element.getAttribute(name);
      if (!value) return fallback;
      try {
        return JSON.parse(value);
      } catch (error) {
        return fallback;
      }
    }

    function parseSwitchTime(value) {
      var parts = value.split(':');
      var hour = Number(parts[0]);
      var minute = Number(parts[1]);
      if (!isFinite(hour) || !isFinite(minute)) return { hour: 8, minute: 0 };
      return { hour: hour, minute: minute };
    }

    function isTomorrow(now) {
      var switchAt = parseSwitchTime(switchTime);
      return now.getHours() > switchAt.hour ||
        (now.getHours() === switchAt.hour && now.getMinutes() >= switchAt.minute);
    }

    function targetDay(now) {
      var date = new Date(now.getFullYear(), now.getMonth(), now.getDate());
      if (isTomorrow(now)) date.setDate(date.getDate() + 1);
      return date;
    }

    function weekdayLabel(date) {
      var weekdays = [
        '日曜日', '月曜日', '火曜日', '水曜日', '木曜日', '金曜日', '土曜日'
      ];
      return weekdays[date.getDay()];
    }

    function formatDate(date, tomorrow) {
      var prefix = tomorrow ? '明日　' : '';
      return prefix + weekdayLabel(date);
    }

    function weeklyMatches(date, weekdays) {
      var jsWeekday = date.getDay();
      var weekdayMap = { sun: 0, mon: 1, tue: 2, wed: 3, thu: 4, fri: 5, sat: 6 };
      for (var i = 0; i < weekdays.length; i += 1) {
        if (weekdayMap[weekdays[i]] === jsWeekday) return true;
      }
      return false;
    }

    function nthWeekdayMatches(date, weekday, nth) {
      var weekdayMap = { sun: 0, mon: 1, tue: 2, wed: 3, thu: 4, fri: 5, sat: 6 };
      if (weekdayMap[weekday] !== date.getDay()) return false;
      var occurrence = Math.floor((date.getDate() - 1) / 7) + 1;
      return nth.indexOf(occurrence) !== -1;
    }

    function parseCalendarDate(value, fallbackYear) {
      var parts = String(value).split('/').map(Number);
      if (parts.length === 3) {
        return new Date(parts[0], parts[1] - 1, parts[2]);
      }
      if (parts.length === 2) {
        return new Date(fallbackYear, parts[0] - 1, parts[1]);
      }
      return null;
    }

    function isExcluded(date) {
      var exclusions = calendar.exclusions || [];
      for (var i = 0; i < exclusions.length; i += 1) {
        var item = exclusions[i];
        var startParts = String(item.start).split('/');
        var endParts = String(item.end).split('/');

        if (startParts.length === 3) {
          var fixedStart = parseCalendarDate(item.start, date.getFullYear());
          var fixedEnd = parseCalendarDate(item.end, date.getFullYear());
          if (date >= fixedStart && date <= fixedEnd) return true;
          continue;
        }

        for (var yearOffset = -1; yearOffset <= 1; yearOffset += 1) {
          var baseYear = date.getFullYear() + yearOffset;
          var start = parseCalendarDate(item.start, baseYear);
          var wrapsYear = Number(startParts[0]) > Number(endParts[0]) ||
            (Number(startParts[0]) === Number(endParts[0]) &&
              Number(startParts[1]) > Number(endParts[1]));
          var endYear = wrapsYear ? baseYear + 1 : baseYear;
          var end = parseCalendarDate(item.end, endYear);
          if (date >= start && date <= end) return true;
        }
      }
      return false;
    }

    function matchesRule(date, rule) {
      if (rule.type === 'weekly') {
        return weeklyMatches(date, rule.weekdays || []);
      }
      if (rule.type === 'nth_weekday') {
        return nthWeekdayMatches(date, rule.weekday, rule.nth || []);
      }
      return false;
    }

    function render(now) {
      var tomorrow = isTomorrow(now);
      var date = targetDay(now);
      dateElement.textContent = formatDate(date, tomorrow);

      collectionsElement.innerHTML = '';
      var collections = [];
      if (!isExcluded(date)) {
        var types = calendar.types || [];
        for (var i = 0; i < types.length; i += 1) {
          var schedule = types[i].schedule || [];
          for (var j = 0; j < schedule.length; j += 1) {
            if (matchesRule(date, schedule[j])) {
              collections.push(types[i]);
              break;
            }
          }
        }
      }

      if (collections.length === 0) {
        var empty = document.createElement('div');
        empty.className = 'feature-trash__no-collection';
        empty.textContent = '回収なし';
        collectionsElement.appendChild(empty);
        return;
      }

      for (var k = 0; k < collections.length; k += 1) {
        var row = document.createElement('div');
        row.className = 'feature-trash__collection';

        var icon = document.createElement('span');
        icon.className = 'feature-trash__icon';
        icon.setAttribute('aria-hidden', 'true');
        icon.textContent = collections[k].icon;

        var name = document.createElement('span');
        name.textContent = collections[k].name;

        row.appendChild(icon);
        row.appendChild(name);
        collectionsElement.appendChild(row);
      }
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

    function scheduleBoundaryUpdate() {
      if (boundaryTimer !== null) window.clearTimeout(boundaryTimer);

      var now = new Date();
      var switchAt = parseSwitchTime(switchTime);
      var midnight = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1, 0, 0, 0, 100);
      var cutoff = new Date(
        now.getFullYear(),
        now.getMonth(),
        now.getDate(),
        switchAt.hour,
        switchAt.minute,
        0,
        100
      );

      var next = cutoff > now ? cutoff : midnight;
      if (midnight < next) next = midnight;

      boundaryTimer = window.setTimeout(function () {
        render(new Date());
        scheduleBoundaryUpdate();
      }, Math.max(100, next.getTime() - now.getTime()));
    }

    root.addEventListener('click', function () {
      if (root.getAttribute('data-detail-open') === 'true') {
        closeDetail();
      } else {
        openDetail();
      }
    });

    root.addEventListener('keydown', function (event) {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        if (root.getAttribute('data-detail-open') === 'true') {
          closeDetail();
        } else {
          openDetail();
        }
      }
    });

    render(new Date());
    scheduleBoundaryUpdate();
  });
})();
