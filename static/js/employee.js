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

function setupAoiArea(container) {
  const picker = container.querySelector('[data-aoi-picker]');
  const sheetPanel = container.querySelector('[data-sheet-panel]');
  const sheetTitle = container.querySelector('[data-sheet-title]');
  const sheetForm = container.querySelector('[data-sheet-form]');
  const feedback = container.querySelector('.employee-feedback');
  const backButton = container.querySelector('[data-action="back-to-picker"]');
  const sheetButtons = picker ? picker.querySelectorAll('[data-sheet]') : [];

  if (!picker || !sheetPanel || !sheetTitle || !sheetForm || !feedback || !backButton) {
    return;
  }

  let activeSheet = null;

  sheetButtons.forEach((button) => {
    button.addEventListener('click', () => {
      activeSheet = button.dataset.sheet || '';
      sheetTitle.textContent = button.textContent.trim();
      picker.hidden = true;
      sheetPanel.hidden = false;
      sheetPanel.dataset.sheet = activeSheet;
      sheetForm.reset();
      setFeedback(feedback, '');
    });
  });

  backButton.addEventListener('click', () => {
    sheetPanel.hidden = true;
    picker.hidden = false;
    sheetForm.reset();
    activeSheet = null;
    setFeedback(feedback, '');
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
      const dateField = sheetForm.querySelector('[name="date"]');
      if (dateField) {
        dateField.focus();
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
