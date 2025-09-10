let operatorOptions = [];
let assemblyOptions = [];

function uniqueSorted(arr) {
  const map = new Map();
  arr.forEach((v) => {
    if (v != null && v !== '') {
      const key = String(v).toLowerCase();
      if (!map.has(key)) map.set(key, v);
    }
  });
  return Array.from(map.values()).sort((a, b) => a.localeCompare(b));
}

function populateDynamicSelect(wrapperId, className, options, values = []) {
  const wrapper = document.getElementById(wrapperId);
  if (!wrapper) return;
  wrapper.innerHTML = '';
  function addSelect(value = '') {
    const sel = document.createElement('select');
    sel.className = className;
    const blank = document.createElement('option');
    blank.value = '';
    blank.textContent = '';
    sel.appendChild(blank);
    options.forEach((v) => {
      const opt = document.createElement('option');
      opt.value = v;
      opt.textContent = v;
      sel.appendChild(opt);
    });
    sel.value = value;
    sel.addEventListener('change', () => {
      const sels = wrapper.querySelectorAll('select.' + className);
      const last = sels[sels.length - 1];
      if (sel === last && sel.value !== '') addSelect('');
    });
    wrapper.appendChild(sel);
  }
  values.forEach((v) => addSelect(v));
  addSelect('');
}

function getDropdownValues(className) {
  return Array.from(document.querySelectorAll('select.' + className))
    .map((sel) => sel.value)
    .filter((v) => v);
}

document.addEventListener('DOMContentLoaded', () => {
  const runBtn = document.getElementById('run-report');
  const downloadBtn = document.getElementById('download-report');
  const downloadControls = document.getElementById('download-controls');
  const previewBox = document.getElementById('preview-data');

  if (downloadControls) downloadControls.style.display = 'none';

  fetch('/aoi_reports')
    .then((r) => r.json())
    .then((rows) => {
      operatorOptions = uniqueSorted(rows.map((r) => r['Operator']));
      populateDynamicSelect('operator-wrapper', 'filter-operator', operatorOptions);
      assemblyOptions = uniqueSorted(rows.map((r) => r['Assembly']));
      populateDynamicSelect('assembly-wrapper', 'filter-assembly', assemblyOptions);
    });

  runBtn?.addEventListener('click', () => {
    const date = document.getElementById('report-date').value;
    const operator = getDropdownValues('filter-operator').join(',');
    const assembly = getDropdownValues('filter-assembly').join(',');
    if (!date) {
      alert('Please select a date.');
      return;
    }
    const params = new URLSearchParams({ date });
    if (operator) params.append('operator', operator);
    if (assembly) params.append('assembly', assembly);
    fetch(`/api/reports/aoi_daily?${params.toString()}`)
      .then((res) => res.json())
      .then((data) => {
        if (previewBox) previewBox.textContent = JSON.stringify(data, null, 2);
        if (downloadControls) downloadControls.style.display = 'flex';
      })
      .catch(() => alert('Failed to run report.'));
  });

  downloadBtn?.addEventListener('click', () => {
    const fmt = document.getElementById('file-format').value;
    const date = document.getElementById('report-date').value;
    const operator = getDropdownValues('filter-operator').join(',');
    const assembly = getDropdownValues('filter-assembly').join(',');
    const includeCover = document.getElementById('include-cover')?.checked;
    if (!date) {
      alert('Please select a date.');
      return;
    }
    const params = new URLSearchParams({ format: fmt, date });
    params.append('show_cover', includeCover ? 'true' : 'false');
    if (operator) params.append('operator', operator);
    if (assembly) params.append('assembly', assembly);
    window.location = `/reports/aoi_daily/export?${params.toString()}`;
  });
});
