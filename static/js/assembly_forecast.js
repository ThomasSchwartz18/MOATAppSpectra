let inputCount = 0;
let chartInstance = null;

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
    renderChart(rows);
  } catch (err) {
    console.error('Forecast request failed', err);
  }
}

function renderTable(rows) {
  const tbody = document.querySelector('#forecast-table tbody');
  tbody.innerHTML = rows
    .map(
      (r) => `<tr>
      <td>${r.assembly}</td>
      <td>${r.boards}</td>
      <td>${r.falseCalls}</td>
      <td>${r.inspected}</td>
      <td>${r.rejected}</td>
      <td>${r.yield.toFixed(2)}</td>
      <td>${r.predictedRejects.toFixed(2)}</td>
      <td>${r.predictedYield.toFixed(2)}</td>
    </tr>`
    )
    .join('');
}

function renderChart(rows) {
  const labels = rows.map((r) => r.assembly);
  const actual = rows.map((r) => r.yield);
  const predicted = rows.map((r) => r.predictedYield);
  const ctx = document.getElementById('forecastChart').getContext('2d');
  if (chartInstance) chartInstance.destroy();
  chartInstance = new Chart(ctx, {
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

document.addEventListener('DOMContentLoaded', () => {
  addAssemblyInput();
  document
    .getElementById('run-forecast')
    .addEventListener('click', runForecast);
});
