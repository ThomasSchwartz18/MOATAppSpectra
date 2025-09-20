function setFeedback(element, message, type) {
  if (!element) return;
  element.textContent = message || '';
  element.classList.remove('is-error', 'is-success');
  if (type === 'error') {
    element.classList.add('is-error');
  } else if (type === 'success') {
    element.classList.add('is-success');
  }
}

function formatErrors(errors) {
  if (!errors) return '';
  if (typeof errors === 'string') return errors;
  if (Array.isArray(errors)) return errors.join(' ');
  if (typeof errors === 'object') {
    return Object.values(errors)
      .map((value) => {
        if (!value) return '';
        if (Array.isArray(value)) return value.join(' ');
        return String(value);
      })
      .filter(Boolean)
      .join(' ');
  }
  return '';
}

function setupInspectionWizard(form) {
  if (!form) return null;

  const steps = Array.from(form.querySelectorAll('[data-step]'));
  if (!steps.length) return null;

  const progress = form.querySelector('[data-progress]');
  const progressBar = progress ? progress.querySelector('[data-progress-bar]') : null;
  const progressCurrent = progress ? progress.querySelector('[data-progress-current]') : null;
  const progressTotal = progress ? progress.querySelector('[data-progress-total]') : null;
  const stepGroups = Array.from(form.querySelectorAll('[data-step-group]'));
  const finishElements = Array.from(form.querySelectorAll('[data-step-finish]'));

  const totalSteps = steps.length;
  let visibleIndex = 0;

  if (progressTotal) {
    progressTotal.textContent = String(totalSteps);
  }

  function clampVisibleIndex() {
    if (!steps.length) {
      visibleIndex = 0;
      return;
    }
    if (visibleIndex < 0) {
      visibleIndex = 0;
    } else if (visibleIndex > steps.length - 1) {
      visibleIndex = steps.length - 1;
    }
  }

  function applyVisibility() {
    clampVisibleIndex();
    steps.forEach((step, index) => {
      const isVisible = index <= visibleIndex;
      if (isVisible) {
        step.hidden = false;
        step.classList.add('is-visible');
      } else {
        step.hidden = true;
        step.classList.remove('is-visible');
        delete step.dataset.completed;
      }
    });

    stepGroups.forEach((group) => {
      const hasVisibleStep = Array.from(group.querySelectorAll('[data-step]')).some((step) => !step.hidden);
      group.hidden = !hasVisibleStep;
    });

    finishElements.forEach((element) => {
      element.hidden = visibleIndex < steps.length - 1;
    });
  }

  function getActiveIndex() {
    const firstIncomplete = steps.findIndex((step) => step.dataset.completed === 'true' ? false : true);
    let index = firstIncomplete === -1 ? steps.length - 1 : firstIncomplete;
    if (index > visibleIndex) {
      index = visibleIndex;
    }
    if (index < 0) {
      index = 0;
    }
    return index;
  }

  function updateProgress() {
    const completedCount = steps.reduce((total, step) => (
      total + (step.dataset.completed === 'true' ? 1 : 0)
    ), 0);

    const activeIndex = getActiveIndex();

    if (progressCurrent) {
      progressCurrent.textContent = String(activeIndex + 1);
    }

    if (progressTotal) {
      progressTotal.textContent = String(totalSteps);
    }

    if (progressBar) {
      const percent = totalSteps === 0 ? 0 : Math.min(100, Math.max(0, (completedCount / totalSteps) * 100));
      progressBar.style.width = `${percent}%`;
      progressBar.dataset.progressPercent = String(percent);
    }

    if (completedCount >= steps.length) {
      steps.forEach((step) => {
        step.dataset.state = 'complete';
      });
      return;
    }

    steps.forEach((step, index) => {
      let state = 'upcoming';
      if (index < activeIndex) {
        state = 'complete';
      } else if (index === activeIndex) {
        state = 'active';
      }
      step.dataset.state = state;
    });
  }

  function isStepComplete(step) {
    const input = step.querySelector('input, select, textarea');
    if (!input) return true;
    if (input.disabled) return false;

    const isOptional = step.hasAttribute('data-step-optional');

    if (input.tagName === 'SELECT') {
      return Boolean(input.value);
    }

    const type = input.type;

    if (type === 'number') {
      const rawValue = input.value;
      if (!rawValue) {
        return !input.required && (isOptional ? input.dataset.stepTouched === 'true' : true);
      }
      const parsed = Number(rawValue);
      if (Number.isNaN(parsed)) return false;
      if (input.min !== '' && !Number.isNaN(Number(input.min)) && parsed < Number(input.min)) {
        return false;
      }
      if (input.max !== '' && !Number.isNaN(Number(input.max)) && parsed > Number(input.max)) {
        return false;
      }
      return true;
    }

    if (type === 'date' || type === 'time') {
      if (!input.value) {
        return !input.required && (isOptional ? input.dataset.stepTouched === 'true' : true);
      }
      return true;
    }

    if (type === 'checkbox' || type === 'radio') {
      if (input.required) {
        return input.checked;
      }
      if (isOptional) {
        return input.checked || input.dataset.stepTouched === 'true';
      }
      return true;
    }

    const value = input.value ? input.value.trim() : '';

    if (input.required) {
      return value.length > 0;
    }

    if (isOptional) {
      return value.length > 0 || input.dataset.stepTouched === 'true';
    }

    return true;
  }

  function evaluateStep(stepIndex) {
    const step = steps[stepIndex];
    if (!step) return;

    const completed = isStepComplete(step);

    if (completed) {
      step.dataset.completed = 'true';
      if (stepIndex < steps.length - 1) {
        visibleIndex = Math.max(visibleIndex, stepIndex + 1);
        const nextIndex = stepIndex + 1;
        const nextStep = steps[nextIndex];
        if (nextStep && isStepComplete(nextStep)) {
          evaluateStep(nextIndex);
          return;
        }
      }
    } else {
      delete step.dataset.completed;
      visibleIndex = Math.min(visibleIndex, stepIndex);
      for (let index = stepIndex + 1; index < steps.length; index += 1) {
        delete steps[index].dataset.completed;
      }
    }

    applyVisibility();
    updateProgress();
  }

  function resetWizard({ focus = false } = {}) {
    visibleIndex = 0;
    steps.forEach((step, index) => {
      delete step.dataset.completed;
      step.dataset.state = index === 0 ? 'active' : 'upcoming';
      const input = step.querySelector('input, select, textarea');
      if (input && input.dataset) {
        delete input.dataset.stepTouched;
      }
    });
    applyVisibility();
    updateProgress();
    if (focus) {
      focusActiveStep();
    }
  }

  function focusActiveStep() {
    const activeIndex = getActiveIndex();
    const targetStep = steps[activeIndex];
    if (!targetStep) return;
    const input = targetStep.querySelector('input, select, textarea');
    if (input && typeof input.focus === 'function') {
      const raf = typeof window !== 'undefined' && typeof window.requestAnimationFrame === 'function'
        ? window.requestAnimationFrame.bind(window)
        : (fn) => setTimeout(fn, 0);
      raf(() => {
        input.focus();
      });
    }
  }

  steps.forEach((step, index) => {
    const input = step.querySelector('input, select, textarea');
    if (!input) return;

    const handleInteraction = () => {
      if (step.hasAttribute('data-step-optional')) {
        input.dataset.stepTouched = 'true';
      }
      evaluateStep(index);
    };

    input.addEventListener('input', handleInteraction);
    input.addEventListener('change', handleInteraction);
    input.addEventListener('blur', handleInteraction);
  });

  applyVisibility();
  updateProgress();

  return {
    reset: resetWizard,
    focus: focusActiveStep,
    evaluate: () => {
      steps.forEach((_, index) => {
        evaluateStep(index);
      });
    },
  };
}

function setupAoiArea(container) {
  const picker = container.querySelector('[data-aoi-picker]');
  const sheetPanel = container.querySelector('[data-sheet-panel]');
  const sheetTitle = container.querySelector('[data-sheet-title]');
  const sheetSubtitle = container.querySelector('[data-sheet-subtitle]');
  const sheetForm = container.querySelector('[data-sheet-form]');
  const feedback = container.querySelector('.employee-feedback');
  const backButton = container.querySelector('[data-action="back-to-picker"]');
  const sheetButtons = picker ? picker.querySelectorAll('[data-sheet]') : [];
  const defectSelect = container.querySelector('[data-defect-select]');
  const wizard = setupInspectionWizard(sheetForm);

  if (!picker || !sheetPanel || !sheetTitle || !sheetForm || !feedback || !backButton) {
    return;
  }

  let activeSheet = null;
  let defectOptionsLoaded = false;
  const sheetSubtitleMap = {
    SMT: 'Surface Mount Technology',
    TH: 'Through-Hole Assembly',
  };

  function setDefectPlaceholder(message, disable) {
    if (!defectSelect) return;
    defectSelect.innerHTML = '';
    const option = document.createElement('option');
    option.value = '';
    option.textContent = message;
    option.disabled = true;
    option.selected = true;
    option.defaultSelected = true;
    defectSelect.appendChild(option);
    defectSelect.disabled = Boolean(disable);
  }

  async function loadDefectOptions({ forceRefresh = false } = {}) {
    if (!defectSelect || defectSelect.dataset.loading === 'true') {
      return;
    }
    if (defectOptionsLoaded && !forceRefresh) {
      return;
    }
    defectSelect.dataset.loading = 'true';
    defectOptionsLoaded = false;
    const previousValue = forceRefresh ? defectSelect.value : '';
    setDefectPlaceholder('Loading defects...', true);
    try {
      const response = await fetch('/employee/defects');
      if (!response.ok) {
        throw new Error('Failed to load defects');
      }
      const payload = await response.json();
      const rawDefects = Array.isArray(payload && payload.defects) ? payload.defects : [];
      const unique = [];
      const seen = new Set();
      rawDefects.forEach((item) => {
        if (!item || typeof item !== 'object') return;
        const rawId = item.id;
        const rawName = item.name;
        const id = rawId === undefined || rawId === null ? '' : String(rawId).trim();
        const name = rawName === undefined || rawName === null ? '' : String(rawName).trim();
        if (!id) return;
        const key = id.toLowerCase();
        if (seen.has(key)) return;
        seen.add(key);
        unique.push({ id, name });
      });
      unique.sort((a, b) => a.id.localeCompare(b.id, undefined, { numeric: true, sensitivity: 'base' }));
      if (!unique.length) {
        setDefectPlaceholder('No defects available', true);
        return;
      }
      setDefectPlaceholder('Select defect', false);
      const fragment = document.createDocumentFragment();
      unique.forEach(({ id, name }) => {
        const option = document.createElement('option');
        option.value = id;
        option.textContent = name ? `${id} — ${name}` : id;
        if (name) {
          option.dataset.defectName = name;
        }
        fragment.appendChild(option);
      });
      defectSelect.appendChild(fragment);
      defectSelect.disabled = false;
      if (previousValue && unique.some((item) => item.id === previousValue)) {
        defectSelect.value = previousValue;
      } else {
        defectSelect.value = '';
      }
      defectOptionsLoaded = true;
    } catch (error) {
      setDefectPlaceholder('Unable to load defects', true);
      setFeedback(feedback, 'Unable to load defect list. Please try again later.', 'error');
    } finally {
      delete defectSelect.dataset.loading;
    }
  }

  function resetDefectSelection() {
    if (!defectSelect) return;
    if (defectOptionsLoaded) {
      defectSelect.disabled = false;
      defectSelect.selectedIndex = 0;
      defectSelect.value = '';
    } else if (defectSelect.dataset.loading !== 'true') {
      loadDefectOptions();
    }
  }

  if (defectSelect) {
    loadDefectOptions();
    if (!defectSelect.dataset.refreshBound) {
      const refreshDefectOptions = () => loadDefectOptions({ forceRefresh: true });
      const handleVisibilityChange = () => {
        if (!document.hidden) {
          refreshDefectOptions();
        }
      };
      defectSelect.dataset.refreshBound = 'true';
      window.setInterval(refreshDefectOptions, 900000);
      document.addEventListener('visibilitychange', handleVisibilityChange);
      window.addEventListener('focus', refreshDefectOptions);
    }
  }

  sheetButtons.forEach((button) => {
    button.addEventListener('click', () => {
      activeSheet = button.dataset.sheet || '';
      sheetTitle.textContent = button.textContent.trim();
      picker.hidden = true;
      sheetPanel.hidden = false;
      sheetPanel.dataset.sheet = activeSheet;
      if (sheetForm) {
        sheetForm.dataset.sheetVariant = activeSheet;
      }
      if (sheetSubtitle) {
        const subtitleText = sheetSubtitleMap[activeSheet] || '';
        sheetSubtitle.textContent = subtitleText;
        sheetSubtitle.hidden = !subtitleText;
      }
      sheetForm.reset();
      resetDefectSelection();
      setFeedback(feedback, '');
      if (wizard) {
        wizard.reset({ focus: true });
      }
    });
  });

  backButton.addEventListener('click', () => {
    sheetPanel.hidden = true;
    picker.hidden = false;
    delete sheetPanel.dataset.sheet;
    sheetForm.reset();
    resetDefectSelection();
    activeSheet = null;
    setFeedback(feedback, '');
    if (sheetForm) {
      delete sheetForm.dataset.sheetVariant;
    }
    if (sheetSubtitle) {
      sheetSubtitle.textContent = '';
      sheetSubtitle.hidden = true;
    }
    if (wizard) {
      wizard.reset();
    }
  });

  sheetForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!activeSheet) {
      setFeedback(feedback, 'Select a data sheet before submitting.', 'error');
      return;
    }

    const submitButton = sheetForm.querySelector('[type="submit"]');
    if (submitButton) {
      submitButton.disabled = true;
    }

    setFeedback(feedback, 'Submitting...');

    const formData = new FormData(sheetForm);
    const payload = Object.fromEntries(formData.entries());
    payload.inspection_type = activeSheet;

    try {
      const response = await fetch('/employee/aoi_reports', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      let responseData = null;
      try {
        responseData = await response.json();
      } catch (parseError) {
        responseData = null;
      }

      if (!response.ok) {
        const errorMessage = formatErrors(responseData && responseData.errors) ||
          'Unable to submit inspection at this time.';
        setFeedback(feedback, errorMessage, 'error');
        return;
      }

      const successMessage = (responseData && responseData.message) ||
        'AOI report submitted successfully.';
      setFeedback(feedback, successMessage, 'success');
      sheetForm.reset();
      resetDefectSelection();
      if (wizard) {
        wizard.reset({ focus: true });
      }
    } catch (error) {
      setFeedback(feedback, 'Unable to submit inspection at this time.', 'error');
    } finally {
      if (submitButton) {
        submitButton.disabled = false;
      }
    }
  });
}

function setupEmployeePortal() {
  const portal = document.querySelector('[data-employee-portal]');
  if (!portal) return;

  const areaSelection = portal.querySelector('[data-area-selection]');
  const areaSelect = portal.querySelector('[data-area-select]');
  const areaPanel = portal.querySelector('[data-area-content]');
  const areaTitle = portal.querySelector('[data-area-title]');
  const areaSlot = portal.querySelector('[data-area-slot]');
  const changeAreaButton = portal.querySelector('[data-action="change-area"]');
  const messageTemplate = portal.querySelector('#employee-area-message-template');
  const aoiTemplate = portal.querySelector('#employee-aoi-template');

  if (!areaSelection || !areaSelect || !areaPanel || !areaTitle || !areaSlot || !changeAreaButton) {
    return;
  }

  function clearAreaSlot() {
    areaSlot.innerHTML = '';
  }

  function resetArea() {
    clearAreaSlot();
    areaPanel.hidden = true;
    areaTitle.textContent = '';
    areaSelection.hidden = false;
    areaSelect.value = '';
  }

  changeAreaButton.addEventListener('click', () => {
    resetArea();
    areaSelect.focus();
  });

  areaSelect.addEventListener('change', (event) => {
    const areaName = event.target.value;
    if (!areaName) return;
    areaSelection.hidden = true;
    areaPanel.hidden = false;
    areaTitle.textContent = areaName;
    clearAreaSlot();

    if (areaName === 'AOI' && aoiTemplate) {
      const areaContent = aoiTemplate.content.firstElementChild.cloneNode(true);
      areaSlot.appendChild(areaContent);
      setupAoiArea(areaContent);
      return;
    }

    if (messageTemplate) {
      const areaContent = messageTemplate.content.firstElementChild.cloneNode(true);
      const paragraph = areaContent.querySelector('p');
      if (paragraph) {
        paragraph.textContent = `The ${areaName} workflow is part of the prototype build and is not functional yet.`;
      }
      areaSlot.appendChild(areaContent);
    }
  });
}

document.addEventListener('DOMContentLoaded', setupEmployeePortal);
