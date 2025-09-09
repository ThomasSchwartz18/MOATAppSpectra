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
  const downloadControls = document.getElementById('download-controls');
  const downloadBtn = document.getElementById('download-report');
  let dailyChart = null;

  if (downloadControls) downloadControls.style.display = 'none';

  fetch('/aoi_reports')
    .then((r) => r.json())
    .then((rows) => {
      if (!Array.isArray(rows)) return;
      operatorOptions = uniqueSorted(rows.map((r) => r['Operator']));
      populateDynamicSelect('operator-wrapper', 'filter-operator', operatorOptions);
    });

  runBtn?.addEventListener('click', () => {
    const start = document.getElementById('start-date').value;
    const end = document.getElementById('end-date').value;
    const operator = getDropdownValues('filter-operator').join(',');
    if (!start || !end) {
      alert('Please select a date range.');
      return;
    }
    const params = new URLSearchParams({ start_date: start, end_date: end });
    if (operator) params.append('operator', operator);
    fetch(`/api/reports/operator?${params.toString()}`)
      .then((res) => res.json())
      .then((data) => {
        renderReport(data);
        if (downloadControls) downloadControls.style.display = 'flex';
      })
      .catch(() => alert('Failed to run report.'));
  });

  downloadBtn?.addEventListener('click', () => {
    const fmt = document.getElementById('file-format').value;
    const start = document.getElementById('start-date').value;
    const end = document.getElementById('end-date').value;
    const operator = getDropdownValues('filter-operator').join(',');
    const params = new URLSearchParams({ format: fmt });
    if (start) params.append('start_date', start);
    if (end) params.append('end_date', end);
    if (operator) params.append('operator', operator);
    window.location = `/reports/operator/export?${params.toString()}`;
  });

  document.getElementById('email-report')?.addEventListener('click', () => {
    alert('Email sent (placeholder).');
  });

  function setDesc(id, lines) {
    const el = document.getElementById(id);
    if (!el) return;
    el.innerHTML = lines.map((line) => `<span>${line}</span>`).join('');
  }

  function renderReport(data) {
    const { daily = {}, summary = {}, assemblies = [] } = data || {};
    const dailySection = document.getElementById('dailySection');
    const assemblySection = document.getElementById('assemblySection');

    const hasDaily = (daily.dates || []).length > 0;
    if (hasDaily) {
      dailySection.style.display = 'block';
      if (dailyChart) dailyChart.destroy();
      const ctx = document.getElementById('dailyChart').getContext('2d');
      dailyChart = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: daily.dates,
          datasets: [
            {
              type: 'bar',
              label: 'Boards Inspected',
              data: daily.inspected,
              backgroundColor: 'steelblue',
              yAxisID: 'y',
            },
            {
              type: 'line',
              label: 'Reject %',
              data: daily.rejectRates,
              yAxisID: 'y1',
              borderColor: 'crimson',
              backgroundColor: 'crimson',
              tension: 0.1,
              pointRadius: 3,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: { mode: 'index', intersect: false },
          scales: {
            y: {
              beginAtZero: true,
              title: { display: true, text: 'Boards Inspected' },
            },
            y1: {
              beginAtZero: true,
              max: 100,
              position: 'right',
              grid: { drawOnChartArea: false },
              ticks: { callback: (v) => `${v}%` },
              title: { display: true, text: 'Reject %' },
            },
          },
          plugins: { legend: { display: true } },
        },
      });
      setDesc('dailyDesc', [
        `<strong>Total boards:</strong> ${summary.totalBoards ?? 0}`,
        `<strong>Average boards per 10-hour shift:</strong> ${(summary.avgPerShift ?? 0).toFixed(2)}`,
        `<strong>Average reject rate:</strong> ${(summary.avgRejectRate ?? 0).toFixed(2)}%`,
      ]);
      const dTable = document.getElementById('dailyTable');
      const dTbody = dTable.querySelector('tbody');
      dTbody.innerHTML = '';
      (daily.dates || []).forEach((d, i) => {
        const tr = document.createElement('tr');
        const dateTd = document.createElement('td');
        dateTd.textContent = d;
        const rateTd = document.createElement('td');
        rateTd.textContent = `${(daily.rejectRates[i] ?? 0).toFixed(2)}%`;
        tr.appendChild(dateTd);
        tr.appendChild(rateTd);
        dTbody.appendChild(tr);
      });
      dTable.style.display = 'table';
    } else {
      dailySection.style.display = 'none';
    }

    const aTable = document.getElementById('assemblyTotals');
    const aTbody = aTable.querySelector('tbody');
    aTbody.innerHTML = '';
    if ((assemblies || []).length > 0) {
      assemblySection.style.display = 'block';
      assemblies.forEach((a) => {
        const tr = document.createElement('tr');
        const nameTd = document.createElement('td');
        nameTd.textContent = a.assembly;
        const inspTd = document.createElement('td');
        inspTd.textContent = a.inspected;
        tr.appendChild(nameTd);
        tr.appendChild(inspTd);
        aTbody.appendChild(tr);
      });
      aTable.style.display = 'table';
    } else {
      assemblySection.style.display = 'none';
    }
  }
});
