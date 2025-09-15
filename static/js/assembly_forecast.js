let inputCount = 0;
let yieldChartInstance = null;
let fcChartInstance = null;
let ngChartInstance = null;
let customerYieldChartInstance = null;

const hLinePlugin = {
  id: 'hLines',
  afterDraw(chart) {
    const {
      ctx,
      chartArea: { left, right, top, bottom },
      scales,
    } = chart;
    const yScale = scales.y;
    if (!yScale) return;
    const lines = [
      { value: 20, color: 'red' },
      { value: 15, color: 'gold' },
      { value: 10, color: 'green' },
    ];
    ctx.save();
    ctx.setLineDash([4, 4]);
    lines.forEach((ln) => {
      const y = yScale.getPixelForValue(ln.value);
      if (y >= top && y <= bottom) {
        ctx.beginPath();
        ctx.moveTo(left, y);
        ctx.lineTo(right, y);
        ctx.strokeStyle = ln.color;
        ctx.lineWidth = 1;
        ctx.stroke();
      }
    });
    ctx.restore();
  },
};

function addAssemblyInput() {
  const container = document.getElementById('assembly-inputs');
  const idx = inputCount++;
  const wrapper = document.createElement('div');
  wrapper.className = 'field';
  const input = document.createElement('input');
  input.type = 'text';
  input.setAttribute('list', `asm-list-${idx}`);
  input.className = 'asm-input';
  const list = document.createElement('datalist');
  list.id = `asm-list-${idx}`;
  wrapper.appendChild(input);
  wrapper.appendChild(list);
  container.appendChild(wrapper);

  input.addEventListener('input', () => fetchSuggestions(input.value, list));
  input.addEventListener('change', () => {
    if (input.value && container.lastElementChild === wrapper) {
      addAssemblyInput();
    }
  });
}

async function fetchSuggestions(term, listEl) {
  if (!term) {
    listEl.innerHTML = '';
    return;
  }
  try {
    const res = await fetch(`/api/assemblies/search?q=${encodeURIComponent(term)}`);
    const suggestions = await res.json();
    listEl.innerHTML = suggestions.map((s) => `<option value="${s}">`).join('');
  } catch (err) {
    console.error('Suggestion fetch failed', err);
  }
}

async function runForecast() {
  const container = document.getElementById('assembly-inputs');
  const assemblies = Array.from(container.querySelectorAll('input'))
    .map((i) => i.value.trim())
    .filter((v) => v);
  if (!assemblies.length) return;
  try {
    const res = await fetch('/api/assemblies/forecast', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ assemblies }),
    });
    const data = await res.json();
    const rows = data.assemblies || [];
    renderTable(rows);
    renderYieldChart(rows);
    renderCustomerYieldChart(rows);
    renderFalseCallChart(rows);
    renderNGRatioChart(rows);
  } catch (err) {
    console.error('Forecast request failed', err);
  }
}

function renderTable(rows) {
  const tbody = document.querySelector('#forecast-table tbody');
  const missingEl = document.getElementById('missing-msg');
  const missingAsms = [];
  tbody.innerHTML = rows
    .map((r) => {
      if (r.missing) missingAsms.push(r.assembly);
      return `<tr${r.missing ? ' class="missing"' : ''}>
      <td>${r.assembly}</td>
      <td>${r.boards}</td>
      <td>${r.falseCalls}</td>
      <td>${r.avgFalseCalls.toFixed(2)}</td>
      <td>${r.predictedFalseCalls.toFixed(2)}</td>
      <td>${r.predictedFCPerBoard.toFixed(2)}</td>
      <td>${r.inspected}</td>
      <td>${r.rejected}</td>
      <td>${r.ngRatio.toFixed(2)}</td>
      <td>${r.yield.toFixed(2)}</td>
      <td>${r.predictedRejects.toFixed(2)}</td>
      <td>${r.predictedNGsPerBoard.toFixed(2)}</td>
      <td>${r.predictedYield.toFixed(2)}</td>
      <td>${r.customerYield.toFixed(2)}</td>
    </tr>`;
    })
    .join('');
  if (missingEl) {
    if (missingAsms.length) {
      missingEl.style.display = 'block';
      missingEl.textContent = `Assemblies not found: ${missingAsms.join(', ')}`;
    } else {
      missingEl.style.display = 'none';
      missingEl.textContent = '';
    }
  }
}

function renderYieldChart(rows) {
  const labels = rows.map((r) => r.assembly);
  const actual = rows.map((r) => r.yield);
  const predicted = rows.map((r) => r.predictedYield);
  const ctx = document.getElementById('forecastChart').getContext('2d');
  if (yieldChartInstance) yieldChartInstance.destroy();
  // eslint-disable-next-line no-undef
  yieldChartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label: 'Yield %',
          data: actual,
          backgroundColor: 'rgba(54,162,235,0.5)',
        },
        {
          label: 'Predicted Yield %',
          data: predicted,
          backgroundColor: 'rgba(255,99,132,0.5)',
        },
      ],
    },
    options: {
      responsive: true,
      scales: { y: { beginAtZero: true, max: 100 } },
    },
  });
}

function renderCustomerYieldChart(rows) {
  const aggregates = {};
  rows.forEach((r) => {
    const cust = r.customer || 'Unknown';
    if (!aggregates[cust]) {
      aggregates[cust] = { inspected: 0, rejected: 0 };
    }
    aggregates[cust].inspected += r.inspected;
    aggregates[cust].rejected += r.rejected;
  });
  const labels = Object.keys(aggregates);
  const data = labels.map((c) => {
    const { inspected, rejected } = aggregates[c];
    return inspected ? ((inspected - rejected) / inspected) * 100 : 0;
  });
  const ctx = document
    .getElementById('customerYieldChart')
    .getContext('2d');
  if (customerYieldChartInstance) customerYieldChartInstance.destroy();
  // eslint-disable-next-line no-undef
  customerYieldChartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label: 'Customer Yield %',
          data,
          backgroundColor: 'rgba(75,192,192,0.5)',
        },
      ],
    },
    options: {
      responsive: true,
      scales: { y: { beginAtZero: true, max: 100 } },
    },
  });
}

function renderFalseCallChart(rows) {
  const labels = rows.map((r) => r.assembly);
  const data = rows.map((r) => r.avgFalseCalls);
  const ctx = document.getElementById('falseCallChart').getContext('2d');
  if (fcChartInstance) fcChartInstance.destroy();
  // eslint-disable-next-line no-undef
  fcChartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'Avg FC/Board',
          data,
          borderColor: '#000',
          backgroundColor: '#000',
          pointBackgroundColor: '#000',
          pointBorderColor: '#000',
          pointRadius: 3,
          fill: false,
          tension: 0,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: true } },
    },
    plugins: [hLinePlugin],
  });
}

function renderNGRatioChart(rows) {
  const labels = rows.map((r) => r.assembly);
  const data = rows.map((r) => r.ngRatio);
  const ctx = document.getElementById('ngRatioChart').getContext('2d');
  if (ngChartInstance) ngChartInstance.destroy();
  // eslint-disable-next-line no-undef
  ngChartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'NG Ratio %',
          data,
          borderColor: '#000',
          backgroundColor: '#000',
          pointBackgroundColor: '#000',
          pointBorderColor: '#000',
          pointRadius: 3,
          fill: false,
          tension: 0,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: true } },
    },
    plugins: [hLinePlugin],
  });
}

document.addEventListener('DOMContentLoaded', () => {
  addAssemblyInput();
  document
    .getElementById('run-forecast')
    .addEventListener('click', runForecast);
});
