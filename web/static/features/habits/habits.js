(function () {
  var roots = document.querySelectorAll('[data-feature-root="habits"]');

  roots.forEach(function (root) {
    var overview = root.querySelector('[data-habits-view="overview"]');
    var recordView = root.querySelector('[data-habits-view="record"]');
    var habitList = root.querySelector('[data-role="habit-list"]');
    var recordList = root.querySelector('[data-role="record-list"]');
    var empty = root.querySelector('[data-role="overview-empty"]');
    var error = root.querySelector('[data-role="error"]');
    var milestone = root.querySelector('[data-role="milestone"]');
    var dateInput = root.querySelector('[data-role="selected-date"]');
    var stateUrl = root.getAttribute('data-state-url') || '/api/features/habits/state';
    var boundary = root.getAttribute('data-day-boundary') || '06:00';
    var state = null;
    var recordOpen = false;

    root.style.setProperty('--habits-log-horizontal-margin',
      (root.getAttribute('data-log-horizontal-margin-px') || '12') + 'px');
    root.style.setProperty('--habits-record-horizontal-margin',
      (root.getAttribute('data-record-horizontal-margin-px') || '12') + 'px');
    var refreshTimer = null;
    var boundaryTimer = null;
    var closeTimer = null;
    var previousStreaks = {};

    function showError(message) {
      error.textContent = message;
      error.hidden = false;
    }

    function clearError() {
      error.hidden = true;
      error.textContent = '';
    }

    function fetchState(selectedDate, done) {
      var url = stateUrl;
      if (selectedDate) url += '?selected_date=' + encodeURIComponent(selectedDate);
      var request = new XMLHttpRequest();
      request.open('GET', url, true);
      request.onreadystatechange = function () {
        if (request.readyState !== 4) return;
        if (request.status < 200 || request.status >= 300) {
          showError('習慣ログを取得できませんでした');
          if (done) done(false);
          return;
        }
        try {
          state = JSON.parse(request.responseText);
        } catch (ignored) {
          showError('習慣ログのデータが不正です');
          if (done) done(false);
          return;
        }
        clearError();
        renderState();
        if (done) done(true);
      };
      request.send();
    }

    function postRecord(habitId, selectedDate, occurrence, method, done) {
      var path = '/api/features/habits/' + encodeURIComponent(habitId) +
        '/records/' + encodeURIComponent(selectedDate) + '/' + encodeURIComponent(occurrence);
      var request = new XMLHttpRequest();
      request.open(method, path, true);
      request.setRequestHeader('Accept', 'application/json');
      request.onreadystatechange = function () {
        if (request.readyState !== 4) return;
        if (request.status < 200 || request.status >= 300) {
          showError('実績を更新できませんでした');
          if (done) done(false);
          return;
        }
        fetchState(recordOpen ? dateInput.value : null, done);
      };
      request.send();
    }

    function parseBoundary(value) {
      var parts = String(value).split(':');
      var hour = Number(parts[0]);
      var minute = Number(parts[1]);
      if (!isFinite(hour) || !isFinite(minute)) return { hour: 6, minute: 0 };
      return { hour: hour, minute: minute };
    }

    function currentHabitDate() {
      var now = new Date();
      var cutoff = parseBoundary(boundary);
      var date = new Date(now.getFullYear(), now.getMonth(), now.getDate());
      if (now.getHours() < cutoff.hour ||
          (now.getHours() === cutoff.hour && now.getMinutes() < cutoff.minute)) {
        date.setDate(date.getDate() - 1);
      }
      return formatDateInput(date);
    }

    function formatDateInput(date) {
      var year = date.getFullYear();
      var month = String(date.getMonth() + 1);
      var day = String(date.getDate());
      if (month.length < 2) month = '0' + month;
      if (day.length < 2) day = '0' + day;
      return year + '-' + month + '-' + day;
    }

    function parseDateInput(value) {
      var parts = String(value).split('-').map(Number);
      if (parts.length !== 3 || !parts[0] || !parts[1] || !parts[2]) return null;
      return new Date(parts[0], parts[1] - 1, parts[2]);
    }

    function shiftDate(value, delta) {
      var date = parseDateInput(value);
      if (!date) return value;
      date.setDate(date.getDate() + delta);
      return formatDateInput(date);
    }

    function isFutureDate(value) {
      var current = currentHabitDate();
      return value > current;
    }

    function setSelectedDate(value) {
      var current = currentHabitDate();
      if (!value || isFutureDate(value)) value = current;
      dateInput.value = value;
      fetchState(value);
    }

    function relativeDayLabel(distance) {
      if (distance === 0) return '今日';
      if (distance === 1) return '昨日';
      if (distance === 2) return '一昨日';
      return distance + '日前';
    }

    function renderState() {
      if (!state) return;
      renderOverview();
      renderRecord();
      scheduleOverviewEmojiFit();
      if (recordOpen && dateInput.value !== state.selected_habit_day) {
        dateInput.value = state.selected_habit_day;
      }
    }

    function historyToEmojis(habit) {
      var result = [];
      var history = habit.history || [];
      for (var i = 0; i < history.length; i += 1) {
        var unit = history[i];
        if (unit.kind === 'past') {
          result.push(unit.achieved ? '🌳️' : '🪾️');
          continue;
        }
        if (unit.completed) {
          result.push('🌳️');
          continue;
        }
        var target = Number(unit.target_count) || 1;
        var count = Math.max(0, Math.min(Number(unit.count) || 0, target));
        for (var j = 0; j < target; j += 1) {
          result.push(j < count ? '🌱️' : '🕳️');
        }
      }
      return result;
    }

    function progressToEmojis(habit) {
      var target = Number(habit.target_count) || 1;
      var count = Math.max(0, Number(habit.period_count) || 0);
      if (count >= target && target === 1) {
        return ['🌳️'];
      }
      if (target === 1) {
        return ['🕳️'];
      }
      count = Math.min(count, target);
      var result = [];
      for (var i = 0; i < target; i += 1) {
        result.push(i < count ? '🌱️' : '🕳️');
      }
      return result;
    }

    function renderOverview() {
      var habits = state.habits || [];
      habitList.innerHTML = '';
      root.style.setProperty('--habit-count', String(Math.max(1, habits.length)));
      empty.hidden = habits.length !== 0;
      if (habits.length === 0) {
        milestone.classList.remove('is-visible');
        milestone.hidden = true;
        milestone.textContent = '';
      }

      for (var i = 0; i < habits.length; i += 1) {
        var habit = habits[i];
        var item = document.createElement('div');
        item.className = 'feature-habits__habit';
        item.setAttribute('data-habit-id', habit.id);

        var iconColumn = document.createElement('div');
        iconColumn.className = 'feature-habits__habit-icon-column';
        var largeIcon = document.createElement('span');
        largeIcon.className = 'feature-habits__habit-icon';
        largeIcon.textContent = habit.emoji;
        largeIcon.setAttribute('aria-hidden', 'true');
        iconColumn.appendChild(largeIcon);

        var main = document.createElement('div');
        main.className = 'feature-habits__habit-main';

        var header = document.createElement('div');
        header.className = 'feature-habits__habit-header';
        var name = document.createElement('div');
        name.className = 'feature-habits__habit-name';
        name.textContent = habit.name;
        var rule = document.createElement('div');
        rule.className = 'feature-habits__habit-rule';
        rule.textContent = habit.rule_text;
        header.appendChild(name);
        header.appendChild(rule);

        var bottom = document.createElement('div');
        bottom.className = 'feature-habits__habit-bottom';

        var emojiList = document.createElement('div');
        emojiList.className = 'feature-habits__emoji-list';
        var emojis = historyToEmojis(habit);
        for (var j = 0; j < emojis.length; j += 1) {
          var emoji = document.createElement('span');
          emoji.className = 'feature-habits__emoji';
          emoji.textContent = emojis[j];
          if (emojis[j] === '🕳️') emoji.className += ' feature-habits__hole--pulse';
          emoji.setAttribute('aria-hidden', 'true');
          emojiList.appendChild(emoji);
        }

        var stats = document.createElement('div');
        stats.className = 'feature-habits__stats';
        var current = document.createElement('div');
        current.className = 'feature-habits__stat-current';
        var currentIcon = document.createElement('span');
        currentIcon.className = 'feature-habits__emoji';
        currentIcon.textContent = '🌳️';
        current.appendChild(currentIcon);
        current.appendChild(document.createTextNode(String(habit.current_streak || 0)));
        var best = document.createElement('div');
        best.className = 'feature-habits__stat-best';
        best.textContent = '最高' + String(habit.best_streak || 0);
        stats.appendChild(current);
        stats.appendChild(best);

        bottom.appendChild(emojiList);
        bottom.appendChild(stats);
        main.appendChild(header);
        main.appendChild(bottom);
        item.appendChild(iconColumn);
        item.appendChild(main);
        habitList.appendChild(item);

        var previous = previousStreaks[habit.id];
        var milestoneValue = habit.tree_milestone_streak;
        if (milestoneValue && habit.current_streak > 0 && habit.current_streak % milestoneValue === 0 &&
            previous !== habit.current_streak) {
          showMilestone();
        }
        previousStreaks[habit.id] = habit.current_streak;
      }
    }

    function renderRecord() {
      if (!state) return;
      var habits = state.record && state.record.habits ? state.record.habits : [];
      recordList.innerHTML = '';
      root.style.setProperty('--record-habit-count', String(Math.max(1, habits.length)));

      for (var i = 0; i < habits.length; i += 1) {
        var habit = habits[i];
        var item = document.createElement('div');
        item.className = 'feature-habits__record-item';
        item.setAttribute('data-habit-id', habit.id);

        var iconColumn = document.createElement('div');
        iconColumn.className = 'feature-habits__record-icon-column';
        var habitIcon = document.createElement('span');
        habitIcon.className = 'feature-habits__record-habit-icon';
        habitIcon.textContent = habit.emoji;
        habitIcon.setAttribute('aria-hidden', 'true');
        iconColumn.appendChild(habitIcon);

        var main = document.createElement('div');
        main.className = 'feature-habits__record-main';

        var header = document.createElement('div');
        header.className = 'feature-habits__record-header';
        var name = document.createElement('div');
        name.className = 'feature-habits__record-name';
        name.textContent = habit.name;
        var summary = document.createElement('div');
        summary.className = 'feature-habits__record-summary';
        summary.textContent = habit.progress_text;
        header.appendChild(name);
        header.appendChild(summary);

        var controls = document.createElement('div');
        controls.className = 'feature-habits__record-controls';

        var progress = document.createElement('div');
        progress.className = 'feature-habits__progress';
        var icons = progressToEmojis(habit);
        var selectedOccurrences = habit.selected_occurrences || [];
        for (var j = 0; j < icons.length; j += 1) {
          var iconButton = document.createElement('button');
          iconButton.type = 'button';
          iconButton.className = 'feature-habits__progress-icon';
          iconButton.textContent = icons[j];
          if (icons[j] === '🌱️' || icons[j] === '🌳️') {
            var occurrenceNumber = j + 1;
            var isSelectedDayOccurrence = selectedOccurrences.indexOf(occurrenceNumber) !== -1;
            if (isSelectedDayOccurrence) {
              iconButton.className += ' feature-habits__progress-icon--active';
            } else {
              iconButton.className += ' feature-habits__progress-icon--dim';
            }
          }
          iconButton.setAttribute('aria-label', icons[j] === '🕳️' ? '未達成枠' : '達成');
          if (icons[j] === '🕳️') {
            iconButton.setAttribute('data-action', 'add-one');
            iconButton.setAttribute('data-habit-id', habit.id);
          } else if ((habit.day_count || 0) > 0 && (Number(habit.target_count) > 1 || icons[j] === '🌳️')) {
            iconButton.setAttribute('data-action', 'remove-one');
            iconButton.setAttribute('data-habit-id', habit.id);
          } else {
            iconButton.className += ' feature-habits__progress-icon--locked';
            iconButton.disabled = true;
          }
          progress.appendChild(iconButton);
        }

        var adjust = document.createElement('div');
        adjust.className = 'feature-habits__adjust-group';

        var minus = document.createElement('button');
        minus.type = 'button';
        minus.className = 'button feature-habits__adjust';
        minus.textContent = '−';
        minus.setAttribute('data-action', 'remove-one');
        minus.setAttribute('data-habit-id', habit.id);
        minus.disabled = (habit.day_count || 0) === 0;

        var plus = document.createElement('button');
        plus.type = 'button';
        plus.className = 'button feature-habits__adjust';
        plus.textContent = '+';
        plus.setAttribute('data-action', 'add-one');
        plus.setAttribute('data-habit-id', habit.id);

        adjust.appendChild(minus);
        adjust.appendChild(plus);
        controls.appendChild(progress);
        controls.appendChild(adjust);
        main.appendChild(header);
        main.appendChild(controls);
        item.appendChild(iconColumn);
        item.appendChild(main);
        recordList.appendChild(item);
      }
    }

    function fitOverviewEmojis() {
      if (overview.hidden) return;
      var lists = habitList.querySelectorAll('.feature-habits__emoji-list');
      lists.forEach(function (list) {
        var size = Math.max(14, Math.min(48, Math.floor(window.innerWidth * 0.055)));
        list.style.setProperty('--habit-emoji-size', size + 'px');
      });
    }

    function scheduleOverviewEmojiFit() {
      var schedule = window.requestAnimationFrame || function (callback) {
        return window.setTimeout(callback, 0);
      };
      schedule(function () {
        fitOverviewEmojis();
      });
    }

    function showMilestone() {
      if (!state || !state.habits || state.habits.length === 0) return;
      milestone.textContent = '✨️';
      milestone.hidden = false;
      milestone.classList.remove('is-visible');
      void milestone.offsetWidth;
      milestone.classList.add('is-visible');
      window.setTimeout(function () {
        milestone.classList.remove('is-visible');
        milestone.hidden = true;
        milestone.textContent = '';
      }, 3100);
    }

    function openRecord() {
      recordOpen = true;
      overview.hidden = true;
      recordView.hidden = false;
      var current = currentHabitDate();
      dateInput.max = current;
      dateInput.value = current;
      fetchState(current);
      resetCloseTimer();
    }

    function closeRecord() {
      recordOpen = false;
      overview.hidden = false;
      recordView.hidden = true;
      scheduleOverviewEmojiFit();
      if (closeTimer !== null) {
        window.clearTimeout(closeTimer);
        closeTimer = null;
      }
    }

    function resetCloseTimer() {
      if (!recordOpen) return;
      if (closeTimer !== null) window.clearTimeout(closeTimer);
      closeTimer = window.setTimeout(closeRecord, 10000);
    }

    function scheduleBoundaryUpdate() {
      if (boundaryTimer !== null) window.clearTimeout(boundaryTimer);
      var now = new Date();
      var cutoff = parseBoundary(boundary);
      var next = new Date(now.getFullYear(), now.getMonth(), now.getDate(), cutoff.hour, cutoff.minute, 0, 50);
      if (next <= now) next.setDate(next.getDate() + 1);
      boundaryTimer = window.setTimeout(function () {
        fetchState(recordOpen ? dateInput.value : null);
        dateInput.max = currentHabitDate();
        scheduleBoundaryUpdate();
      }, Math.max(100, next.getTime() - now.getTime()));
    }

    function schedulePeriodicRefresh() {
      if (refreshTimer !== null) window.clearInterval(refreshTimer);
      refreshTimer = window.setInterval(function () {
        fetchState(recordOpen ? dateInput.value : null);
      }, 10 * 60 * 1000);
    }

    root.addEventListener('click', function (event) {
      var actionElement = event.target.closest('[data-action]');
      if (!actionElement) {
        if (event.target.closest('[data-habits-view=\"overview\"]')) openRecord();
        return;
      }
      resetCloseTimer();
      var action = actionElement.getAttribute('data-action');
      if (action === 'open-record') {
        openRecord();
        return;
      }
      if (action === 'close-record') {
        closeRecord();
        return;
      }
      if (action === 'previous-day') {
        setSelectedDate(shiftDate(dateInput.value, -1));
        resetCloseTimer();
        return;
      }
      if (action === 'today') {
        setSelectedDate(currentHabitDate());
        resetCloseTimer();
        return;
      }
      if (action === 'next-day') {
        var next = shiftDate(dateInput.value, 1);
        if (!isFutureDate(next)) setSelectedDate(next);
        resetCloseTimer();
        return;
      }
      if (action === 'add-one' || action === 'remove-one') {
        if (!recordOpen) return;
        var habitId = actionElement.getAttribute('data-habit-id');
        var target = null;
        for (var i = 0; i < state.record.habits.length; i += 1) {
          if (state.record.habits[i].id === habitId) {
            target = state.record.habits[i];
            break;
          }
        }
        if (!target) return;
        var selectedDate = dateInput.value;
        if (action === 'add-one') {
          postRecord(habitId, selectedDate, (target.day_count || 0) + 1, 'PUT', function () {
            resetCloseTimer();
          });
        } else if ((target.day_count || 0) > 0) {
          postRecord(habitId, selectedDate, target.day_count, 'DELETE', function () {
            resetCloseTimer();
          });
        }
      }
    });

    root.addEventListener('keydown', function (event) {
      resetCloseTimer();
      if (event.target === overview && (event.key === 'Enter' || event.key === ' ')) {
        event.preventDefault();
        openRecord();
      }
    });

    root.addEventListener('input', function () {
      resetCloseTimer();
    });

    root.addEventListener('touchstart', function () {
      resetCloseTimer();
    });

    root.addEventListener('focusin', function () {
      resetCloseTimer();
    });

    root.addEventListener('change', function (event) {
      resetCloseTimer();
      if (event.target === dateInput) {
        setSelectedDate(dateInput.value);
      }
    });

    root.addEventListener('scroll', function () {
      resetCloseTimer();
    }, true);

    document.addEventListener('visibilitychange', function () {
      if (!document.hidden) {
        fetchState(recordOpen ? dateInput.value : null);
      }
    });

    window.addEventListener('resize', function () {
      if (!overview.hidden) fitOverviewEmojis();
    });

    dateInput.max = currentHabitDate();
    fetchState(null);
    scheduleBoundaryUpdate();
    schedulePeriodicRefresh();
  });
})();
