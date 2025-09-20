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

    // Session tracking should only end on explicit sign-outs triggered via
    // data-track-session-end="true" elements. Removing the beforeunload
    // listener prevents refreshes from prematurely closing the session.
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

  const chatContainer = document.getElementById('bug-chat-container');
  if (chatContainer) {
    const endpoint = chatContainer.dataset.endpoint;
    const trigger = chatContainer.querySelector('.bug-chat-trigger');
    const panel = chatContainer.querySelector('.bug-chat-panel');
    const closeButton = chatContainer.querySelector('.bug-chat-close');
    const messageStream = chatContainer.querySelector('.bug-chat-messages');
    const form = chatContainer.querySelector('.bug-chat-form');
    const fields = chatContainer.querySelector('.bug-chat-fields');
    const authGuard = chatContainer.querySelector('.bug-chat-auth-guard');
    const submitButton = chatContainer.querySelector('.bug-chat-submit');
    const resetButton = chatContainer.querySelector('.bug-chat-reset');
    const attachmentsInput = form ? form.querySelector('input[name="attachments"]') : null;

    if (panel) {
      panel.setAttribute('aria-hidden', 'true');
    }

    let isSignedIn = chatContainer.dataset.signedIn === 'true';
    let isSubmitting = false;
    let lastSubmissionKey = null;
    let lastSubmissionTime = 0;

    const defaultSubmitLabel = submitButton ? submitButton.textContent : '';
    const userDisplayName = (chatContainer.dataset.username || '').trim() || 'there';

    const appendMessage = (text, role = 'system') => {
      if (!messageStream || !text) return;
      const wrapper = document.createElement('div');
      wrapper.classList.add('bug-chat-message');
      if (role) {
        wrapper.classList.add(role);
      }
      const paragraph = document.createElement('p');
      paragraph.textContent = text;
      wrapper.appendChild(paragraph);
      messageStream.appendChild(wrapper);
      messageStream.scrollTop = messageStream.scrollHeight;
    };

    const updateAuthState = () => {
      if (!form) return;
      const shouldLock = !isSignedIn;
      if (authGuard) {
        authGuard.hidden = !shouldLock;
      }
      if (fields) {
        fields.disabled = shouldLock;
      }
      if (submitButton) {
        submitButton.disabled = shouldLock || isSubmitting;
      }
    };

    const primeConversation = () => {
      if (messageStream) {
        messageStream.innerHTML = '';
      }
      appendMessage(`Hi ${userDisplayName}!`, 'system');
      appendMessage('Use this space to report bugs or share quick feedback with the support team.', 'system');
      if (!isSignedIn) {
        appendMessage('Sign in to send a new report.', 'system');
      }
    };

    const setSubmitting = (state) => {
      isSubmitting = state;
      if (submitButton) {
        submitButton.disabled = state || !isSignedIn;
        submitButton.textContent = state ? 'Sending…' : defaultSubmitLabel;
      }
    };

    const openPanel = () => {
      if (!panel || !trigger) return;
      chatContainer.classList.add('is-open');
      panel.hidden = false;
      panel.setAttribute('aria-hidden', 'false');
      trigger.setAttribute('aria-expanded', 'true');
      window.requestAnimationFrame(() => {
        panel.focus();
      });
    };

    const closePanel = () => {
      if (!panel || !trigger) return;
      chatContainer.classList.remove('is-open');
      panel.hidden = true;
      panel.setAttribute('aria-hidden', 'true');
      trigger.setAttribute('aria-expanded', 'false');
      trigger.focus();
    };

    const togglePanel = () => {
      if (!panel) return;
      const willOpen = panel.hasAttribute('hidden');
      if (willOpen) openPanel();
      else closePanel();
    };

    const buildSubmissionKey = (values) => {
      return JSON.stringify([
        values.title,
        values.description,
        values.priority,
        values.severity,
        values.environment,
      ]);
    };

    const parseResponse = async (response) => {
      const contentType = response.headers.get('content-type') || '';
      let payload = null;
      if (contentType.includes('application/json')) {
        payload = await response.json().catch(() => null);
      } else {
        const text = await response.text().catch(() => '');
        if (text) {
          payload = { message: text };
        }
      }
      if (!response.ok) {
        const error = new Error(
          (payload && (payload.message || payload.error)) || 'Unable to submit the bug report.'
        );
        error.status = response.status;
        error.payload = payload;
        throw error;
      }
      return payload;
    };

    const markComplete = (data) => {
      if (submitButton) {
        submitButton.textContent = 'Report sent';
        submitButton.disabled = true;
      }
      if (fields) {
        fields.disabled = true;
      }
      if (resetButton) {
        resetButton.hidden = false;
      }
      const identifier = data && (data.id || data.report_id);
      if (identifier) {
        appendMessage(`Report #${identifier} has been submitted successfully.`, 'status');
      } else {
        appendMessage('Your report has been submitted successfully.', 'status');
      }
    };

    const resetForm = () => {
      if (!form) return;
      form.reset();
      if (fields) {
        fields.disabled = !isSignedIn;
      }
      if (submitButton) {
        submitButton.textContent = defaultSubmitLabel;
        submitButton.disabled = !isSignedIn;
      }
      if (resetButton) {
        resetButton.hidden = true;
      }
      lastSubmissionKey = null;
      lastSubmissionTime = 0;
      primeConversation();
    };

    if (resetButton) {
      resetButton.addEventListener('click', () => {
        resetForm();
        if (!panel || panel.hasAttribute('hidden')) {
          openPanel();
        }
      });
    }

    if (trigger) {
      trigger.addEventListener('click', () => {
        togglePanel();
      });
    }

    if (closeButton) {
      closeButton.addEventListener('click', () => {
        closePanel();
      });
    }

    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && chatContainer.classList.contains('is-open')) {
        closePanel();
      }
    });

    if (form && endpoint) {
      form.addEventListener('submit', (event) => {
        event.preventDefault();
        if (!isSignedIn) {
          appendMessage('Please sign in to send your report.', 'error');
          return;
        }
        if (isSubmitting) {
          return;
        }

        const formData = new FormData(form);
        const values = {
          title: (formData.get('title') || '').toString().trim(),
          description: (formData.get('description') || '').toString().trim(),
          priority: (formData.get('priority') || '').toString().trim(),
          severity: (formData.get('severity') || '').toString().trim(),
          environment: (formData.get('environment') || '').toString().trim(),
        };

        if (!values.title || !values.description) {
          appendMessage('A title and description are required before submitting.', 'error');
          return;
        }

        const submissionKey = buildSubmissionKey(values);
        const now = Date.now();
        if (
          lastSubmissionKey &&
          submissionKey === lastSubmissionKey &&
          now - lastSubmissionTime < 15000
        ) {
          appendMessage(
            'It looks like you already submitted this report. Add more details or wait a moment before trying again.',
            'system'
          );
          return;
        }

        appendMessage(`"${values.title}"`, 'user');
        if (values.description) {
          appendMessage(values.description, 'user');
        }
        appendMessage('Submitting your report…', 'system');

        setSubmitting(true);

        const payload = new FormData();
        payload.append('title', values.title);
        payload.append('description', values.description);
        if (values.priority) payload.append('priority', values.priority);
        if (values.severity) payload.append('severity', values.severity);
        if (values.environment) payload.append('environment', values.environment);
        if (attachmentsInput && attachmentsInput.files) {
          Array.from(attachmentsInput.files).forEach((file) => {
            payload.append('attachments', file);
          });
        }

        fetch(endpoint, {
          method: 'POST',
          body: payload,
          credentials: 'same-origin',
        })
          .then((response) => parseResponse(response))
          .then((data) => {
            setSubmitting(false);
            lastSubmissionKey = submissionKey;
            lastSubmissionTime = Date.now();
            markComplete(data || {});
          })
          .catch((error) => {
            setSubmitting(false);
            if (error.status === 401 || error.status === 403) {
              isSignedIn = false;
              updateAuthState();
              appendMessage('Please sign in to continue.', 'error');
              return;
            }
            appendMessage(error.message || 'Something went wrong while submitting your report.', 'error');
          });
      });
    }

    primeConversation();
    updateAuthState();
  }
});
