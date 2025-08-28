let ppmChartInstance = null;
let ppmChartExpandedInstance = null;
let currentData = { labels: [], values: [] };
let savedQueriesCache = [];

const hLinePlugin = {
  id: 'hLines',
  afterDraw(chart) {
    const { ctx, chartArea: { left, right, top, bottom }, scales } = chart;
    const yScale = scales.y;
    if (!yScale) return;
    const lines = [
      { value: 20, color: 'red' },
      { value: 10, color: 'gold' },
      { value: 5, color: 'green' },
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

function parseRelativeDate(token) {
  // Supports patterns like today-1d, today-5d
  if (!token) return null;
  const m = String(token).trim().match(/^today-(\d+)d$/i);
  const now = new Date();
  if (m) {
    const days = parseInt(m[1], 10);
    const d = new Date(now);
    d.setDate(d.getDate() - days);
    return d.toISOString().slice(0, 10);
  }
  if (String(token).trim().toLowerCase() === 'today') {
    return now.toISOString().slice(0, 10);
  }
  return token;
}

function computeDerived(row, expr) {
  // Safe limited evaluator for expressions like a/b
  const ctx = {
    falsecall_parts: Number(row['FalseCall Parts'] ?? row['falsecall_parts'] ?? 0),
    total_boards: Number(row['Total Boards'] ?? row['total_boards'] ?? 0),
    total_parts: Number(row['Total Parts'] ?? row['total_parts'] ?? 0),
  };
  // Only allow identifiers, numbers, spaces, and operators + - * / ( ) .
  const safe = /^[\w\s+\-*/().]+$/.test(expr);
  if (!safe) return null;
  try {
    // eslint-disable-next-line no-new-func
    const fn = new Function('fc', 'tb', 'tp', `return (${expr.replaceAll('falsecall_parts','fc').replaceAll('total_boards','tb').replaceAll('total_parts','tp')});`);
    const v = fn(ctx.falsecall_parts, ctx.total_boards, ctx.total_parts);
    if (!isFinite(v)) return null;
    return Number(v);
  } catch (_) {
    return null;
  }
}

function buildOptions({ showTooltips, xTitle, yTitle }) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false }, tooltip: { enabled: showTooltips } },
    scales: {
      x: { display: !!xTitle, title: { display: !!xTitle, text: xTitle || '' }, grid: { display: false } },
      y: { display: !!yTitle, title: { display: !!yTitle, text: yTitle || '' }, grid: { display: false }, beginAtZero: true },
    },
  };
}

function renderChart(targetId, labels, values, cfg) {
  const ctx = document.getElementById(targetId).getContext('2d');
  const data = {
    labels,
    datasets: [
      {
        data: values,
        borderColor: cfg.color,
        backgroundColor: cfg.color,
        pointBackgroundColor: cfg.color,
        pointBorderColor: cfg.color,
        pointStyle: cfg.pointStyle,
        pointRadius: cfg.pointRadius,
        fill: false,
        tension: cfg.tension,
        borderWidth: 2,
      },
    ],
  };

  if (targetId === 'ppmChart' && ppmChartInstance) ppmChartInstance.destroy();
  if (targetId === 'ppmChartExpanded' && ppmChartExpandedInstance) ppmChartExpandedInstance.destroy();

  // eslint-disable-next-line no-undef
  const instance = new Chart(ctx, { type: cfg.type, data, options: buildOptions(cfg), plugins: [hLinePlugin] });
  if (targetId === 'ppmChart') ppmChartInstance = instance;
  if (targetId === 'ppmChartExpanded') ppmChartExpandedInstance = instance;
}

function fillTable(labels, values) {
  const tbody = document.getElementById('data-tbody');
  tbody.innerHTML = '';
  labels.forEach((lab, i) => {
    const tr = document.createElement('tr');
    const td1 = document.createElement('td');
    const td2 = document.createElement('td');
    td1.textContent = lab;
    td2.textContent = (values[i] ?? '').toFixed ? values[i].toFixed(4) : values[i];
    tr.appendChild(td1); tr.appendChild(td2);
    tbody.appendChild(tr);
  });
}

function updateInfo(labels, values) {
  const info = document.getElementById('ppm-info');
  const avg = values.length ? (values.reduce((a, b) => a + b, 0) / values.length).toFixed(4) : '0';
  info.textContent = `${labels[0] || ''} to ${labels[labels.length - 1] || ''} | Avg: ${avg}`;
}

function expandModal(show) {
  const overlay = document.getElementById('chart-modal');
  overlay.style.display = show ? 'flex' : 'none';
  if (show) {
    document.getElementById('modal-title').textContent = document.getElementById('chart-title').value || 'Chart Detail';
    renderChart('ppmChartExpanded', currentData.labels, currentData.values, collectChartConfig());
    fillTable(currentData.labels, currentData.values);
  }
}

function collectChartConfig() {
  const type = document.getElementById('chart-type').value || 'line';
  const color = document.getElementById('line-color').value || '#000000';
  const pointStyle = document.getElementById('point-style').value || 'circle';
  const pointRadius = Number(document.getElementById('point-radius').value || 3);
  const tension = Number(document.getElementById('line-tension').value || 0);
  const xTitle = document.getElementById('x-title').value || '';
  const yTitle = document.getElementById('y-title').value || '';
  const showTooltips = (document.getElementById('show-tooltips').value || 'yes') === 'yes';
  return { type, color, pointStyle, pointRadius, tension, xTitle, yTitle, showTooltips };
}

function collectParamsForSave() {
  return {
    title: document.getElementById('chart-title').value || '',
    start_date: document.getElementById('start-date').value || '',
    end_date: document.getElementById('end-date').value || '',
    transform_expression: document.getElementById('transform-expression').value || '',
    value_source: document.getElementById('value-source').value || 'avg_false_calls_per_assembly',
    options: collectChartConfig(),
  };
}

function loadParamsIntoBuilder(params) {
  document.getElementById('chart-title').value = params.title || '';
  document.getElementById('start-date').value = params.start_date || '';
  document.getElementById('end-date').value = params.end_date || '';
  document.getElementById('transform-expression').value = params.transform_expression || '';
  document.getElementById('value-source').value = params.value_source || 'avg_false_calls_per_assembly';
  if (params.options) {
    document.getElementById('chart-type').value = params.options.type || 'line';
    document.getElementById('line-color').value = params.options.color || '#000000';
    document.getElementById('point-style').value = params.options.pointStyle || 'circle';
    document.getElementById('point-radius').value = params.options.pointRadius ?? 3;
    document.getElementById('line-tension').value = params.options.tension ?? 0;
    document.getElementById('x-title').value = params.options.xTitle || '';
    document.getElementById('y-title').value = params.options.yTitle || '';
    document.getElementById('show-tooltips').value = params.options.showTooltips ? 'yes' : 'no';
  }
}

function filterSavedList() {
  const q = (document.getElementById('saved-search').value || '').toLowerCase();
  const list = document.getElementById('saved-list');
  list.innerHTML = '';
  const items = savedQueriesCache.filter((r) => (r.name || '').toLowerCase().includes(q));
  if (items.length === 0) {
    list.innerHTML = '<li style="color:#666;">No matches.</li>';
    return;
  }
  items.forEach((r) => {
    const li = document.createElement('li');
    li.textContent = r.name || r.type || 'Saved Chart';
    li.style.cursor = 'pointer';
    li.addEventListener('click', () => {
      const params = r.params || {};
      loadParamsIntoBuilder(params);
      runChart();
    });
    list.appendChild(li);
  });
}

function loadSavedQueries() {
  fetch('/analysis/ppm/saved')
    .then((res) => res.json())
    .then((rows) => {
      savedQueriesCache = Array.isArray(rows) ? rows : [];
      filterSavedList();
    })
    .catch(() => {
      savedQueriesCache = [];
      filterSavedList();
    });
}

function getDateInputs() {
  const rawStart = document.getElementById('start-date').value;
  const rawEnd = document.getElementById('end-date').value;
  const start = parseRelativeDate(rawStart);
  const end = parseRelativeDate(rawEnd);
  return { start, end, rawStart, rawEnd };
}

function runChart() {
  const { start, end } = getDateInputs();
  const source = document.getElementById('value-source').value;
  const expr = document.getElementById('transform-expression').value.trim();
  const title = document.getElementById('chart-title').value.trim();

  // If using built-in series, leverage backend aggregation ordered by date
  if (source === 'avg_false_calls_per_assembly') {
    const params = new URLSearchParams({ type: 'avg_false_calls_per_assembly' });
    if (start) params.append('start_date', start);
    if (end) params.append('end_date', end);
    fetch(`/analysis/ppm/data?${params.toString()}`)
      .then((res) => res.json())
      .then((payload) => {
        currentData = { labels: payload.labels || [], values: payload.values || [] };
        const cfg = collectChartConfig();
        renderChart('ppmChart', currentData.labels, currentData.values, cfg);
        updateInfo(currentData.labels, currentData.values);
        if (title) document.getElementById('modal-title').textContent = title;
      })
      .catch(() => { document.getElementById('ppm-info').textContent = 'Failed to load chart data.'; });
    return;
  }

  // Derived series: fetch raw moat and compute per day
  fetch('/moat')
    .then((res) => res.json())
    .then((rows) => {
      const map = new Map(); // date -> { sum, count }
      rows.forEach((row) => {
        const d = row['Report Date'] || row['report_date'];
        if (!d) return;
        const iso = String(d).slice(0, 10);
        if (start && iso < start) return;
        if (end && iso > end) return;
        let val = computeDerived(row, expr);
        if (val == null) return;
        const agg = map.get(iso) || { sum: 0, n: 0 };
        agg.sum += Number(val);
        agg.n += 1;
        map.set(iso, agg);
      });
      const labels = Array.from(map.keys()).sort();
      const values = labels.map((k) => {
        const { sum, n } = map.get(k);
        return n ? sum / n : 0;
      });
      currentData = { labels, values };
      const cfg = collectChartConfig();
      renderChart('ppmChart', labels, values, cfg);
      updateInfo(labels, values);
      if (title) document.getElementById('modal-title').textContent = title;
    })
    .catch(() => { document.getElementById('ppm-info').textContent = 'Failed to compute derived chart.'; });
}

function saveQuery() {
  const name = document.getElementById('save-name').value.trim();
  if (!name) { alert('Please provide a name for this chart.'); return; }
  const payload = {
    name,
    type: 'custom',
    params: collectParamsForSave(),
  };
  fetch('/analysis/ppm/saved', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
    .then((res) => { if (!res.ok) throw new Error('save failed'); return res.json(); })
    .then(() => { document.getElementById('save-name').value=''; loadSavedQueries(); })
    .catch(() => alert('Failed to save chart. Ensure Supabase table exists.'));
}

async function copyChartImage() {
  const canvas = document.getElementById('ppmChart');
  if (!navigator.clipboard || !navigator.clipboard.write) {
    alert('Clipboard API not supported in this browser.');
    return;
  }
  try {
    const blob = await new Promise((resolve) => canvas.toBlob(resolve));
    await navigator.clipboard.write([new ClipboardItem({ [blob.type]: blob })]);
    alert('Chart image copied to clipboard.');
  } catch (e) {
    alert('Failed to copy image.');
  }
}

function downloadPDF() {
  const canvas = document.getElementById('ppmChart');
  const imgData = canvas.toDataURL('image/png');
  // eslint-disable-next-line no-undef
  const { jsPDF } = window.jspdf;
  const pdf = new jsPDF({ orientation: 'l', unit: 'pt', format: 'letter' });
  const pageWidth = pdf.internal.pageSize.getWidth();
  const pageHeight = pdf.internal.pageSize.getHeight();
  const margin = 36;
  const usableW = pageWidth - margin * 2;
  const usableH = pageHeight - margin * 2;
  pdf.addImage(imgData, 'PNG', margin, margin, usableW, usableH, undefined, 'FAST');
  const title = document.getElementById('chart-title').value || 'chart';
  pdf.save(`${title}.pdf`);
}

document.addEventListener('DOMContentLoaded', () => {
  // Preset from preview
  const url = new URL(window.location.href);
  const preset = url.searchParams.get('preset');
  if (preset === 'avg_false_calls_per_assembly') {
    document.getElementById('value-source').value = 'avg_false_calls_per_assembly';
    document.getElementById('chart-title').value = 'Average False Calls Per Assembly';
    document.getElementById('y-title').value = 'Avg False Calls';
    document.getElementById('x-title').value = 'Date';
  }

  document.getElementById('run-chart').addEventListener('click', runChart);
  document.getElementById('save-query').addEventListener('click', saveQuery);
  document.getElementById('saved-search').addEventListener('input', filterSavedList);
  document.getElementById('expand-chart').addEventListener('click', () => expandModal(true));
  document.getElementById('modal-close').addEventListener('click', () => expandModal(false));
  document.getElementById('download-pdf').addEventListener('click', downloadPDF);
  document.getElementById('copy-image').addEventListener('click', copyChartImage);

  loadSavedQueries();
  runChart();
});
