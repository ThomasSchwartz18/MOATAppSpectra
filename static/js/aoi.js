let aoiChartInstance = null;
let aoiChartExpandedInstance = null;
let currentData = { labels: [], accepted: [], rejected: [] };
let savedQueriesCache = [];

function uniqueSorted(arr) {
  return Array.from(new Set(arr.filter((x) => x != null && x !== ''))).sort();
}

function populateSelect(id, values) {
  const sel = document.getElementById(id);
  sel.innerHTML = '';
  values.forEach((v) => {
    const opt = document.createElement('option');
    opt.value = v;
    opt.textContent = v;
    sel.appendChild(opt);
  });
}

function initFiltersUI() {
  fetch('/aoi_reports')
    .then((r) => r.json())
    .then((rows) => {
      if (!Array.isArray(rows)) return;
      populateSelect('filter-job', uniqueSorted(rows.map((r) => r['Job Number'])));
      populateSelect('filter-rev', uniqueSorted(rows.map((r) => r['Rev'])));
      populateSelect('filter-assembly', uniqueSorted(rows.map((r) => r['Assembly'])));
      populateSelect('filter-customer', uniqueSorted(rows.map((r) => r['Customer'])));
      populateSelect('filter-operator', uniqueSorted(rows.map((r) => r['Operator'])));
    });
}

function getSelectedValues(id) {
  const sel = document.getElementById(id);
  return Array.from(sel.selectedOptions).map((o) => o.value);
}

function renderChart(targetId, labels, accepted, rejected) {
  const ctx = document.getElementById(targetId).getContext('2d');
  const data = {
    labels,
    datasets: [
      { label: 'Accepted', data: accepted, backgroundColor: 'rgba(54,162,235,0.6)', stack: 'stack' },
      { label: 'Rejected', data: rejected, backgroundColor: 'rgba(255,99,132,0.6)', stack: 'stack' },
    ],
  };
  const options = {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      x: { stacked: true },
      y: { stacked: true, beginAtZero: true },
    },
  };
  if (targetId === 'aoiChart' && aoiChartInstance) aoiChartInstance.destroy();
  if (targetId === 'aoiChartExpanded' && aoiChartExpandedInstance) aoiChartExpandedInstance.destroy();
  // eslint-disable-next-line no-undef
  const inst = new Chart(ctx, { type: 'bar', data, options });
  if (targetId === 'aoiChart') aoiChartInstance = inst; else aoiChartExpandedInstance = inst;
}

function fillTable(labels, accepted, rejected) {
  const tbody = document.getElementById('data-tbody');
  tbody.innerHTML = '';
  labels.forEach((lab, i) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${lab}</td><td>${accepted[i]}</td><td>${rejected[i]}</td>`;
    tbody.appendChild(tr);
  });
}

function expandModal(show) {
  const overlay = document.getElementById('chart-modal');
  overlay.style.display = show ? 'flex' : 'none';
  if (show) {
    renderChart('aoiChartExpanded', currentData.labels, currentData.accepted, currentData.rejected);
    fillTable(currentData.labels, currentData.accepted, currentData.rejected);
  }
}

document.getElementById('expand-chart').addEventListener('click', () => expandModal(true));
document.getElementById('modal-close').addEventListener('click', () => expandModal(false));

document.getElementById('modal-download-chart').addEventListener('click', () => {
  const canvas = document.getElementById('aoiChartExpanded');
  const link = document.createElement('a');
  link.href = canvas.toDataURL('image/png');
  link.download = 'chart.png';
  link.click();
});

document.getElementById('modal-download-csv').addEventListener('click', () => {
  const { labels, accepted, rejected } = currentData;
  let csv = 'Operator,Accepted,Rejected\n';
  labels.forEach((lab, i) => { csv += `${lab},${accepted[i]},${rejected[i]}\n`; });
  const blob = new Blob([csv], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'data.csv';
  link.click();
  URL.revokeObjectURL(url);
});

function runChart() {
  const params = {
    start_date: document.getElementById('start-date').value,
    end_date: document.getElementById('end-date').value,
    job_numbers: getSelectedValues('filter-job').join(','),
    rev_numbers: getSelectedValues('filter-rev').join(','),
    assemblies: getSelectedValues('filter-assembly').join(','),
    customers: getSelectedValues('filter-customer').join(','),
    operators: getSelectedValues('filter-operator').join(','),
  };
  const qs = new URLSearchParams(params).toString();
  fetch(`/analysis/aoi/data?${qs}`)
    .then((r) => r.json())
    .then((res) => {
      currentData = { labels: res.labels || [], accepted: res.accepted || [], rejected: res.rejected || [] };
      renderChart('aoiChart', currentData.labels, currentData.accepted, currentData.rejected);
      document.getElementById('result-chart-name').textContent = document.getElementById('chart-title').value || '';
      document.getElementById('chart-description-result').textContent = document.getElementById('chart-description').value || '';
    });
}

document.getElementById('run-chart').addEventListener('click', runChart);

async function copyChartImage() {
  const canvas = document.getElementById('aoiChart');
  if (!navigator.clipboard || !navigator.clipboard.write) { alert('Clipboard API not supported.'); return; }
  try {
    const blob = await new Promise((resolve) => canvas.toBlob(resolve));
    await navigator.clipboard.write([new ClipboardItem({ [blob.type]: blob })]);
    alert('Chart image copied to clipboard.');
  } catch (e) {
    alert('Failed to copy image.');
  }
}

document.getElementById('copy-image').addEventListener('click', copyChartImage);

document.getElementById('download-pdf').addEventListener('click', () => {
  const { jsPDF } = window.jspdf;
  const canvas = document.getElementById('aoiChart');
  const dataURL = canvas.toDataURL('image/png', 1.0);
  const pdf = new jsPDF();
  const imgProps = pdf.getImageProperties(dataURL);
  const pdfWidth = pdf.internal.pageSize.getWidth();
  const pdfHeight = (imgProps.height * pdfWidth) / imgProps.width;
  pdf.addImage(dataURL, 'PNG', 0, 0, pdfWidth, pdfHeight);
  const title = document.getElementById('chart-title').value || 'chart';
  pdf.save(`${title}.pdf`);
});

function defaultPresets() {
  return [
    {
      name: 'Operator Reject Rate',
      description: 'Boards accepted vs rejected per operator',
      params: { start_date: '', end_date: '', job_numbers: [], rev_numbers: [], assemblies: [], customers: [], operators: [] },
    },
  ];
}

function renderSavedList() {
  const q = (document.getElementById('saved-search').value || '').toLowerCase();
  const list = document.getElementById('saved-list');
  list.innerHTML = '';
  savedQueriesCache.filter((r) => (r.name || '').toLowerCase().includes(q)).forEach((row) => {
    const li = document.createElement('li');
    li.textContent = row.name;
    li.addEventListener('click', () => loadParams(row));
    list.appendChild(li);
  });
}

document.getElementById('saved-search').addEventListener('input', renderSavedList);

function setSelectValues(id, values) {
  const sel = document.getElementById(id);
  Array.from(sel.options).forEach((opt) => { opt.selected = values.includes(opt.value); });
}

function loadParams(row) {
  const p = row.params || {};
  document.getElementById('chart-title').value = row.name || '';
  document.getElementById('chart-description').value = row.description || '';
  document.getElementById('start-date').value = p.start_date || '';
  document.getElementById('end-date').value = p.end_date || '';
  setSelectValues('filter-job', p.job_numbers || []);
  setSelectValues('filter-rev', p.rev_numbers || []);
  setSelectValues('filter-assembly', p.assemblies || []);
  setSelectValues('filter-customer', p.customers || []);
  setSelectValues('filter-operator', p.operators || []);
  document.getElementById('result-chart-name').textContent = row.name || '';
  document.getElementById('chart-description-result').textContent = row.description || '';
  runChart();
}

function loadSavedQueries() {
  fetch('/analysis/aoi/saved')
    .then((r) => r.json())
    .then((rows) => {
      savedQueriesCache = defaultPresets().concat(Array.isArray(rows) ? rows : []);
      renderSavedList();
      if (savedQueriesCache[0]) loadParams(savedQueriesCache[0]);
    })
    .catch(() => {
      savedQueriesCache = defaultPresets();
      renderSavedList();
      if (savedQueriesCache[0]) loadParams(savedQueriesCache[0]);
    });
}

function collectParams() {
  return {
    start_date: document.getElementById('start-date').value || '',
    end_date: document.getElementById('end-date').value || '',
    job_numbers: getSelectedValues('filter-job'),
    rev_numbers: getSelectedValues('filter-rev'),
    assemblies: getSelectedValues('filter-assembly'),
    customers: getSelectedValues('filter-customer'),
    operators: getSelectedValues('filter-operator'),
  };
}

function saveQuery() {
  const name = document.getElementById('save-name').value.trim();
  if (!name) { alert('Please provide a name for this chart.'); return; }
  const existing = savedQueriesCache.find((q) => q.name === name);
  if (existing && !confirm('Overwrite existing chart?')) return;
  const description = document.getElementById('chart-description').value.trim();
  const payload = {
    name,
    description,
    start_date: document.getElementById('start-date').value || '',
    end_date: document.getElementById('end-date').value || '',
    params: collectParams(),
  };
  const method = existing ? 'PUT' : 'POST';
  fetch('/analysis/aoi/saved', { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
    .then((res) => { if (!res.ok) throw new Error('save failed'); return res.json(); })
    .then(() => { document.getElementById('save-name').value=''; loadSavedQueries(); })
    .catch(() => alert('Failed to save chart. Ensure Supabase table exists.'));
}

document.getElementById('save-chart').addEventListener('click', saveQuery);

// Initialize on load
initFiltersUI();
loadSavedQueries();
