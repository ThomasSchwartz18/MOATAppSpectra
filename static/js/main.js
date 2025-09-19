const appTracker = (() => {
  const ctx = window.APP_CONTEXT || {};
  const user = ctx.user || {};
  const endpoints = ctx.tracking || {};

  if (!user || !user.role || !endpoints || (!endpoints.clickUrl && !endpoints.sessionStartUrl)) {
    return null;
  }

  let sessionId = endpoints.sessionId || null;
  let sessionClosed = false;

  const nowIso = () => new Date().toISOString();

  const send = (url, payload, { useBeacon } = {}) => {
    if (!url) return Promise.resolve();
    const body = JSON.stringify(payload);
    if (useBeacon && navigator.sendBeacon) {
      const blob = new Blob([body], { type: 'application/json' });
      navigator.sendBeacon(url, blob);
      return Promise.resolve();
    }
    return fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body,
    }).then((res) => {
      if (!res.ok) {
        throw new Error(`Request failed: ${res.status}`);
      }
      return res
        .json()
        .catch(() => ({}));
    });
  };

  return {
    start(extraPayload = {}) {
      if (!endpoints.sessionStartUrl) return Promise.resolve();
      const payload = {
        sessionId,
        timestamp: nowIso(),
        userId: user.id || null,
        userRole: user.role || null,
        ...extraPayload,
      };
      return send(endpoints.sessionStartUrl, payload)
        .then((data) => {
          if (data && data.session_id) {
            sessionId = data.session_id;
            if (window.APP_CONTEXT && window.APP_CONTEXT.tracking) {
              window.APP_CONTEXT.tracking.sessionId = sessionId;
            }
          }
          sessionClosed = false;
        })
        .catch((err) => {
          // eslint-disable-next-line no-console
          console.warn('Failed to start tracking session', err);
        });
    },
    recordClick(eventName, context = {}, metadata) {
      if (!endpoints.clickUrl || !eventName) return;
      const payload = {
        sessionId,
        timestamp: nowIso(),
        event: eventName,
        context,
        metadata: metadata || undefined,
        userId: user.id || null,
        userRole: user.role || null,
      };
      send(endpoints.clickUrl, payload).catch(() => {});
    },
    end(reason = 'client', options = {}) {
      if (!endpoints.sessionEndUrl || sessionClosed) return;
      sessionClosed = true;
      const payload = {
        sessionId,
        timestamp: nowIso(),
        reason,
        userId: user.id || null,
        userRole: user.role || null,
      };
      send(endpoints.sessionEndUrl, payload, { useBeacon: options.useBeacon === true }).catch(
        () => {}
      );
    },
  };
})();

window.APP_TRACKER = appTracker;

function renderLinePreview({ endpoint, canvasId, infoId, onClickHref }) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;

  if (onClickHref) {
    canvas.style.cursor = 'pointer';
    canvas.addEventListener('click', () => {
      window.location.href = onClickHref;
    });
  }

  if (!endpoint) return;

  fetch(endpoint)
    .then((res) => {
      if (!res.ok) {
        throw new Error(`Request failed with status ${res.status}`);
      }
      return res.json();
    })
    .then((data) => {
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      const isFalseCallPreview = Array.isArray(data.avg_false_calls);
      const labels =
        data.labels || (isFalseCallPreview ? data.models : undefined) || [];
      const values =
        data.values ||
        (isFalseCallPreview
          ? data.avg_false_calls
          : data.yields || data.avg_false_calls) || [];

      const chartConfig = {
        type: 'line',
        data: {
          labels,
          datasets: [
            {
              data: values,
              borderColor: '#000',
              backgroundColor: '#000',
              pointBackgroundColor: '#000',
              pointBorderColor: '#000',
              pointRadius: 3,
              fill: false,
              tension: 0,
              borderWidth: 2,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: { enabled: false },
          },
          elements: {
            line: { borderWidth: 2 },
          },
          scales: isFalseCallPreview
            ? {
                x: { display: false, grid: { display: false }, ticks: { display: false } },
                y: { beginAtZero: true, display: false, grid: { display: false }, ticks: { display: false } },
              }
            : {
                x: {
                  display: true,
                  title: { display: true, text: 'Date' },
                  grid: { display: false },
                  ticks: { display: true },
                  border: { display: true },
                },
                y: {
                  beginAtZero: true,
                  display: true,
                  title: { display: true, text: 'Yield' },
                  grid: { display: false },
                  ticks: { display: true },
                  border: { display: true },
                },
              },
        },
        plugins: [],
      };

      if (isFalseCallPreview) {
        chartConfig.plugins.push({
          id: 'hLines',
          afterDraw(chart) {
            const {
              ctx: chartCtx,
              chartArea: { left, right, top, bottom },
              scales,
            } = chart;
            const yScale = scales.y;
            if (!yScale) return;

            const lines = [
              { value: 20, color: 'red' },
              { value: 10, color: 'gold' },
              { value: 5, color: 'green' },
            ];

            chartCtx.save();
            chartCtx.setLineDash([4, 4]);
            lines.forEach((line) => {
              const y = yScale.getPixelForValue(line.value);
              if (y >= top && y <= bottom) {
                chartCtx.beginPath();
                chartCtx.moveTo(left, y);
                chartCtx.lineTo(right, y);
                chartCtx.strokeStyle = line.color;
                chartCtx.lineWidth = 1;
                chartCtx.stroke();
              }
            });
            chartCtx.restore();
          },
        });
      }

      // eslint-disable-next-line no-undef
      new Chart(ctx, chartConfig);

      if (infoId) {
        const infoEl = document.getElementById(infoId);
        if (infoEl) {
          if (isFalseCallPreview) {
            const avg = Number.isFinite(Number(data.overall_avg))
              ? Number(data.overall_avg).toFixed(2)
              : '0';
            const start = data.start_date || 'N/A';
            const end = data.end_date || 'N/A';
            infoEl.textContent = `${start} to ${end} | Avg False Calls: ${avg}`;
          } else if (data && Object.prototype.hasOwnProperty.call(data, 'avg_yield')) {
            const avgYield = Number.isFinite(Number(data.avg_yield))
              ? Number(data.avg_yield).toFixed(1)
              : '0';
            const start = data.start_date || 'N/A';
            const end = data.end_date || 'N/A';
            infoEl.textContent = `${start} to ${end} | Avg Yield: ${avgYield}%`;
          }
        }
      }
    })
    .catch((err) => {
      // eslint-disable-next-line no-console
      console.error('Failed to load preview', err);
    });
}

document.addEventListener('DOMContentLoaded', () => {
  const previewConfigs = [
    {
      endpoint: '/moat_preview',
      canvasId: 'ppmAnalysisPreview',
      onClickHref: '/analysis/ppm?preset=avg_false_calls_per_assembly',
    },
    {
      endpoint: '/aoi_preview',
      canvasId: 'aoiFiAnalysisPreview',
      onClickHref: '/analysis/aoi/grades/view',
    },
    {
      endpoint: '/daily_reports_preview',
      canvasId: 'dailyReportsPreview',
      onClickHref: '/reports/aoi_daily',
    },
    {
      endpoint: '/forecast_preview',
      canvasId: 'assemblyForecastPreview',
      onClickHref: '/tools/assembly-forecast',
    },
  ];

  previewConfigs.forEach((config) => {
    renderLinePreview(config);
  });

  const tracker = window.APP_TRACKER;
  if (tracker) {
    tracker.start();

    document.body.addEventListener('click', (event) => {
      const actionable = event.target.closest(
        '[data-track-event], [data-track-session-end], a, button'
      );
      if (!actionable || actionable.dataset.trackIgnore === 'true') return;

      if (actionable.dataset.trackSessionEnd === 'true') {
        tracker.end('logout', { useBeacon: true });
      }

      const tag = actionable.tagName.toLowerCase();
      const eventName =
        actionable.dataset.trackEvent || (tag === 'a' ? 'navigate' : `${tag}-click`);

      const label = actionable.dataset.trackLabel || actionable.textContent || '';
      const context = {
        id: actionable.id || null,
        href: actionable.getAttribute('href') || null,
        text: label.trim().slice(0, 160),
        role: actionable.getAttribute('role') || null,
        classes: actionable.className || null,
        dataset: actionable.dataset.trackContext || null,
      };

      tracker.recordClick(eventName, context);
    });

    window.addEventListener('beforeunload', () => {
      tracker.end('page-unload', { useBeacon: true });
    });
  }

  // Auto-hide navbar on scroll down; reveal on scroll up
  const nav = document.querySelector('.navbar');
  if (nav) {
    let lastY = window.scrollY;
    window.addEventListener('scroll', () => {
      const y = window.scrollY;
      const goingDown = y > lastY;
      if (goingDown && y > 10) nav.classList.add('navbar--hidden');
      else nav.classList.remove('navbar--hidden');
      lastY = y;
    }, { passive: true });
  }

  // Tab navigation for admin console and other tabbed layouts
  const tabContainers = document.querySelectorAll('[data-tabs]');
  tabContainers.forEach((container) => {
    const tabs = Array.from(container.querySelectorAll('[role="tab"]'));
    const panels = Array.from(container.querySelectorAll('[role="tabpanel"]'));

    const activateTab = (targetId) => {
      tabs.forEach((tab) => {
        const isActive = tab.dataset.tabTarget === targetId;
        tab.classList.toggle('is-active', isActive);
        tab.setAttribute('aria-selected', isActive ? 'true' : 'false');
        tab.setAttribute('tabindex', isActive ? '0' : '-1');
      });

      panels.forEach((panel) => {
        const isActive = panel.dataset.tabPanel === targetId;
        panel.classList.toggle('is-active', isActive);
        panel.setAttribute('aria-hidden', isActive ? 'false' : 'true');
      });
    };

    tabs.forEach((tab) => {
      tab.addEventListener('click', () => {
        activateTab(tab.dataset.tabTarget);
      });

      tab.addEventListener('keydown', (event) => {
        if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
        event.preventDefault();
        const currentIndex = tabs.indexOf(tab);
        if (currentIndex === -1) return;
        const offset = event.key === 'ArrowLeft' ? -1 : 1;
        let nextIndex = (currentIndex + offset + tabs.length) % tabs.length;
        const nextTab = tabs[nextIndex];
        if (nextTab) {
          nextTab.focus();
          activateTab(nextTab.dataset.tabTarget);
        }
      });
    });
  });
});
