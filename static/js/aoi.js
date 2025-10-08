import { showSpinner, hideSpinner } from './utils.js';

let aoiChartInstance = null;
let aoiChartExpandedInstance = null;
let currentData = { labels: [], accepted: [], rejected: [] };
let customerOptions = [];
let operatorOptions = [];

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

function getTextValues(id) {
  const val = document.getElementById(id).value || '';
  return val.split(',').map((v) => v.trim()).filter((v) => v);
}

function getDropdownValues(className) {
  return Array.from(document.querySelectorAll('select.' + className))
    .map((sel) => sel.value)
    .filter((v) => v);
}

function initFiltersUI() {
  return fetch('/aoi_reports')
    .then((r) => r.json())
    .then((rows) => {
      if (!Array.isArray(rows)) return;
      customerOptions = uniqueSorted(rows.map((r) => r['Customer']));
      operatorOptions = uniqueSorted(rows.map((r) => r['Operator']));
      populateDynamicSelect('customer-wrapper', 'filter-customer', customerOptions);
      populateDynamicSelect('operator-wrapper', 'filter-operator', operatorOptions);
    });
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
    plugins: {
      tooltip: {
        callbacks: {
          label(ctx) {
            const label = ctx.dataset.label || '';
            const value = ctx.parsed.y;
            const total = ctx.chart.data.datasets.reduce((sum, ds) => sum + ds.data[ctx.dataIndex], 0);
            const pct = total ? ((value / total) * 100).toFixed(1) : 0;
            return `${label}: ${value} (${pct}%)`;
          },
        },
      },
    },
  };
  if (targetId === 'aoiChart' && aoiChartInstance) aoiChartInstance.destroy();
  if (targetId === 'aoiChartExpanded' && aoiChartExpandedInstance) aoiChartExpandedInstance.destroy();
  // eslint-disable-next-line no-undef
  const inst = new Chart(ctx, { type: 'bar', data, options });
  if (targetId === 'aoiChart') aoiChartInstance = inst; else aoiChartExpandedInstance = inst;
}

function renderShiftChart(targetId, labels, shift1, shift2) {
  const ctx = document.getElementById(targetId).getContext('2d');
  const data = {
    labels,
    datasets: [
      { label: '1st Accepted', data: shift1.accepted, backgroundColor: 'rgba(54,162,235,0.6)', stack: 'shift1' },
      { label: '1st Rejected', data: shift1.rejected, backgroundColor: 'rgba(255,99,132,0.6)', stack: 'shift1' },
      { label: '2nd Accepted', data: shift2.accepted, backgroundColor: 'rgba(75,192,192,0.6)', stack: 'shift2' },
      { label: '2nd Rejected', data: shift2.rejected, backgroundColor: 'rgba(255,206,86,0.6)', stack: 'shift2' },
    ],
  };
  const options = {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      x: { stacked: true },
      y: { stacked: true, beginAtZero: true },
    },
    plugins: {
      tooltip: {
        callbacks: {
          label(ctx) {
            const label = ctx.dataset.label || '';
            const value = ctx.parsed.y;
            const total = ctx.chart.data.datasets
              .filter((ds) => ds.stack === ctx.dataset.stack)
              .reduce((sum, ds) => sum + ds.data[ctx.dataIndex], 0);
            const pct = total ? ((value / total) * 100).toFixed(1) : 0;
            return `${label}: ${value} (${pct}%)`;
          },
        },
      },
    },
  };
  if (targetId === 'aoiChart' && aoiChartInstance) aoiChartInstance.destroy();
  if (targetId === 'aoiChartExpanded' && aoiChartExpandedInstance) aoiChartExpandedInstance.destroy();
  // eslint-disable-next-line no-undef
  const inst = new Chart(ctx, { type: 'bar', data, options });
  if (targetId === 'aoiChart') aoiChartInstance = inst; else aoiChartExpandedInstance = inst;
}

function renderYieldChart(targetId, labels, yields) {
  const ctx = document.getElementById(targetId).getContext('2d');
  const minY = yields.length ? Math.min(...yields) : 0;
  const data = {
    labels,
    datasets: [
      { label: 'Yield %', data: yields, backgroundColor: 'rgba(75,192,192,0.6)', borderColor: 'rgba(75,192,192,0.8)', fill: false },
    ],
  };
  const options = {
    responsive: true,
    maintainAspectRatio: false,
    scales: { y: { beginAtZero: false, min: minY, max: 100, ticks: { callback: (v) => v + '%' } } },
  };
  if (targetId === 'aoiChart' && aoiChartInstance) aoiChartInstance.destroy();
  if (targetId === 'aoiChartExpanded' && aoiChartExpandedInstance) aoiChartExpandedInstance.destroy();
  // eslint-disable-next-line no-undef
  const inst = new Chart(ctx, { type: 'line', data, options });
  if (targetId === 'aoiChart') aoiChartInstance = inst; else aoiChartExpandedInstance = inst;
}

function renderRateChart(targetId, labels, rates) {
  const ctx = document.getElementById(targetId).getContext('2d');
  const data = {
    labels,
    datasets: [
      { label: 'Reject %', data: rates, backgroundColor: 'rgba(255,99,132,0.6)' },
    ],
  };
  const options = {
    responsive: true,
    maintainAspectRatio: false,
    scales: { y: { beginAtZero: true, max: 100, ticks: { callback: (v) => v + '%' } } },
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
    const total = accepted[i] + rejected[i];
    const accPct = total ? ((accepted[i] / total) * 100).toFixed(1) : 0;
    const rejPct = total ? ((rejected[i] / total) * 100).toFixed(1) : 0;
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${lab}</td><td>${accepted[i]}</td><td>${rejected[i]}</td><td>${accPct}%</td><td>${rejPct}%</td>`;
    tbody.appendChild(tr);
  });
}

function fillShiftTable(labels, shift1, shift2) {
  const tbody = document.getElementById('data-tbody');
  tbody.innerHTML = '';
  labels.forEach((lab, i) => {
    const entries = [
      { name: `${lab} 1st`, acc: shift1.accepted[i], rej: shift1.rejected[i] },
      { name: `${lab} 2nd`, acc: shift2.accepted[i], rej: shift2.rejected[i] },
    ];
    entries.forEach((e) => {
      const total = e.acc + e.rej;
      const accPct = total ? ((e.acc / total) * 100).toFixed(1) : 0;
      const rejPct = total ? ((e.rej / total) * 100).toFixed(1) : 0;
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${e.name}</td><td>${e.acc}</td><td>${e.rej}</td><td>${accPct}%</td><td>${rejPct}%</td>`;
      tbody.appendChild(tr);
    });
  });
}

function fillYieldTable(labels, yields) {
  const tbody = document.getElementById('data-tbody');
  tbody.innerHTML = '';
  labels.forEach((lab, i) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${lab}</td><td>${yields[i].toFixed(1)}%</td>`;
    tbody.appendChild(tr);
  });
}

function fillRateTable(labels, rates) {
  const tbody = document.getElementById('data-tbody');
  tbody.innerHTML = '';
  labels.forEach((lab, i) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${lab}</td><td>${rates[i].toFixed(1)}%</td>`;
    tbody.appendChild(tr);
  });
}

function renderAssemblyTable(tableId, assemblies, inspected, rejected, yields) {
  const table = document.getElementById(tableId);
  if (!table) return;
  table.innerHTML = '<thead><tr><th>Assembly</th><th>Total Inspected</th><th>Total Rejected</th><th>Yield %</th></tr></thead><tbody></tbody>';
  const tbody = table.querySelector('tbody');
  assemblies.forEach((asm, i) => {
    const y = yields[i]?.toFixed ? yields[i].toFixed(1) : yields[i];
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${asm}</td><td>${inspected[i]}</td><td>${rejected[i]}</td><td>${y}%</td>`;
    tbody.appendChild(tr);
  });
  makeSortable(table);
}

function makeSortable(table) {
  const headers = table.querySelectorAll('th');
  headers.forEach((th, idx) => {
    th.addEventListener('click', () => {
      const tbody = table.querySelector('tbody');
      const rows = Array.from(tbody.querySelectorAll('tr'));
      const asc = th.getAttribute('data-sort') !== 'asc';
      rows.sort((a, b) => {
        const av = a.children[idx].textContent.replace('%', '');
        const bv = b.children[idx].textContent.replace('%', '');
        const aNum = parseFloat(av);
        const bNum = parseFloat(bv);
        const cmp = Number.isNaN(aNum) || Number.isNaN(bNum) ? av.localeCompare(bv) : aNum - bNum;
        return asc ? cmp : -cmp;
      });
      rows.forEach((r) => tbody.appendChild(r));
      headers.forEach((h) => h.removeAttribute('data-sort'));
      th.setAttribute('data-sort', asc ? 'asc' : 'desc');
    });
  });
}

function expandModal(show) {
  const overlay = document.getElementById('chart-modal');
  overlay.style.display = show ? 'flex' : 'none';
  if (show) {
    const chartBox = document.querySelector('.modal-chart-box');
    chartBox.style.display = 'block';
    const thead = document.querySelector('.data-table thead');
    if (currentData.shift1 && currentData.shift2) {
      if (thead) thead.innerHTML = '<tr><th>Date / Shift</th><th>Accepted</th><th>Rejected</th><th>Accepted %</th><th>Rejected %</th></tr>';
      renderShiftChart('aoiChartExpanded', currentData.labels, currentData.shift1, currentData.shift2);
      fillShiftTable(currentData.labels, currentData.shift1, currentData.shift2);
    } else if (currentData.yields) {
      if (thead) thead.innerHTML = '<tr><th>Date</th><th>Yield %</th></tr>';
      renderYieldChart('aoiChartExpanded', currentData.labels, currentData.yields);
      fillYieldTable(currentData.labels, currentData.yields);
    } else if (currentData.rates) {
      if (thead) thead.innerHTML = '<tr><th>Customer</th><th>Rejection %</th></tr>';
      renderRateChart('aoiChartExpanded', currentData.labels, currentData.rates);
      fillRateTable(currentData.labels, currentData.rates);
    } else if (currentData.assemblies) {
      chartBox.style.display = 'none';
      renderAssemblyTable('modal-data-table', currentData.assemblies, currentData.inspected, currentData.rejected, currentData.yields);
    } else {
      if (thead) thead.innerHTML = '<tr><th>Operator</th><th>Accepted</th><th>Rejected</th><th>Accepted %</th><th>Rejected %</th></tr>';
      renderChart('aoiChartExpanded', currentData.labels, currentData.accepted, currentData.rejected);
      fillTable(currentData.labels, currentData.accepted, currentData.rejected);
    }
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
  let csv = '';
  if (currentData.shift1 && currentData.shift2) {
    csv = 'Date,Shift,Accepted,Rejected,Accepted %,Rejected %\n';
    currentData.labels.forEach((lab, i) => {
      ['1st', '2nd'].forEach((sh) => {
        const acc = currentData[sh === '1st' ? 'shift1' : 'shift2'].accepted[i];
        const rej = currentData[sh === '1st' ? 'shift1' : 'shift2'].rejected[i];
        const total = acc + rej;
        const accPct = total ? ((acc / total) * 100).toFixed(1) : 0;
        const rejPct = total ? ((rej / total) * 100).toFixed(1) : 0;
        csv += `${lab},${sh},${acc},${rej},${accPct},${rejPct}\n`;
      });
    });
  } else if (currentData.yields) {
    csv = 'Date,Yield %\n';
    currentData.labels.forEach((lab, i) => {
      csv += `${lab},${currentData.yields[i].toFixed(1)}\n`;
    });
  } else if (currentData.rates) {
    csv = 'Customer,Rejection %\n';
    currentData.labels.forEach((lab, i) => {
      csv += `${lab},${currentData.rates[i].toFixed(1)}\n`;
    });
  } else if (currentData.assemblies) {
    csv = 'Assembly,Total Inspected,Total Rejected,Yield %\n';
    currentData.assemblies.forEach((asm, i) => {
      const y = currentData.yields[i]?.toFixed ? currentData.yields[i].toFixed(1) : currentData.yields[i];
      csv += `${asm},${currentData.inspected[i]},${currentData.rejected[i]},${y}\n`;
    });
  } else {
    csv = 'Operator,Accepted,Rejected,Accepted %,Rejected %\n';
    currentData.labels.forEach((lab, i) => {
      const total = currentData.accepted[i] + currentData.rejected[i];
      const accPct = total ? ((currentData.accepted[i] / total) * 100).toFixed(1) : 0;
      const rejPct = total ? ((currentData.rejected[i] / total) * 100).toFixed(1) : 0;
      csv += `${lab},${currentData.accepted[i]},${currentData.rejected[i]},${accPct},${rejPct}\n`;
    });
  }
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
    job_numbers: getTextValues('filter-job').join(','),
    rev_numbers: getTextValues('filter-rev').join(','),
    assemblies: getTextValues('filter-assembly').join(','),
    customers: getDropdownValues('filter-customer').join(','),
    operators: getDropdownValues('filter-operator').join(','),
  };
  const title = document.getElementById('chart-title').value || '';
  const range = (params.start_date || params.end_date)
    ? ` (${params.start_date || ''} to ${params.end_date || ''})`
    : '';
  document.getElementById('result-chart-name').textContent = title + range;
  const qs = new URLSearchParams(params).toString();
  fetch(`/analysis/aoi/data?${qs}`)
    .then((r) => r.json())
    .then((res) => {
      document.getElementById('preview-table').style.display = 'none';
      document.getElementById('aoiChart').style.display = 'block';
      if (res.shift1 && res.shift2) {
        currentData = { labels: res.labels || [], shift1: res.shift1, shift2: res.shift2 };
        renderShiftChart('aoiChart', currentData.labels, currentData.shift1, currentData.shift2);
        const s1 = res.shift1.avg_reject_rate?.toFixed ? res.shift1.avg_reject_rate.toFixed(1) : res.shift1.avg_reject_rate;
        const s2 = res.shift2.avg_reject_rate?.toFixed ? res.shift2.avg_reject_rate.toFixed(1) : res.shift2.avg_reject_rate;
        document.getElementById('aoi-info').textContent = `1st Shift Avg Reject Rate: ${s1}% | 2nd Shift Avg Reject Rate: ${s2}%`;
      } else if (res.yields) {
        currentData = { labels: res.labels || [], yields: res.yields || [] };
        renderYieldChart('aoiChart', currentData.labels, currentData.yields);
        const avg = res.avg_yield?.toFixed ? res.avg_yield.toFixed(1) : res.avg_yield;
        const min = res.min_yield?.toFixed ? res.min_yield.toFixed(1) : res.min_yield;
        const max = res.max_yield?.toFixed ? res.max_yield.toFixed(1) : res.max_yield;
        document.getElementById('aoi-info').textContent = `Avg Yield: ${avg}% | Min: ${min}% | Max: ${max}%`;
      } else if (res.rates) {
        currentData = { labels: res.labels || [], rates: res.rates || [] };
        renderRateChart('aoiChart', currentData.labels, currentData.rates);
        const avg = res.avg_rate?.toFixed ? res.avg_rate.toFixed(1) : res.avg_rate;
        const maxRate = res.max_rate?.toFixed ? res.max_rate.toFixed(1) : res.max_rate;
        const minRate = res.min_rate?.toFixed ? res.min_rate.toFixed(1) : res.min_rate;
        document.getElementById('aoi-info').textContent = `Max: ${res.max_customer} ${maxRate}% | Min: ${res.min_customer} ${minRate}% | Avg: ${avg}%`;
      } else if (res.assemblies) {
        currentData = { assemblies: res.assemblies || [], inspected: res.inspected || [], rejected: res.rejected || [], yields: res.yields || [] };
        document.getElementById('aoiChart').style.display = 'none';
        document.getElementById('preview-table').style.display = 'table';
        renderAssemblyTable('preview-table', currentData.assemblies, currentData.inspected, currentData.rejected, currentData.yields);
        document.getElementById('aoi-info').textContent = '';
      } else {
        currentData = { labels: res.labels || [], accepted: res.accepted || [], rejected: res.rejected || [] };
        renderChart('aoiChart', currentData.labels, currentData.accepted, currentData.rejected);
        document.getElementById('aoi-info').textContent = '';
      }
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

document.getElementById('download-pdf').addEventListener('click', async () => {
  showSpinner('download-pdf');
  try {
    const { jsPDF } = window.jspdf;
    const doc = new jsPDF();

    const title = document.getElementById('chart-title').value || 'Report';
    const start = document.getElementById('start-date').value || '';
    const end = document.getElementById('end-date').value || '';
    const range = start || end ? `${start} to ${end}` : '';

    const logo = new Image();
    logo.src = '/static/images/company-logo.png';
    await logo.decode();
    const pageWidth = doc.internal.pageSize.getWidth();
    doc.addImage(logo, 'PNG', (pageWidth - 40) / 2, 20, 40, 40);
    doc.setFontSize(18);
    doc.text(title, pageWidth / 2, 70, { align: 'center' });
    if (range) {
      doc.setFontSize(12);
      doc.text(range, pageWidth / 2, 80, { align: 'center' });
    }

    doc.addPage();
    const canvas = document.getElementById('aoiChart');
    const dataURL = canvas.toDataURL('image/png', 1.0);
    const imgProps = doc.getImageProperties(dataURL);
    const pdfWidth = doc.internal.pageSize.getWidth();
    const pdfHeight = (imgProps.height * pdfWidth) / imgProps.width;
    doc.addImage(dataURL, 'PNG', 0, 0, pdfWidth, pdfHeight);

    doc.addPage();
    let head = [];
    const body = [];
    if (currentData.shift1 && currentData.shift2) {
      head = [['Date / Shift', 'Accepted', 'Rejected', 'Accepted %', 'Rejected %']];
      currentData.labels.forEach((lab, i) => {
        const acc1 = currentData.shift1.accepted[i];
        const rej1 = currentData.shift1.rejected[i];
        const tot1 = acc1 + rej1;
        body.push([`${lab} 1st`, acc1, rej1, tot1 ? ((acc1 / tot1) * 100).toFixed(1) : 0, tot1 ? ((rej1 / tot1) * 100).toFixed(1) : 0]);
        const acc2 = currentData.shift2.accepted[i];
        const rej2 = currentData.shift2.rejected[i];
        const tot2 = acc2 + rej2;
        body.push([`${lab} 2nd`, acc2, rej2, tot2 ? ((acc2 / tot2) * 100).toFixed(1) : 0, tot2 ? ((rej2 / tot2) * 100).toFixed(1) : 0]);
      });
    } else if (currentData.yields) {
      head = [['Date', 'Yield %']];
      currentData.labels.forEach((lab, i) => {
        body.push([lab, currentData.yields[i]?.toFixed ? currentData.yields[i].toFixed(1) : currentData.yields[i]]);
      });
    } else if (currentData.rates) {
      head = [['Customer', 'Rejection %']];
      currentData.labels.forEach((lab, i) => {
        body.push([lab, currentData.rates[i]?.toFixed ? currentData.rates[i].toFixed(1) : currentData.rates[i]]);
      });
    } else if (currentData.assemblies) {
      head = [['Assembly', 'Inspected', 'Rejected', 'Yield %']];
      currentData.assemblies.forEach((asm, i) => {
        const y = currentData.yields[i]?.toFixed ? currentData.yields[i].toFixed(1) : currentData.yields[i];
        body.push([asm, currentData.inspected[i], currentData.rejected[i], y]);
      });
    } else {
      head = [['Operator', 'Accepted', 'Rejected', 'Accepted %', 'Rejected %']];
      currentData.labels.forEach((lab, i) => {
        const total = currentData.accepted[i] + currentData.rejected[i];
        const accPct = total ? ((currentData.accepted[i] / total) * 100).toFixed(1) : 0;
        const rejPct = total ? ((currentData.rejected[i] / total) * 100).toFixed(1) : 0;
        body.push([lab, currentData.accepted[i], currentData.rejected[i], accPct, rejPct]);
      });
    }
    // eslint-disable-next-line no-undef
    doc.autoTable({ head, body });

    doc.save(`${title}.pdf`);
  } finally {
    hideSpinner('download-pdf');
  }
});

// Tab switching for Chart Builder / Upload
document.querySelectorAll('.tab').forEach((tab) => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach((t) => t.classList.remove('active'));
    tab.classList.add('active');
    document.querySelectorAll('.tab-content').forEach((c) => { c.style.display = 'none'; });
    const target = document.getElementById(tab.dataset.target);
    if (target) target.style.display = 'block';
  });
});

// Handle CSV upload
const uploadForm = document.getElementById('upload-form');
if (uploadForm) {
  uploadForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const fileInput = document.getElementById('upload-csv');
    if (!fileInput.files.length) { alert('Please select a file.'); return; }
    const fd = new FormData();
    fd.append('file', fileInput.files[0]);
    try {
      const res = await fetch('/aoi_reports/upload', { method: 'POST', body: fd });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || 'Upload failed');
      }
      const data = await res.json();
      alert(`Uploaded ${data.inserted} rows`);
      fileInput.value = '';
    } catch (err) {
      alert(err.message || 'Upload failed');
    }
  });
}

// Initialize on load
initFiltersUI().then(() => runChart());
