const employeePortalPopup = (() => {
  let handler = null;

  function getHandler() {
    if (handler) return handler;
    if (typeof window !== 'undefined' && typeof window.alert === 'function') {
      return (message) => window.alert(message);
    }
    return null;
  }

  function normalizeMessage(message) {
    if (message == null) return '';
    return String(message).trim();
  }

  return {
    show(message, type) {
      const normalized = normalizeMessage(message);
      if (!normalized) return;
      const activeHandler = getHandler();
      if (typeof activeHandler === 'function') {
        activeHandler(normalized, type);
      }
    },
    setHandler(nextHandler) {
      handler = typeof nextHandler === 'function' ? nextHandler : null;
    },
    resetHandler() {
      handler = null;
    },
  };
})();

if (typeof window !== 'undefined') {
  window.employeePortalPopup = employeePortalPopup;
}

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

let defectCatalogData = null;
let defectCatalogError = null;
let defectCatalogRequest = null;

function normalizeDefectEntry(entry) {
  if (!entry || typeof entry !== 'object') return null;
  const rawId = entry.id;
  const rawName = entry.name;
  const id = rawId == null ? '' : String(rawId).trim();
  if (!id) return null;
  const name = rawName == null ? '' : String(rawName).trim();
  return { id, name };
}

function getDefectCatalog() {
  return Array.isArray(defectCatalogData) ? defectCatalogData : [];
}

function ensureDefectCatalogLoaded() {
  if (Array.isArray(defectCatalogData)) {
    return Promise.resolve(defectCatalogData);
  }
  if (defectCatalogRequest) {
    return defectCatalogRequest;
  }
  defectCatalogError = null;
  defectCatalogRequest = fetch('/employee/defects', {
    method: 'GET',
    headers: { Accept: 'application/json' },
  })
    .then((response) => {
      if (!response.ok) {
        throw new Error('Failed to load defect catalog');
      }
      return response.json();
    })
    .then((payload) => {
      const entries = Array.isArray(payload && payload.defects)
        ? payload.defects
        : [];
      const normalized = entries
        .map((item) => normalizeDefectEntry(item))
        .filter((item) => item);
      defectCatalogData = normalized;
      defectCatalogError = null;
      return normalized;
    })
    .catch((error) => {
      defectCatalogData = null;
      defectCatalogError = error || new Error('Failed to load defect catalog');
      throw defectCatalogError;
    })
    .finally(() => {
      defectCatalogRequest = null;
    });
  return defectCatalogRequest;
}

function formatDefectOptionLabel(defect) {
  if (!defect) return '';
  const { id, name } = defect;
  if (name) {
    return `${id} — ${name}`;
  }
  return id;
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
  const sheetPlaceholder = container.querySelector('[data-sheet-placeholder]');
  const feedback = container.querySelector('.employee-feedback');
  const backButton = container.querySelector('[data-action="back-to-picker"]');
  const sheetButtons = picker ? picker.querySelectorAll('[data-sheet]') : [];
  const wizard = setupInspectionWizard(sheetForm);
  const quantityRejectedInput = sheetForm ? sheetForm.querySelector('input[name="quantity_rejected"]') : null;
  const rejectionSection = sheetForm ? sheetForm.querySelector('[data-rejection-details]') : null;
  const rejectionRowsContainer = sheetForm ? sheetForm.querySelector('[data-rejection-rows]') : null;
  const rejectionEmptyRow = sheetForm ? sheetForm.querySelector('[data-rejection-empty]') : null;
  const rejectionRowTemplate = sheetForm ? sheetForm.querySelector('[data-rejection-row-template]') : null;
  const addRejectionRowButton = sheetForm ? sheetForm.querySelector('[data-action="add-rejection-row"]') : null;
  const rejectionHiddenInput = sheetForm ? sheetForm.querySelector('[data-rejection-json]') : null;
  const rejectionReasonSelects = new Set();
  const operatorSignature = sheetForm ? sheetForm.querySelector('[data-operator-signature]') : null;
  const signatureControl = operatorSignature ? operatorSignature.querySelector('[data-action="operator-signature"]') : null;
  const signatureDisplay = operatorSignature ? operatorSignature.querySelector('[data-signature-display]') : null;
  const signatureHiddenInput = operatorSignature ? operatorSignature.querySelector('[data-signature-field]') : null;
  const signatureDefaultText = signatureDisplay ? signatureDisplay.textContent.trim() : 'Sign on file';
  const operatorUsername = sheetForm ? (sheetForm.dataset.operatorUsername || '').trim() : '';
  const operatorInput = sheetForm ? sheetForm.querySelector('input[name="operator"]') : null;
  const programInput = sheetForm ? sheetForm.querySelector('input[name="program"]') : null;

  if (!picker || !sheetPanel || !sheetTitle || !sheetForm || !feedback || !backButton) {
    return;
  }

  picker.hidden = false;
  sheetPanel.hidden = true;
  if (sheetPlaceholder) {
    sheetPlaceholder.hidden = false;
  }
  delete sheetPanel.dataset.sheet;
  if (sheetForm) {
    sheetForm.reset();
    delete sheetForm.dataset.sheetVariant;
  }
  if (sheetSubtitle) {
    sheetSubtitle.textContent = '';
    sheetSubtitle.hidden = true;
  }
  setFeedback(feedback, '');
  resetRejectionDetails();
  resetSignatureState();
  if (wizard && typeof wizard.reset === 'function') {
    wizard.reset({ focus: false });
  }

  let activeSheet = null;
  const sheetSubtitleMap = {
    SMT: 'Surface Mount Technology',
    TH: 'Through-Hole Assembly',
  };

  const rejectionReasonSelects = new Set();

  function populateDefectSelect(select, selectedId = '') {
    if (!select) return;
    const doc = select.ownerDocument || document;
    const defects = getDefectCatalog();
    const hasDefects = defects.length > 0;
    const previous = selectedId || select.value || select.dataset.pendingSelection || '';
    const placeholder = doc.createElement('option');
    placeholder.value = '';
    placeholder.disabled = true;
    if (defectCatalogError) {
      placeholder.textContent = 'Unable to load defects';
      select.disabled = true;
    } else if (!hasDefects) {
      placeholder.textContent = 'Loading defects...';
      select.disabled = true;
    } else {
      placeholder.textContent = 'Select defect';
      select.disabled = false;
    }

    select.innerHTML = '';
    select.appendChild(placeholder);

    if (hasDefects) {
      defects.forEach((defect) => {
        const option = doc.createElement('option');
        option.value = defect.id;
        option.textContent = formatDefectOptionLabel(defect);
        if (defect.id === previous) {
          option.selected = true;
          placeholder.selected = false;
        }
        select.appendChild(option);
      });
    } else {
      placeholder.selected = true;
    }

    if (!select.value && previous && hasDefects) {
      const match = defects.find((item) => item.id === previous);
      if (match) {
        select.value = previous;
        placeholder.selected = false;
      }
    }

    if (!hasDefects && previous) {
      select.dataset.pendingSelection = previous;
    } else {
      delete select.dataset.pendingSelection;
    }
  }

  function refreshDefectSelects() {
    rejectionReasonSelects.forEach((select) => {
      const current = select.value || select.dataset.pendingSelection || '';
      populateDefectSelect(select, current);
    });
  }

  ensureDefectCatalogLoaded()
    .then(() => {
      refreshDefectSelects();
    })
    .catch(() => {
      refreshDefectSelects();
    });

  function updateRejectionEmptyState() {
    if (!rejectionRowsContainer) return;
    const hasRows = Boolean(rejectionRowsContainer.querySelector('[data-rejection-row]'));
    if (rejectionEmptyRow) {
      rejectionEmptyRow.hidden = hasRows;
    }
  }

  function markRowValidity(row, isValid) {
    if (!row) return;
    if (isValid) {
      row.classList.remove('is-invalid');
      row.removeAttribute('data-invalid');
    } else {
      row.classList.add('is-invalid');
      row.dataset.invalid = 'true';
    }
    const controls = row.querySelectorAll('[data-rejection-ref], [data-rejection-reason], [data-rejection-quantity]');
    controls.forEach((control) => {
      if (isValid) {
        control.removeAttribute('aria-invalid');
      } else {
        control.setAttribute('aria-invalid', 'true');
      }
    });
  }

  function collectRejectionRowData() {
    if (!rejectionRowsContainer) return [];
    return Array.from(rejectionRowsContainer.querySelectorAll('[data-rejection-row]')).map((row) => {
      const refInput = row.querySelector('[data-rejection-ref]');
      const reasonInput = row.querySelector('[data-rejection-reason]');
      const quantityInput = row.querySelector('[data-rejection-quantity]');
      const ref = refInput ? refInput.value.trim() : '';
      const reasonId = reasonInput ? reasonInput.value.trim() : '';
      let reasonLabel = '';
      if (reasonInput && reasonInput.selectedIndex >= 0) {
        const option = reasonInput.options[reasonInput.selectedIndex];
        reasonLabel = option && option.textContent ? option.textContent.trim() : '';
      }
      const reason = reasonLabel || reasonId;
      const quantityRaw = quantityInput ? quantityInput.value : '';
      const quantityNumber = quantityRaw === '' ? Number.NaN : Number(quantityRaw);
      const isQuantityValid = Number.isFinite(quantityNumber) && Number.isInteger(quantityNumber) && quantityNumber > 0;
      return {
        row,
        ref,
        reason,
        reasonId,
        quantity: quantityNumber,
        isQuantityValid,
      };
    });
  }

  function syncRejectionDetails() {
    if (!rejectionHiddenInput) return;
    const rows = collectRejectionRowData();
    const requireDetails = Boolean(rejectionSection && !rejectionSection.hidden);
    const validEntries = rows.filter((entry) => entry.ref && entry.reasonId && entry.isQuantityValid);
    if (requireDetails && validEntries.length === rows.length && validEntries.length > 0) {
      const serialized = validEntries.map(({ ref, reason, reasonId, quantity }) => ({
        ref,
        reason,
        reason_id: reasonId,
        quantity,
      }));
      rejectionHiddenInput.value = JSON.stringify(serialized);
    } else if (!requireDetails) {
      rejectionHiddenInput.value = '';
    } else {
      rejectionHiddenInput.value = '';
    }
    if (wizard) {
      wizard.evaluate();
    }
  }

  function clearRejectionRows() {
    if (!rejectionRowsContainer) return;
    const rows = Array.from(rejectionRowsContainer.querySelectorAll('[data-rejection-row]'));
    rows.forEach((row) => {
      const reasonSelect = row.querySelector('[data-rejection-reason]');
      if (reasonSelect) {
        rejectionReasonSelects.delete(reasonSelect);
      }
      row.remove();
    });
    rejectionReasonSelects.clear();
    updateRejectionEmptyState();
    syncRejectionDetails();
  }

  function isSignatureAcknowledged() {
    return Boolean(signatureHiddenInput && signatureHiddenInput.value === 'true');
  }

  function setSignatureAcknowledged(value) {
    const acknowledged = Boolean(value);
    if (signatureHiddenInput) {
      signatureHiddenInput.value = acknowledged ? 'true' : '';
    }
    if (signatureControl) {
      signatureControl.setAttribute('aria-pressed', acknowledged ? 'true' : 'false');
      if (acknowledged) {
        signatureControl.classList.add('is-signed');
      } else {
        signatureControl.classList.remove('is-signed');
      }
    }
    if (signatureDisplay) {
      if (acknowledged) {
        signatureDisplay.textContent = operatorUsername || 'Signature confirmed';
      } else {
        signatureDisplay.textContent = signatureDefaultText || 'Sign on file';
      }
    }
    if (
      acknowledged &&
      operatorInput &&
      !operatorInput.value.trim() &&
      operatorUsername
    ) {
      operatorInput.value = operatorUsername;
      operatorInput.dispatchEvent(new Event('input', { bubbles: true }));
      operatorInput.dispatchEvent(new Event('change', { bubbles: true }));
    }
    if (wizard) {
      wizard.evaluate();
    }
  }

  function resetSignatureState() {
    setSignatureAcknowledged(false);
  }

  function ensureRejectionRows() {
    if (!rejectionRowsContainer) return;
    if (!rejectionRowsContainer.querySelector('[data-rejection-row]')) {
      addRejectionRow();
    }
  }

  function addRejectionRow(defaults = {}) {
    if (!rejectionRowTemplate || !rejectionRowsContainer) return null;
    const fragment = rejectionRowTemplate.content.cloneNode(true);
    const row = fragment.querySelector('[data-rejection-row]');
    if (!row) return null;
    const refInput = row.querySelector('[data-rejection-ref]');
    const reasonInput = row.querySelector('[data-rejection-reason]');
    const quantityInput = row.querySelector('[data-rejection-quantity]');
    const removeButton = row.querySelector('[data-action="remove-rejection-row"]');

    if (refInput && defaults.ref) {
      refInput.value = defaults.ref;
    }
    if (reasonInput) {
      if (defaults.reason_id) {
        reasonInput.value = defaults.reason_id;
      } else if (defaults.reason) {
        reasonInput.value = defaults.reason;
      }
    }
    if (quantityInput && Number.isFinite(defaults.quantity)) {
      quantityInput.value = String(defaults.quantity);
    }

    const handleRowChange = (event) => {
      const targetRow = event.target.closest('[data-rejection-row]');
      if (targetRow) {
        markRowValidity(targetRow, true);
      }
      if (event.target && event.target.hasAttribute && event.target.hasAttribute('data-rejection-reason')) {
        delete event.target.dataset.pendingSelection;
      }
      syncRejectionDetails();
    };

    if (refInput) {
      refInput.addEventListener('input', handleRowChange);
      refInput.addEventListener('change', handleRowChange);
    }
    if (reasonInput) {
      const pendingSelection = defaults.reason_id || defaults.reason || '';
      if (pendingSelection) {
        reasonInput.dataset.pendingSelection = pendingSelection;
      }
      rejectionReasonSelects.add(reasonInput);
      populateDefectSelect(reasonInput, pendingSelection);
      reasonInput.addEventListener('input', handleRowChange);
      reasonInput.addEventListener('change', handleRowChange);
    }
    if (quantityInput) {
      quantityInput.addEventListener('input', handleRowChange);
      quantityInput.addEventListener('change', handleRowChange);
    }
    if (removeButton) {
      removeButton.addEventListener('click', () => {
        if (reasonInput) {
          rejectionReasonSelects.delete(reasonInput);
        }
        row.remove();
        updateRejectionEmptyState();
        syncRejectionDetails();
      });
    }

    rejectionRowsContainer.appendChild(row);
    updateRejectionEmptyState();
    syncRejectionDetails();
    if (refInput && typeof refInput.focus === 'function') {
      refInput.focus();
    }
    return row;
  }

  function validateRejectionRows() {
    if (!rejectionSection || rejectionSection.hidden) {
      return { valid: true, entries: [] };
    }
    const rows = collectRejectionRowData();
    if (!rows.length) {
      return { valid: false, entries: [] };
    }
    let valid = true;
    const entries = [];
    rows.forEach((entry) => {
      const rowValid = Boolean(entry.ref) && Boolean(entry.reasonId) && entry.isQuantityValid;
      markRowValidity(entry.row, rowValid);
      if (!rowValid) {
        valid = false;
        return;
      }
      entries.push({
        ref: entry.ref,
        reason: entry.reason,
        reason_id: entry.reasonId,
        quantity: entry.quantity,
      });
    });
    if (!valid || !entries.length) {
      return { valid: false, entries: [] };
    }
    return { valid: true, entries };
  }

  function handleQuantityRejectedChange() {
    if (!quantityRejectedInput) return;
    const rawValue = quantityRejectedInput.value;
    const parsed = rawValue === '' ? 0 : Number(rawValue);
    const shouldShow = Number.isFinite(parsed) && parsed > 0;
    if (rejectionSection) {
      rejectionSection.hidden = !shouldShow;
    }
    if (shouldShow) {
      ensureRejectionRows();
    } else {
      clearRejectionRows();
    }
    updateRejectionEmptyState();
    syncRejectionDetails();
  }

  function resetRejectionDetails() {
    clearRejectionRows();
    if (rejectionSection) {
      rejectionSection.hidden = true;
    }
    if (rejectionHiddenInput) {
      rejectionHiddenInput.value = '';
    }
    updateRejectionEmptyState();
    if (quantityRejectedInput) {
      quantityRejectedInput.value = '';
      handleQuantityRejectedChange();
    }
  }

  if (quantityRejectedInput) {
    quantityRejectedInput.addEventListener('input', handleQuantityRejectedChange);
    quantityRejectedInput.addEventListener('change', handleQuantityRejectedChange);
    handleQuantityRejectedChange();
  } else {
    updateRejectionEmptyState();
  }

  resetSignatureState();

  if (signatureControl) {
    signatureControl.addEventListener('click', () => {
      const nextState = !isSignatureAcknowledged();
      setSignatureAcknowledged(nextState);
    });
  }

  if (addRejectionRowButton) {
    addRejectionRowButton.addEventListener('click', () => {
      addRejectionRow();
    });
  }

  sheetButtons.forEach((button) => {
    button.addEventListener('click', () => {
      activeSheet = button.dataset.sheet || '';
      sheetTitle.textContent = button.textContent.trim();
      picker.hidden = true;
      if (sheetPlaceholder) {
        sheetPlaceholder.hidden = true;
      }
      sheetPanel.dataset.sheet = activeSheet;
      sheetPanel.hidden = false;
      if (sheetForm) {
        sheetForm.dataset.sheetVariant = activeSheet;
      }
      if (sheetSubtitle) {
        const subtitleText = sheetSubtitleMap[activeSheet] || '';
        sheetSubtitle.textContent = subtitleText;
        sheetSubtitle.hidden = !subtitleText;
      }
      sheetForm.reset();
      resetRejectionDetails();
      resetSignatureState();
      setFeedback(feedback, '');
      if (wizard) {
        wizard.reset({ focus: true });
      }
      if (programInput) {
        programInput.value = activeSheet || '';
        programInput.readOnly = Boolean(activeSheet);
        const eventOptions = { bubbles: true };
        programInput.dispatchEvent(new Event('input', eventOptions));
        programInput.dispatchEvent(new Event('change', eventOptions));
      }
      refreshDefectSelects();
      ensureDefectCatalogLoaded().then(() => {
        refreshDefectSelects();
      }).catch(() => {
        refreshDefectSelects();
      });
    });
  });

  backButton.addEventListener('click', () => {
    sheetPanel.hidden = true;
    picker.hidden = false;
    if (sheetPlaceholder) {
      sheetPlaceholder.hidden = false;
    }
    delete sheetPanel.dataset.sheet;
    sheetForm.reset();
    resetRejectionDetails();
    resetSignatureState();
    activeSheet = null;
    setFeedback(feedback, '');
    if (sheetForm) {
      delete sheetForm.dataset.sheetVariant;
    }
    if (sheetSubtitle) {
      sheetSubtitle.textContent = '';
      sheetSubtitle.hidden = true;
    }
    if (programInput) {
      programInput.readOnly = false;
    }
    if (wizard) {
      wizard.reset();
    }
  });

  sheetForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!activeSheet) {
      const message = 'Select a data sheet before submitting.';
      employeePortalPopup.show(message, 'error');
      setFeedback(feedback, message, 'error');
      return;
    }

    const submitButton = sheetForm.querySelector('[type="submit"]');
    if (submitButton) {
      submitButton.disabled = true;
    }

    if (signatureHiddenInput && signatureControl && !isSignatureAcknowledged()) {
      if (submitButton) {
        submitButton.disabled = false;
      }
      const message = 'Confirm your operator signature before submitting.';
      employeePortalPopup.show(message, 'error');
      setFeedback(feedback, message, 'error');
      if (typeof signatureControl.focus === 'function') {
        signatureControl.focus();
      }
      return;
    }

    const requiresRejectionDetails = Boolean(rejectionSection && !rejectionSection.hidden);
    let rejectionEntries = [];
    if (requiresRejectionDetails) {
      const validation = validateRejectionRows();
      if (!validation.valid) {
        if (submitButton) {
          submitButton.disabled = false;
        }
        const message = 'Complete all rejection detail rows before submitting.';
        employeePortalPopup.show(message, 'error');
        setFeedback(feedback, message, 'error');
        return;
      }
      rejectionEntries = validation.entries;
      if (rejectionHiddenInput) {
        rejectionHiddenInput.value = JSON.stringify(rejectionEntries);
      }
    } else if (rejectionHiddenInput) {
      rejectionHiddenInput.value = '';
    }

    setFeedback(feedback, 'Submitting...');

    const formData = new FormData(sheetForm);
    const payload = Object.fromEntries(formData.entries());
    payload.inspection_type = activeSheet;
    payload.rejection_details = rejectionEntries;

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
        employeePortalPopup.show(errorMessage, 'error');
        setFeedback(feedback, errorMessage, 'error');
        return;
      }

      const successMessage = (responseData && responseData.message) ||
        'AOI report submitted successfully.';
      employeePortalPopup.show(successMessage, 'success');
      setFeedback(feedback, successMessage, 'success');
      sheetForm.reset();
      resetRejectionDetails();
      resetSignatureState();
      if (wizard) {
        wizard.reset({ focus: true });
      }
    } catch (error) {
      const message = 'Unable to submit inspection at this time.';
      employeePortalPopup.show(message, 'error');
      setFeedback(feedback, message, 'error');
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
  const areaOptionsContainer = portal.querySelector('[data-area-options]');
  const areaPanel = portal.querySelector('[data-area-content]');
  const areaTitle = portal.querySelector('[data-area-title]');
  const areaSlot = portal.querySelector('[data-area-slot]');
  const changeAreaButton = portal.querySelector('[data-action="change-area"]');
  const messageTemplate = portal.querySelector('#employee-area-message-template');
  const aoiTemplate = portal.querySelector('#employee-aoi-template');

  if (!areaSelection || !areaOptionsContainer || !areaPanel || !areaTitle || !areaSlot || !changeAreaButton) {
    return;
  }

  function getAreaOptions() {
    return Array.from(areaOptionsContainer.querySelectorAll('[data-area-option]'));
  }

  function clearAreaSlot() {
    areaSlot.innerHTML = '';
  }

  function resetArea({ focus = false } = {}) {
    clearAreaSlot();
    areaPanel.hidden = true;
    areaTitle.textContent = '';
    areaSelection.hidden = false;
    getAreaOptions().forEach((option) => {
      option.classList.remove('is-selected');
      option.setAttribute('aria-pressed', 'false');
    });

    if (focus) {
      const [firstOption] = getAreaOptions();
      if (firstOption) {
        firstOption.focus();
      }
    }
  }

  changeAreaButton.addEventListener('click', () => {
    resetArea({ focus: true });
  });

  function selectArea(option) {
    if (!option) return;
    const areaName = option.dataset.areaValue;
    if (!areaName) return;

    getAreaOptions().forEach((candidate) => {
      const isActive = candidate === option;
      candidate.classList.toggle('is-selected', isActive);
      candidate.setAttribute('aria-pressed', String(isActive));
    });

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

    changeAreaButton.focus();
  }

  areaOptionsContainer.addEventListener('click', (event) => {
    const option = event.target.closest('[data-area-option]');
    if (!option || !areaOptionsContainer.contains(option)) {
      return;
    }
    event.preventDefault();
    selectArea(option);
  });

  areaOptionsContainer.addEventListener('keydown', (event) => {
    const option = event.target.closest('[data-area-option]');
    if (!option || !areaOptionsContainer.contains(option)) {
      return;
    }

    const options = getAreaOptions();
    if (!options.length) {
      return;
    }

    const currentIndex = options.indexOf(option);
    if (currentIndex === -1) {
      return;
    }

    const lastIndex = options.length - 1;

    switch (event.key) {
      case 'ArrowRight':
      case 'ArrowDown': {
        event.preventDefault();
        const nextIndex = currentIndex === lastIndex ? 0 : currentIndex + 1;
        options[nextIndex].focus();
        break;
      }
      case 'ArrowLeft':
      case 'ArrowUp': {
        event.preventDefault();
        const previousIndex = currentIndex === 0 ? lastIndex : currentIndex - 1;
        options[previousIndex].focus();
        break;
      }
      case 'Home': {
        event.preventDefault();
        options[0].focus();
        break;
      }
      case 'End': {
        event.preventDefault();
        options[lastIndex].focus();
        break;
      }
      case 'Enter':
      case ' ': {
        event.preventDefault();
        selectArea(option);
        break;
      }
      default:
        break;
    }
  });
}

document.addEventListener('DOMContentLoaded', setupEmployeePortal);
