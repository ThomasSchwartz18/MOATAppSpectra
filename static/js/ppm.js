let ppmChartInstance = null;
let ppmChartExpandedInstance = null;
let currentData = { labels: [], values: [], datasets: [] };
let savedQueriesCache = [];

// Inferred columns/types from /moat
let allColumns = [];
let columnTypes = {}; // { colName: 'temporal'|'numeric'|'categorical'|'boolean' }

// Dynamic control limit lines: mean, UCL, LCL
const controlLinesPlugin = {
  id: 'controlLines',
  afterDraw(chart) {
    const opts = chart?.options?.controlLimits;
    if (!opts) return;
    const { mean, ucl, lcl } = opts;
    const { ctx, chartArea: { left, right, top, bottom }, scales } = chart;
    const yScale = scales.y;
    if (!yScale) return;
    const lines = [
      { value: mean, color: '#0077ff', dash: [6, 4], width: 1.5 },
      { value: ucl, color: '#ff4d4d', dash: [4, 4], width: 1 },
      { value: lcl, color: '#00b894', dash: [4, 4], width: 1 },
    ].filter((ln) => ln.value != null && isFinite(ln.value));
    ctx.save();
    lines.forEach((ln) => {
      const y = yScale.getPixelForValue(ln.value);
      if (y >= top && y <= bottom) {
        ctx.beginPath();
        ctx.moveTo(left, y);
        ctx.lineTo(right, y);
        ctx.setLineDash(ln.dash);
        ctx.strokeStyle = ln.color;
        ctx.lineWidth = ln.width;
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

function withMetaTooltip(opts, metaLookup, showTooltips = true) {
  if (!opts.plugins) opts.plugins = {};
  if (!opts.plugins.tooltip) opts.plugins.tooltip = {};
  opts.plugins.tooltip.enabled = showTooltips;
  if (!metaLookup) return opts;
  const baseCb = opts.plugins.tooltip.callbacks && opts.plugins.tooltip.callbacks.label;
  if (!opts.plugins.tooltip.callbacks) opts.plugins.tooltip.callbacks = {};
  const toArr = (v) => (v == null ? [] : Array.isArray(v) ? v : [v]);
  opts.plugins.tooltip.callbacks.label = (context) => {
    const dsLabel = context.dataset?.label || '';
    const lbl = context.label ?? context.dataIndex;
    const key = `${dsLabel}||${lbl}`;
    const meta = metaLookup[key] || metaLookup[lbl] || metaLookup[context.dataIndex];
    const val = context.formattedValue;
    const base = baseCb ? baseCb(context) : (dsLabel ? `${dsLabel}: ${val}` : `${val}`);
    const parts = [];
    const fromRaw = context.raw || {};
    const metaSrc = meta || { date: toArr(fromRaw.date), line: toArr(fromRaw.line), model: toArr(fromRaw.model) };
    if (metaSrc.date && metaSrc.date.length) parts.push(`Date: ${metaSrc.date.join(', ')}`);
    if (metaSrc.line && metaSrc.line.length) parts.push(`Line: ${metaSrc.line.join(', ')}`);
    if (metaSrc.model && metaSrc.model.length) parts.push(`Model: ${metaSrc.model.join(', ')}`);
    return parts.length ? `${base} (${parts.join(' | ')})` : base;
  };
  return opts;
}

function buildOptions({ showTooltips, xTitle, yTitle, controlLimits, xTickDisplay = true, metaLookup }) {
  const opts = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false }, tooltip: { enabled: showTooltips } },
    scales: {
      x: { display: !!xTitle, title: { display: !!xTitle, text: xTitle || '' }, grid: { display: false }, ticks: { display: xTickDisplay } },
      y: { display: !!yTitle, title: { display: !!yTitle, text: yTitle || '' }, grid: { display: false }, beginAtZero: true },
    },
    controlLimits: controlLimits || null,
  };
  return withMetaTooltip(opts, metaLookup, showTooltips);
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
  const instance = new Chart(ctx, { type: cfg.type, data, options: buildOptions(cfg), plugins: [controlLinesPlugin] });
  if (targetId === 'ppmChart') ppmChartInstance = instance;
  if (targetId === 'ppmChartExpanded') ppmChartExpandedInstance = instance;
}

// Render multiple datasets (series) against shared labels
function renderChartMulti(targetId, labels, datasets, cfg) {
  const ctx = document.getElementById(targetId).getContext('2d');
  const mk = (i) => {
    const hue = (i * 53) % 360;
    const base = `hsl(${hue} 75% 45%)`;
    return {
      borderColor: base,
      backgroundColor: cfg.type === 'bar' ? `hsl(${hue} 75% 65% / 0.6)` : `hsl(${hue} 75% 65% / 0.25)`,
      pointBackgroundColor: base,
      pointBorderColor: base,
    };
  };
  const chartDatasets = datasets.map((d, i) => ({
    label: d.label,
    data: d.data,
    ...mk(i),
    pointStyle: cfg.pointStyle,
    pointRadius: cfg.pointRadius,
    fill: false,
    tension: cfg.tension,
    borderWidth: 2,
  }));

  if (targetId === 'ppmChart' && ppmChartInstance) ppmChartInstance.destroy();
  if (targetId === 'ppmChartExpanded' && ppmChartExpandedInstance) ppmChartExpandedInstance.destroy();

  // eslint-disable-next-line no-undef
  const baseOpts = buildOptions(cfg);
  const instance = new Chart(ctx, {
    type: cfg.type === 'area' ? 'line' : cfg.type,
    data: { labels, datasets: chartDatasets },
    options: { ...baseOpts, plugins: { ...baseOpts.plugins, legend: { display: true } } },
    plugins: [controlLinesPlugin],
  });
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
    const cfg = collectChartConfig();
    if (ppmChartExpandedInstance) ppmChartExpandedInstance.destroy();
    const expandedCanvas = document.getElementById('ppmChartExpanded');
    const box = expandedCanvas.parentElement;
    const rect = box.getBoundingClientRect();
    if (rect.width && rect.height) {
      expandedCanvas.style.width = rect.width + 'px';
      expandedCanvas.style.height = rect.height + 'px';
    }
    const ctx = expandedCanvas.getContext('2d');
    const meta = window.currentChartMeta || { labels: currentData.labels, datasets: currentData.datasets.length? currentData.datasets : [{ label: activePreset?.name || 'Series', data: currentData.values }], type: 'line', options: buildOptions(cfg) };
    const opts = { ...meta.options };
    if (opts.scales && opts.scales.x && opts.scales.x.ticks) opts.scales.x.ticks.display = true;
    // eslint-disable-next-line no-undef
    ppmChartExpandedInstance = new Chart(ctx, { type: meta.type, data: { labels: meta.labels, datasets: meta.datasets }, options: opts, plugins: (activePreset?.kind==='line-control' ? [controlLinesPlugin] : []) });
    const vals = meta.datasets[0] && Array.isArray(meta.datasets[0].data) ? meta.datasets[0].data : currentData.values;
    fillTable(meta.labels || currentData.labels, vals);
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
  const params = {
    title: document.getElementById('chart-title').value || '',
    description: document.getElementById('chart-description').value || '',
    start_date: document.getElementById('start-date').value || '',
    end_date: document.getElementById('end-date').value || '',
    transform_expression: document.getElementById('transform-expression').value || '',
    value_source: document.getElementById('value-source').value || 'avg_false_calls_per_assembly',
    x_column: document.getElementById('x-column').value || '',
    x_binning: document.getElementById('x-binning').value || 'none',
    x_cat_sort: document.getElementById('x-cat-sort').value || 'alpha-asc',
    y_agg: document.getElementById('y-agg').value || 'avg',
    series_column: document.getElementById('series-column').value || '',
    options: collectChartConfig(),
  };

  return {
    params,
    start_date: params.start_date,
    end_date: params.end_date,
    value_source: params.value_source,
    x_column: params.x_column,
    y_agg: params.y_agg,
    chart_type: params.options.type,
    line_color: params.options.color,
  };
}

function loadParamsIntoBuilder(row) {
  const params = row.params || {};
  document.getElementById('chart-title').value = params.title || '';
  document.getElementById('chart-description').value = row.description || params.description || '';
  document.getElementById('start-date').value = row.start_date || params.start_date || '';
  document.getElementById('end-date').value = row.end_date || params.end_date || '';
  document.getElementById('transform-expression').value = params.transform_expression || '';
  document.getElementById('value-source').value = row.value_source || params.value_source || 'avg_false_calls_per_assembly';
  const xCol = row.x_column || params.x_column;
  if (xCol) document.getElementById('x-column').value = xCol;
  if (params.x_binning) document.getElementById('x-binning').value = params.x_binning;
  if (params.x_cat_sort) document.getElementById('x-cat-sort').value = params.x_cat_sort;
  const yAgg = row.y_agg || params.y_agg;
  if (yAgg) document.getElementById('y-agg').value = yAgg;
  if (params.series_column !== undefined) document.getElementById('series-column').value = params.series_column;
  const chartType = row.chart_type || params.options?.type;
  const lineColor = row.line_color || params.options?.color;
  if (chartType) document.getElementById('chart-type').value = chartType;
  if (lineColor) document.getElementById('line-color').value = lineColor;
  if (params.options) {
    document.getElementById('point-style').value = params.options.pointStyle || 'circle';
    document.getElementById('point-radius').value = params.options.pointRadius ?? 3;
    document.getElementById('line-tension').value = params.options.tension ?? 0;
    document.getElementById('x-title').value = params.options.xTitle || '';
    document.getElementById('y-title').value = params.options.yTitle || '';
    document.getElementById('show-tooltips').value = params.options.showTooltips ? 'yes' : 'no';
  }
  updateXTypeUI();
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
    li.title = r.description || '';
    li.style.cursor = 'pointer';
      li.addEventListener('click', () => {
        if (r.params) {
          loadParamsIntoBuilder(r);
          document.getElementById('chart-description-result').textContent = r.description || '';
        } else if (r.id) {
          setPreset(r.id);
        }
        runChart();
      });
    list.appendChild(li);
  });
}

function loadSavedQueries() {
  fetch('/analysis/ppm/saved')
    .then((res) => res.json())
    .then((rows) => {
      const server = Array.isArray(rows)
        ? rows.map((r) => ({ ...r, description: r.description || r.params?.description || '' }))
        : [];
      savedQueriesCache = presetsList().concat(server);
      filterSavedList();
    })
    .catch(() => {
      savedQueriesCache = presetsList();
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
  const title = document.getElementById('chart-title').value.trim();
  const { start, end } = getDateInputs();
  const range = (start || end) ? ` (${start || ''} to ${end || ''})` : '';
  document.getElementById('result-chart-name').textContent = (title || '(untitled)') + range;
  const description = document.getElementById('chart-description').value.trim();

  const xCol = document.getElementById('x-column')?.value || '';
  const sCol = document.getElementById('series-column')?.value || '';
  const expr = document.getElementById('transform-expression')?.value.trim() || '';
  const yAgg = document.getElementById('y-agg')?.value || 'avg';
  const xBin = document.getElementById('x-binning')?.value || 'none';
  const xSort = document.getElementById('x-cat-sort')?.value || 'alpha-asc';
  const src = document.getElementById('value-source')?.value || 'avg_false_calls_per_assembly';

  const hasCustom = Boolean(
    xCol || sCol || expr || src !== 'avg_false_calls_per_assembly' ||
    yAgg !== 'avg' || xBin !== 'none' || xSort !== 'alpha-asc'
  );

  const runner = hasCustom ? runChartFlexible() : runPresetChart();
  runner
    .then((result) => {
      const cfg = collectChartConfig();
      const canvasEl = document.getElementById('ppmChart');

      if (hasCustom) {
        const labels = result.labels || [];
        const datasets = result.datasets || [];
        const chartType = cfg.type === 'area' ? 'line' : cfg.type;
        const chartCfg = { ...cfg, type: chartType, xTickDisplay: false, metaLookup: result.metaLookup };
        const container = canvasEl.parentElement;
        const minPerLabel = 120;
        const width = Math.max(container.clientWidth, labels.length * minPerLabel);
        canvasEl.style.width = width + 'px';
        if (datasets.length > 1) {
          renderChartMulti('ppmChart', labels, datasets, chartCfg);
        } else {
          renderChart('ppmChart', labels, datasets[0]?.data || [], chartCfg);
        }
        currentData = { labels, values: datasets[0]?.data || [], datasets, metaLookup: result.metaLookup };
        window.currentChartMeta = { labels, datasets, type: chartType, options: buildOptions(chartCfg), metaLookup: result.metaLookup };
        updateInfo(labels, datasets[0]?.data || []);
        if (title) document.getElementById('modal-title').textContent = title;
        document.getElementById('chart-description-result').textContent = description;
        return;
      }

      const ctx = canvasEl.getContext('2d');
      let chartType = 'line';
      let options = buildOptions({ ...cfg, xTickDisplay: false, metaLookup: result.metaLookup });
      let datasets = [];
      let labels = [];

      if (result.kind === 'line-control') {
        labels = result.labels; datasets = [{ label: activePreset?.name || 'Series', data: result.values, borderColor: cfg.color, backgroundColor: cfg.color, pointRadius: cfg.pointRadius, pointStyle: cfg.pointStyle, fill: false, tension: cfg.tension, borderWidth: 2 }];
        options = buildOptions({ ...cfg, controlLimits: result.limits, xTickDisplay: false, metaLookup: result.metaLookup });
        chartType = 'line';
        const container = canvasEl.parentElement; const minPerLabel = 120; const width = Math.max(container.clientWidth, labels.length * minPerLabel); canvasEl.style.width = width + 'px';
      } else if (result.kind === 'pareto') {
        labels = result.labels; datasets = result.datasets; chartType = 'bar';
        const basePareto = buildOptions({ ...cfg, xTickDisplay: false, metaLookup: result.metaLookup });
        options = {
          ...basePareto,
          scales: { x: { ...basePareto.scales.x }, y: { beginAtZero: true }, y2: { beginAtZero: true, position: 'right', grid: { drawOnChartArea: false }, ticks: { callback: (v)=> v + '%' } } },
          plugins: { ...basePareto.plugins, legend: { display: true } }
        };
        const container = canvasEl.parentElement; const minPerLabel = 120; const width = Math.max(container.clientWidth, labels.length * minPerLabel); canvasEl.style.width = width + 'px';
      } else if (result.kind === 'fc_avg_and_ppm') {
        labels = result.labels; datasets = result.datasets; chartType = 'bar';
        const baseDual = buildOptions({ ...cfg, xTickDisplay: false, metaLookup: result.metaLookup });
        options = {
          ...baseDual,
          scales: { x: { ...baseDual.scales.x }, y: { beginAtZero: true }, y2: { beginAtZero: true, position: 'right', grid: { drawOnChartArea: false } } },
          plugins: { ...baseDual.plugins, legend: { display: true } }
        };
        const container = canvasEl.parentElement; const minPerLabel = 120; const width = Math.max(container.clientWidth, labels.length * minPerLabel); canvasEl.style.width = width + 'px';
      } else if (result.kind === 'scatter') {
        chartType = 'scatter'; labels = []; datasets = [{ label: 'Models', data: result.points, pointRadius: cfg.pointRadius, backgroundColor: cfg.color, borderColor: cfg.color }];
        options = withMetaTooltip({ responsive: true, maintainAspectRatio: false, plugins: { legend: { display: true } }, scales: { x: { type: 'linear', title: { display: true, text: 'NG PPM' } }, y: { type: 'linear', title: { display: true, text: 'FalseCall PPM' } } } }, result.metaLookup, cfg.showTooltips);
        canvasEl.style.width = '100%';
      } else if (result.kind === 'ts_ng_by_line' || result.kind === 'ts_fc_vs_ng') {
        labels = result.labels; datasets = result.datasets; chartType = 'line';
        const baseTs = buildOptions({ ...cfg, metaLookup: result.metaLookup });
        options = { ...baseTs, plugins: { ...baseTs.plugins, legend: { display: true } } };
        canvasEl.style.width = '100%';
      } else if (result.kind === 'ratio_fc_ng') {
        labels = result.labels; datasets = [{ label: 'FC/NG Ratio', data: result.values, backgroundColor: cfg.color, borderColor: cfg.color }]; chartType = 'bar';
        const baseRatio = buildOptions({ ...cfg, xTickDisplay: false, metaLookup: result.metaLookup });
        options = { ...baseRatio, plugins: { ...baseRatio.plugins, legend: { display: false } }, scales: { y: { beginAtZero: true } } };
        const container = canvasEl.parentElement; const minPerLabel = 120; const width = Math.max(container.clientWidth, labels.length * minPerLabel); canvasEl.style.width = width + 'px';
      }

      if (ppmChartInstance) ppmChartInstance.destroy();
      // eslint-disable-next-line no-undef
      ppmChartInstance = new Chart(ctx, { type: chartType, data: { labels, datasets }, options, plugins: (result.kind==='line-control' ? [controlLinesPlugin] : []) });
      currentData = { labels, values: datasets[0]?.data || [], datasets, metaLookup: result.metaLookup };
      window.currentChartMeta = { labels, datasets, type: chartType, options, metaLookup: result.metaLookup };
      updateInfo(labels, datasets[0]?.data || []);
      if (title) document.getElementById('modal-title').textContent = title;
      document.getElementById('chart-description-result').textContent = description;
    })
    .catch(() => { document.getElementById('ppm-info').textContent = 'Failed to build chart.'; });
}

// Flexible builder: group by arbitrary X, optional series, aggregation choice
async function runChartFlexible() {
  const { start, end } = getDateInputs();
  const source = document.getElementById('value-source').value;
  const expr = document.getElementById('transform-expression').value.trim();
  const xCol = document.getElementById('x-column').value;
  const sCol = document.getElementById('series-column').value || '';
  const yAgg = document.getElementById('y-agg').value || 'avg';
  const xBin = document.getElementById('x-binning').value || 'none';
  const xSort = document.getElementById('x-cat-sort').value || 'alpha-asc';

  const rows = await fetch('/moat').then((r) => r.json());
  if (!rows || !rows.length) return { labels: [], datasets: [], firstValues: [], metaLookup: {} };
  const cols = window.__ppm_cols__ || resolveColumns(rows);

  // Value per row
  const valueFn = (row) => {
    if (yAgg === 'count') return 1;
    if (source === 'avg_false_calls_per_assembly') {
      const fc = Number(row['FalseCall Parts'] ?? row['falsecall_parts'] ?? 0);
      const tb = Number(row['Total Boards'] ?? row['total_boards'] ?? 0);
      return tb ? fc / tb : 0;
    }
    // derived
    const v = computeDerived(row, expr);
    return v == null ? 0 : Number(v);
  };

  const xType = (columnTypes[xCol] || 'categorical');
  const keyFns = {
    temporal: (v) => {
      const d = (v instanceof Date) ? v : new Date(v);
      if (!d || isNaN(+d)) return '';
      const y = d.getUTCFullYear();
      const m = d.getUTCMonth();
      const dd = d.getUTCDate();
      switch (xBin) {
        case 'year': return `${y}`;
        case 'quarter': return `${y}-Q${Math.floor(m/3)+1}`;
        case 'month': return `${y}-${String(m+1).padStart(2,'0')}`;
        case 'week': {
          const day = d.getUTCDay();
          const monday = new Date(Date.UTC(y, m, dd - ((day+6)%7)));
          return `W${monday.toISOString().slice(0,10)}`;
        }
        case 'day':
        case 'none':
        default: return d.toISOString().slice(0,10);
      }
    },
    numeric: (v) => Number(v),
    categorical: (v) => String(v ?? ''),
    boolean: (v) => String(Boolean(v)),
  };

  // Grouping
  const groups = new Map(); // xKey -> seriesKey -> {sum,count,min,max,meta:{dates:Set,lines:Set,models:Set}}
  const sKeys = new Set();
  rows.forEach((row) => {
    // Date window is based on Report Date if present
    const dr = row['Report Date'] || row['report_date'];
    if (start && dr && String(dr).slice(0,10) < start) return;
    if (end && dr && String(dr).slice(0,10) > end) return;
    const raw = row[xCol];
    const xKey = keyFns[xType] ? keyFns[xType](raw) : String(raw ?? '');
    const seriesKey = sCol ? String(row[sCol]) : '__single__';
    sKeys.add(seriesKey);
    if (!groups.has(xKey)) groups.set(xKey, new Map());
    const m = groups.get(xKey);
    if (!m.has(seriesKey)) m.set(seriesKey, { sum:0, count:0, min: Infinity, max: -Infinity, meta:{dates:new Set(), lines:new Set(), models:new Set()} });
    const st = m.get(seriesKey);
    const v = Number(valueFn(row));
    if (!isFinite(v)) return;
    st.sum += v;
    st.count += 1;
    st.min = Math.min(st.min, v);
    st.max = Math.max(st.max, v);
    if (cols.date && row[cols.date]) st.meta.dates.add(String(row[cols.date]).slice(0,10));
    if (cols.line && row[cols.line] !== undefined) st.meta.lines.add(String(row[cols.line]));
    if (cols.model && row[cols.model] !== undefined) st.meta.models.add(String(row[cols.model]));
  });

  // Labels sorting
  let labels = Array.from(groups.keys());
  const sorters = {
    temporal: (a,b) => (new Date(a)) - (new Date(b)),
    numeric: (a,b) => parseFloat(a) - parseFloat(b),
    categorical: (a,b) => {
      if (xSort === 'alpha-asc') return String(a).localeCompare(String(b));
      if (xSort === 'alpha-desc') return String(b).localeCompare(String(a));
      const freq = (k) => Array.from((groups.get(k)||new Map()).values()).reduce((acc, st) => acc + st.count, 0);
      return xSort === 'freq-desc' ? (freq(b) - freq(a)) : (freq(a) - freq(b));
    },
    boolean: (a,b) => String(a).localeCompare(String(b)),
  };
  labels.sort(sorters[xType] || ((a,b)=>String(a).localeCompare(String(b))));

  const seriesOrdered = sCol ? Array.from(sKeys).sort() : ['__single__'];
  const datasets = [];
  const metaLookup = {};
  seriesOrdered.forEach((sKey) => {
    const data = labels.map((xk, idx) => {
      const st = groups.get(xk)?.get(sKey);
      if (!st) return 0;
      const meta = {
        date: Array.from(st.meta.dates),
        line: Array.from(st.meta.lines),
        model: Array.from(st.meta.models),
      };
      const dsLabel = sCol ? `${sKey}` : (document.getElementById('y-agg').selectedOptions[0]?.text || 'Value');
      metaLookup[`${dsLabel}||${labels[idx]}`] = meta;
      switch (yAgg) {
        case 'sum': return st.sum;
        case 'avg': return st.count ? st.sum / st.count : 0;
        case 'min': return isFinite(st.min) ? st.min : 0;
        case 'max': return isFinite(st.max) ? st.max : 0;
        case 'count': default: return st.count;
      }
    });
    datasets.push({ label: sCol ? `${sKey}` : (document.getElementById('y-agg').selectedOptions[0]?.text || 'Value'), data });
  });

  return { labels, datasets, firstValues: datasets[0]?.data || [], metaLookup };
}

// Presets and filter-focused charting
let activePreset = null; // { id, name, kind, yTitle?, calc? }

function presetsList() {
  return [
    { id: 'avg_fc_per_board', name: 'Avg False Calls per Board (by Model)', kind: 'line-control', yTitle: 'Avg False Calls/Board', calc: (agg) => (agg.boardSum ? agg.fcSum / agg.boardSum : 0), groupByModel: false },
    { id: 'fc_parts_per_total_parts', name: 'False Call % of Program (by Model)', kind: 'line-control', yTitle: 'False Call % of Program', calc: (agg) => (agg.partsSum ? (agg.fcSum / agg.partsSum) * 100 : 0) },
    { id: 'fc_rate_per_part', name: 'False Call Rate per Part (by Model)', kind: 'line-control', yTitle: 'False Call Rate per Part', calc: (agg) => (agg.partsSum ? (agg.fcSum / agg.partsSum) : 0) },
    { id: 'fc_avg_and_ppm', name: 'Avg FC/Board + FC PPM (by Model)', kind: 'fc_avg_and_ppm' },
    { id: 'pareto_ng_by_model', name: 'Pareto of Defects (NG Parts by Model)', kind: 'pareto' },
    { id: 'scatter_fc_vs_ng', name: 'False Call vs True Defect (Scatter)', kind: 'scatter' },
    { id: 'ng_rate_over_time_by_line', name: 'Defect Rate Over Time (NG PPM by Line)', kind: 'ts_ng_by_line' },
    { id: 'fc_vs_ng_rate_over_time', name: 'False Call vs NG Rate Over Time', kind: 'ts_fc_vs_ng' },
    { id: 'ratio_fc_to_ng', name: 'False Call / True NG Ratio (by Model)', kind: 'ratio_fc_ng' },
  ];
}

function setPreset(id) {
  const p = presetsList().find((x) => x.id === id) || presetsList()[0];
  activePreset = p;
  const titleEl = document.getElementById('chart-title');
  const yEl = document.getElementById('y-title');
  const xEl = document.getElementById('x-title');
  if (titleEl) titleEl.value = p.name;
  if (yEl) yEl.value = p.yTitle || '';
  if (xEl) xEl.value = (p.kind && p.kind.startsWith('ts')) ? 'Date' : 'Model Name';
}

function computeControlLimits(values) {
  if (!values.length) return { mean: 0, ucl: 0, lcl: 0 };
  const mean = values.reduce((a,b)=>a+b,0)/values.length;
  const variance = values.reduce((a,b)=>a + Math.pow(b-mean,2), 0) / values.length;
  const stdev = Math.sqrt(variance);
  const ucl = mean + 3*stdev;
  const lcl = Math.max(0, mean - 3*stdev);
  return { mean, ucl, lcl };
}

function resolveColumns(rows) {
  const cols = rows[0] ? Object.keys(rows[0]) : [];
  const find = (cands) => cands.find((c) => cols.includes(c));
  return {
    date: find(['Report Date','report_date']),
    model: find(['Model Name','model_name','Model']),
    line: find(['Line','line','Line Name','line_name']),
    assembly: find(['Assembly','assembly','Program','program']),
    rev: find(['Rev','rev','Revision','revision']),
    ngParts: find(['NG Parts','ng_parts','NG','ng','Defect Parts','defect_parts']),
    ngPPM: find(['NG PPM','ng_ppm','NG_PPM']),
    fcParts: find(['FalseCall Parts','falsecall_parts']),
    totalBoards: find(['Total Boards','total_boards']),
    totalParts: find(['Total Parts','total_parts']),
  };
}

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

function initFiltersUI() {
  fetch('/moat')
    .then((r) => r.json())
    .then((rows) => {
      if (!Array.isArray(rows) || rows.length === 0) return;
      // Infer column types and full column list for sorting
      const inferred = inferTypes(rows);
      allColumns = inferred.cols;
      columnTypes = inferred.types;
      const cols = resolveColumns(rows);
      // Assembly + Rev
      const wrapA = document.getElementById('wrap-assembly');
      const wrapR = document.getElementById('wrap-rev');
      const aSel = document.getElementById('filter-assembly');
      const rSel = document.getElementById('filter-rev');
      if (!cols.assembly) { if (wrapA) wrapA.style.display = 'none'; if (wrapR) wrapR.style.display = 'none'; }
      else if (aSel) {
        const assemblies = uniqueSorted(rows.map((r)=> r[cols.assembly] ));
        aSel.innerHTML = '<option value="">(All)</option>' + assemblies.map((v)=>`<option value="${String(v)}">${String(v)}</option>`).join('');
        aSel.addEventListener('change', () => {
          const selA = aSel.value;
          if (!cols.rev || !rSel) { if (rSel) { rSel.disabled = true; rSel.innerHTML = ''; } return; }
          const revs = uniqueSorted(rows.filter((r)=> !selA || String(r[cols.assembly])===selA).map((r)=> r[cols.rev]));
          rSel.innerHTML = '<option value="">(All)</option>' + revs.map((v)=>`<option value="${String(v)}">${String(v)}</option>`).join('');
          rSel.disabled = false;
        });
      }
      // Lines multi-selects
      const linesWrap = document.getElementById('filter-lines');
      const addBtn = document.getElementById('add-line');
      if (!cols.line) { if (addBtn) addBtn.style.display = 'none'; if (linesWrap) linesWrap.style.display = 'none'; }
      else if (linesWrap && addBtn) {
        const lines = uniqueSorted(rows.map((r)=> r[cols.line] ));
        const mkSelect = () => {
          const sel = document.createElement('select');
          sel.className = 'line-select';
          sel.innerHTML = '<option value="">(Any)</option>' + lines.map((v)=>`<option value="${String(v)}">${String(v)}</option>`).join('');
          return sel;
        };
        linesWrap.appendChild(mkSelect());
        addBtn.addEventListener('click', () => { linesWrap.appendChild(mkSelect()); });
      }
      // Store for later filtering
      window.__ppm_cols__ = cols;
      // Populate Sort-By selector
      const sortSel = document.getElementById('sort-column');
      if (sortSel) {
        // keep existing (None) and (Y Value) options, append columns
        allColumns.forEach((c) => {
          const opt = document.createElement('option'); opt.value=c; opt.textContent=c; sortSel.appendChild(opt);
        });
      }
    })
    .catch(()=>{});
}

function readFilters() {
  const { start, end } = getDateInputs();
  const modelContains = (document.getElementById('filter-model-contains')?.value || '').toLowerCase().trim();
  const hasTH = !!document.getElementById('filter-has-th')?.checked;
  const hasSMT = !!document.getElementById('filter-has-smt')?.checked;
  const assembly = document.getElementById('filter-assembly')?.value || '';
  const rev = document.getElementById('filter-rev')?.value || '';
  const lineSelects = Array.from(document.querySelectorAll('#filter-lines .line-select'));
  const lines = lineSelects.map((s)=>s.value).filter((v)=>v);
  const sortColumn = document.getElementById('sort-column')?.value || '';
  const sortDir = document.getElementById('sort-dir')?.value || 'desc';
  const minBoards = Number(document.getElementById('filter-min-boards')?.value || 7);
  return { start, end, modelContains, hasTH, hasSMT, assembly, rev, lines, sortColumn, sortDir, minBoards };
}

async function runPresetChart() {
  const rows = await fetch('/moat').then((r)=>r.json());
  if (!activePreset) setPreset('avg_fc_per_board');
  const cols = window.__ppm_cols__ || resolveColumns(rows);
  const f = readFilters();
  const kind = activePreset.kind || 'line-control';
  // filter rows
  const filtered = rows.filter((row) => {
    // Date window
    if (cols.date) {
      const d = row[cols.date];
      const iso = d ? String(d).slice(0,10) : '';
      if (f.start && iso && iso < f.start) return false;
      if (f.end && iso && iso > f.end) return false;
    }
    // Assembly / Rev
    if (cols.assembly && f.assembly && String(row[cols.assembly]) !== f.assembly) return false;
    if (cols.rev && f.rev && String(row[cols.rev]) !== f.rev) return false;
    // Lines (OR across selected)
    if (cols.line && f.lines.length) {
      const v = String(row[cols.line]);
      if (!f.lines.includes(v)) return false;
    }
    // Model contains filters
    if (cols.model) {
      const m = String(row[cols.model] ?? '').toLowerCase();
      if (f.modelContains && !m.includes(f.modelContains)) return false;
      if ((f.hasTH || f.hasSMT) && !(m.includes('th') || m.includes('smt'))) return false;
    }
    return true;
  });
  // Apply minimum boards per model (default 7)
  let filteredByBoards = filtered;
  if (cols.totalBoards && cols.model) {
    const boardsByModel = new Map();
    filtered.forEach((row) => {
      const m = String(row[cols.model] ?? 'Unknown');
      const b = Number(row[cols.totalBoards] ?? 0);
      boardsByModel.set(m, (boardsByModel.get(m) || 0) + (isFinite(b) ? b : 0));
    });
    const threshold = Number(f.minBoards) || 7;
    const allowed = new Set(Array.from(boardsByModel.entries()).filter(([,sum]) => (sum || 0) >= threshold).map(([m]) => m));
    filteredByBoards = filtered.filter((row) => allowed.has(String(row[cols.model] ?? 'Unknown')));
  }

  // For presets that skip model grouping, compute per-row values
  if (kind === 'line-control' && activePreset.groupByModel === false) {
    let rowsSeq = filteredByBoards.slice();
    if (cols.date) {
      rowsSeq.sort((a, b) => {
        const da = Date.parse(String(a[cols.date]));
        const db = Date.parse(String(b[cols.date]));
        if (isNaN(da) && isNaN(db)) return 0;
        if (isNaN(da)) return 1;
        if (isNaN(db)) return -1;
        return da - db;
      });
    }
    const labels = [];
    const values = [];
    const metaLookup = {};
    rowsSeq.forEach((row, idx) => {
      const agg = {
        fcSum: Number(row[cols.fcParts] ?? 0),
        boardSum: Number(row[cols.totalBoards] ?? 0),
        partsSum: Number(row[cols.totalParts] ?? 0),
      };
      const val = activePreset.calc ? activePreset.calc(agg) : 0;
      const label = cols.model && row[cols.model] !== undefined
        ? String(row[cols.model])
        : (cols.date && row[cols.date] ? String(row[cols.date]).slice(0, 10) : 'Unknown');
      labels.push(label);
      values.push(val);
      metaLookup[idx] = {
        date: cols.date && row[cols.date] ? [String(row[cols.date]).slice(0, 10)] : [],
        line: cols.line && row[cols.line] !== undefined ? [String(row[cols.line])] : [],
        model: cols.model && row[cols.model] !== undefined ? [String(row[cols.model])] : [],
      };
    });
    const limits = computeControlLimits(values);
    return { kind, labels, values, limits, metaLookup };
  }

  // group by model
  const groups = new Map(); // model -> { ngSum, fcSum, boardSum, partsSum, meta:{dates:Set, lines:Set, models:Set} }
  filteredByBoards.forEach((row) => {
    const model = cols.model ? String(row[cols.model] ?? 'Unknown') : 'Unknown';
    if (!groups.has(model)) groups.set(model, { ngSum:0, fcSum:0, boardSum:0, partsSum:0, meta:{dates:new Set(), lines:new Set(), models:new Set()} });
    const g = groups.get(model);
    if (cols.date && row[cols.date]) g.meta.dates.add(String(row[cols.date]).slice(0,10));
    if (cols.line && row[cols.line] !== undefined) g.meta.lines.add(String(row[cols.line]));
    if (cols.model && row[cols.model] !== undefined) g.meta.models.add(String(row[cols.model]));
    // NG parts: prefer explicit NG Parts; fallback to NG PPM * Total Parts / 1e6
    if (cols.ngParts) {
      g.ngSum += Number(row[cols.ngParts] ?? 0);
    } else if (cols.ngPPM && cols.totalParts) {
      const parts = Number(row[cols.totalParts] ?? 0);
      const ppm = Number(row[cols.ngPPM] ?? 0);
      if (isFinite(parts) && isFinite(ppm)) g.ngSum += (parts * ppm) / 1e6;
    }
    g.fcSum += Number(row[cols.fcParts] ?? 0);
    g.boardSum += Number(row[cols.totalBoards] ?? 0);
    g.partsSum += Number(row[cols.totalParts] ?? 0);
  });

  // Build per-model sort keys if a column (other than Y) is chosen
  let sortAgg = null;
  if (f.sortColumn && f.sortColumn !== '__y__') {
    sortAgg = new Map();
    const colName = f.sortColumn;
    const t = columnTypes[colName] || 'categorical';
    filteredByBoards.forEach((row) => {
      const model = cols.model ? String(row[cols.model] ?? 'Unknown') : 'Unknown';
      let agg = sortAgg.get(model);
      if (!agg) { agg = { type: t, sum:0, count:0, max:null, min:null, last:null }; sortAgg.set(model, agg); }
      const v = row[colName];
      if (t === 'numeric') {
        const n = Number(v);
        if (isFinite(n)) { agg.sum += n; agg.count += 1; }
      } else if (t === 'temporal') {
        // Expecting YYYY-MM-DD; Date.parse handles this
        const ts = v ? Date.parse(String(v)) : NaN;
        if (!isNaN(ts)) {
          agg.max = (agg.max == null) ? ts : Math.max(agg.max, ts); // latest date per model
          agg.min = (agg.min == null) ? ts : Math.min(agg.min, ts);
        }
      } else {
        agg.last = (v == null) ? '' : String(v);
      }
    });
  }

  if (kind === 'line-control') {
    let labels = Array.from(groups.keys());
    const yByModel = new Map(labels.map((m)=>[m, activePreset.calc(groups.get(m))]));
    if (f.sortColumn === '__y__') {
      labels.sort((a,b) => (yByModel.get(a) - yByModel.get(b)) * (f.sortDir === 'desc' ? -1 : 1));
    } else if (f.sortColumn) {
      const colName = f.sortColumn;
      const t = columnTypes[colName] || 'categorical';
      const key = (m) => {
        const agg = sortAgg && sortAgg.get(m);
        if (!agg) return null;
        if (t === 'numeric') return agg.count ? (agg.sum / agg.count) : null;
        if (t === 'temporal') return agg.max != null ? agg.max : null;
        return agg.last || null;
      };
      labels.sort((a,b) => {
        const ka = key(a), kb = key(b);
        if (ka == null && kb == null) return a.localeCompare(b);
        if (ka == null) return 1;
        if (kb == null) return -1;
        if (t === 'numeric' || t === 'temporal') {
          return ((ka - kb) || 0) * (f.sortDir === 'desc' ? -1 : 1);
        }
        const cmp = String(ka).localeCompare(String(kb));
        return (f.sortDir === 'desc') ? -cmp : cmp;
      });
    } else {
      labels.sort();
    }
    const values = labels.map((m) => yByModel.get(m));
    const limits = computeControlLimits(values);
    const metaLookup = {};
    labels.forEach((m) => {
      const meta = groups.get(m).meta;
      metaLookup[m] = {
        date: Array.from(meta.dates),
        line: Array.from(meta.lines),
        model: Array.from(meta.models),
      };
    });
    return { kind, labels, values, limits, metaLookup };
  }

  if (kind === 'pareto') {
    const entries = Array.from(groups.entries()).map(([m,g]) => ({ model:m, ng:g.ngSum }));
    entries.sort((a,b)=>b.ng - a.ng);
    const total = entries.reduce((s,e)=>s+e.ng,0) || 1;
    let running = 0;
    const labels = entries.map(e=>e.model);
    const bar = entries.map(e=>e.ng);
    const cum = entries.map(e=>{ running += e.ng; return (running/total*100); });
    const datasets = [
      { type:'bar', label:'NG Parts', data: bar, backgroundColor:'#4F6BED' },
      { type:'line', label:'Cumulative %', data: cum, yAxisID:'y2', borderColor:'#F59E0B', backgroundColor:'#F59E0B', pointRadius:2, tension:0.1 }
    ];
    const metaLookup = {};
    labels.forEach((m) => {
      const meta = groups.get(m).meta;
      metaLookup[m] = {
        date: Array.from(meta.dates),
        line: Array.from(meta.lines),
        model: Array.from(meta.models),
      };
    });
    return { kind, labels, datasets, metaLookup };
  }

  if (kind === 'fc_avg_and_ppm') {
    let labels = Array.from(groups.keys());
    const avgByModel = new Map(labels.map((m)=>{ const g=groups.get(m); return [m, (g.boardSum? g.fcSum/g.boardSum : 0)]; }));
    const ppmByModel = new Map(labels.map((m)=>{ const g=groups.get(m); return [m, (g.partsSum? (g.fcSum/g.partsSum)*1e6 : 0)]; }));
    labels.sort((a,b)=> (ppmByModel.get(b) - ppmByModel.get(a)) );
    const avg = labels.map(m=> avgByModel.get(m));
    const ppm = labels.map(m=> ppmByModel.get(m));
    const datasets = [
      { type:'bar', label:'Avg FC/Board', data: avg, backgroundColor:'#4F6BED' },
      { type:'line', label:'FC PPM', data: ppm, yAxisID:'y2', borderColor:'#F59E0B', backgroundColor:'#F59E0B', pointRadius:2, tension:0.1 }
    ];
    const metaLookup = {};
    labels.forEach((m) => {
      const meta = groups.get(m).meta;
      metaLookup[m] = {
        date: Array.from(meta.dates),
        line: Array.from(meta.lines),
        model: Array.from(meta.models),
      };
    });
    return { kind, labels, datasets, metaLookup };
  }

  if (kind === 'scatter') {
    const pts = [];
    groups.forEach((g, m) => {
      const denom = g.partsSum || 0;
      const ngppm = denom ? (g.ngSum/denom)*1e6 : 0;
      const fcppm = denom ? (g.fcSum/denom)*1e6 : 0;
      pts.push({ x: ngppm, y: fcppm, model: m, date: Array.from(g.meta.dates), line: Array.from(g.meta.lines) });
    });
    return { kind, points: pts, metaLookup: {} };
  }

  if (kind === 'ts_ng_by_line') {
    const map = new Map();
    filteredByBoards.forEach((row)=>{
      const d = cols.date ? String(row[cols.date]).slice(0,10) : '';
      const line = cols.line ? String(row[cols.line]||'Unknown') : 'Unknown';
      if (!map.has(d)) map.set(d, new Map());
      const mline = map.get(d);
      if (!mline.has(line)) mline.set(line, { ng:0, parts:0, models:new Set() });
      const ag = mline.get(line);
      if (cols.ngParts) {
        ag.ng += Number(row[cols.ngParts]||0);
      } else if (cols.ngPPM && cols.totalParts) {
        const parts = Number(row[cols.totalParts]||0);
        const ppm = Number(row[cols.ngPPM]||0);
        if (isFinite(parts) && isFinite(ppm)) ag.ng += (parts*ppm)/1e6;
      }
      ag.parts += Number(row[cols.totalParts]||0);
      if (cols.model && row[cols.model] !== undefined) ag.models.add(String(row[cols.model]));
    });
    const dates = Array.from(map.keys()).sort();
    const lines = new Set(); dates.forEach(d=> map.get(d).forEach((_,line)=>lines.add(line)));
    const labels = dates;
    const metaLookup = {};
    const datasets = Array.from(lines).sort().map((line, i)=>{
      const hue=(i*53)%360; const color=`hsl(${hue} 75% 45%)`;
      const data = dates.map(d=>{ const r=map.get(d).get(line); const ppm = r && r.parts ? (r.ng/r.parts)*1e6 : null; const m = r ? { date:[d], line:[line], model:Array.from(r.models) } : { date:[d], line:[line], model:[] }; metaLookup[`${line}||${d}`] = m; return ppm; });
      return { label: line, data, borderColor: color, backgroundColor: color, fill:false, tension:0.1, pointRadius:2 };
    });
    return { kind, labels, datasets, metaLookup };
  }

  if (kind === 'ts_fc_vs_ng') {
    const byDate = new Map();
    filteredByBoards.forEach((row)=>{
      const d = cols.date ? String(row[cols.date]).slice(0,10) : '';
      const ag = byDate.get(d) || { ng:0, fc:0, parts:0, models:new Set(), lines:new Set() };
      if (cols.ngParts) {
        ag.ng += Number(row[cols.ngParts]||0);
      } else if (cols.ngPPM && cols.totalParts) {
        const parts = Number(row[cols.totalParts]||0);
        const ppm = Number(row[cols.ngPPM]||0);
        if (isFinite(parts) && isFinite(ppm)) ag.ng += (parts*ppm)/1e6;
      }
      ag.fc += Number(row[cols.fcParts]||0);
      ag.parts += Number(row[cols.totalParts]||0);
      if (cols.model && row[cols.model] !== undefined) ag.models.add(String(row[cols.model]));
      if (cols.line && row[cols.line] !== undefined) ag.lines.add(String(row[cols.line]));
      byDate.set(d, ag);
    });
    const labels = Array.from(byDate.keys()).sort();
    const metaLookup = {};
    const ng = labels.map(d=>{ const a=byDate.get(d); metaLookup[`NG PPM||${d}`]={ date:[d], line:Array.from(a.lines), model:Array.from(a.models) }; return a.parts? (a.ng/a.parts)*1e6 : 0; });
    const fc = labels.map(d=>{ const a=byDate.get(d); metaLookup[`FalseCall PPM||${d}`]={ date:[d], line:Array.from(a.lines), model:Array.from(a.models) }; return a.parts? (a.fc/a.parts)*1e6 : 0; });
    const datasets = [
      { label:'NG PPM', data: ng, borderColor:'#EF4444', backgroundColor:'#EF4444', fill:false, tension:0.1, pointRadius:2 },
      { label:'FalseCall PPM', data: fc, borderColor:'#3B82F6', backgroundColor:'#3B82F6', fill:false, tension:0.1, pointRadius:2 }
    ];
    return { kind, labels, datasets, metaLookup };
  }

  if (kind === 'ratio_fc_ng') {
    let labels = Array.from(groups.keys());
    const ratioByModel = new Map(labels.map((m)=>{ const g=groups.get(m); const r = g.ngSum? (g.fcSum/g.ngSum) : null; return [m, (r==null?0:r)]; }));
    labels.sort((a,b)=> (ratioByModel.get(b) - ratioByModel.get(a)) );
    const values = labels.map(m=> ratioByModel.get(m));
    const metaLookup = {};
    labels.forEach((m) => {
      const meta = groups.get(m).meta;
      metaLookup[m] = {
        date: Array.from(meta.dates),
        line: Array.from(meta.lines),
        model: Array.from(meta.models),
      };
    });
    return { kind, labels, values, metaLookup };
  }

  return { kind:'line-control', labels:[], values:[], limits:{ mean:0,ucl:0,lcl:0 }, metaLookup:{} };
}

// Infer simple types and populate encoding dropdowns
function inferTypes(rows) {
  if (!rows.length) return { cols: [], types: {} };
  const cols = Object.keys(rows[0]);
  const types = {};
  const sample = rows.slice(0, 50);
  cols.forEach((c) => {
    let n=0,t=0,b=0,total=0;
    sample.forEach((r) => {
      const v = r[c];
      if (v === null || v === undefined || v === '') return;
      total++;
      if (typeof v === 'number' || (!isNaN(v) && v !== '')) n++;
      if ((typeof v === 'string' && /\d{4}-\d{2}-\d{2}/.test(v)) || v instanceof Date) t++;
      if (typeof v === 'boolean' || v === 'true' || v === 'false') b++;
    });
    if (t/Math.max(1,total) > 0.6) types[c] = 'temporal';
    else if (n/Math.max(1,total) > 0.6) types[c] = 'numeric';
    else if (b/Math.max(1,total) > 0.6) types[c] = 'boolean';
    else types[c] = 'categorical';
  });
  return { cols, types };
}

function populateSelect(sel, items, withNone=false) {
  sel.innerHTML = '';
  if (withNone) {
    const opt = document.createElement('option'); opt.value=''; opt.textContent='(None)'; sel.appendChild(opt);
  }
  items.forEach((v) => { const o=document.createElement('option'); o.value=v; o.textContent=v; sel.appendChild(o); });
}

function updateXTypeUI() {
  const xCol = document.getElementById('x-column').value;
  const apply = () => {
    const t = columnTypes[xCol] || 'categorical';
    const hint = document.getElementById('x-type-hint');
    hint.textContent = `Type: ${t}`;
    document.getElementById('x-binning-wrap').style.display = (t === 'temporal') ? '' : 'none';
    document.getElementById('x-cat-sort-wrap').style.display = (t === 'categorical') ? '' : 'none';
  };

  if (!columnTypes[xCol]) {
    fetch('/moat')
      .then((res) => res.json())
      .then((rows) => {
        const { cols, types } = inferTypes(rows);
        allColumns = cols;
        columnTypes = types;
        apply();
      })
      .catch(apply);
  } else {
    apply();
  }
}

function initColumnsUI() {
  fetch('/moat')
    .then((res) => res.json())
    .then((rows) => {
      const { cols, types } = inferTypes(rows);
      allColumns = cols;
      columnTypes = types;
      const xSel = document.getElementById('x-column');
      const sSel = document.getElementById('series-column');
      // Prefer Report Date as default X
      const defaultX = cols.includes('Report Date') ? 'Report Date' : (cols[0] || '');
      populateSelect(xSel, cols, false);
      populateSelect(sSel, cols, true);
      xSel.value = defaultX;
      sSel.value = '';
      updateXTypeUI();
    })
    .catch(() => {
      // fallback to known columns
      const fallback = ['Report Date','Model Name'];
      const xSel = document.getElementById('x-column');
      const sSel = document.getElementById('series-column');
      populateSelect(xSel, fallback, false);
      populateSelect(sSel, fallback, true);
      xSel.value = 'Report Date';
      sSel.value = '';
      columnTypes = { 'Report Date': 'temporal', 'Model Name': 'categorical' };
      updateXTypeUI();
    });
}

function saveQuery() {
  const name = document.getElementById('save-name').value.trim();
  if (!name) { alert('Please provide a name for this chart.'); return; }
  const existing = savedQueriesCache.find((q) => q.name === name);
  if (existing && !confirm('Overwrite existing chart?')) return;
  const description = document.getElementById('chart-description').value.trim();
  const cfg = collectParamsForSave();
  const payload = {
    name,
    type: 'custom',
    description,
    params: cfg.params,
    start_date: cfg.start_date,
    end_date: cfg.end_date,
    value_source: cfg.value_source,
    x_column: cfg.x_column,
    y_agg: cfg.y_agg,
    chart_type: cfg.chart_type,
    line_color: cfg.line_color,
  };
  const method = existing ? 'PUT' : 'POST';
  fetch('/analysis/ppm/saved', { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
    .then((res) => { if (!res.ok) throw new Error('save failed'); return res.json(); })
    .then((rows) => {
      document.getElementById('save-name').value='';
      if (Array.isArray(rows) && rows[0]) {
        document.getElementById('chart-description').value = rows[0].description || description;
      }
      loadSavedQueries();
    })
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

function downloadExpandedChart() {
  const canvas = document.getElementById('ppmChartExpanded');
  if (!canvas) return;
  const link = document.createElement('a');
  const title = document.getElementById('chart-title').value || 'chart';
  link.download = `${title}.png`;
  link.href = canvas.toDataURL('image/png');
  link.click();
}

function downloadTableCSV() {
  const rows = document.querySelectorAll('#data-tbody tr');
  const lines = ['Date,Value'];
  rows.forEach((tr) => {
    const cols = tr.querySelectorAll('td');
    const date = cols[0]?.textContent ?? '';
    const val = cols[1]?.textContent ?? '';
    const esc = (s) => `"${String(s).replace(/"/g, '""')}"`;
    lines.push(`${esc(date)},${esc(val)}`);
  });
  const csv = lines.join('\n');
  const blob = new Blob([csv], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  const title = document.getElementById('chart-title').value || 'data';
  link.href = url;
  link.download = `${title}.csv`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function downloadPDF() {
  const meta = window.currentChartMeta;
  if (!meta) return;

  const off = document.createElement('canvas');
  off.width = 1000;
  off.height = 650;
  const ctx = off.getContext('2d');
  const plugins = (meta.options && meta.options.controlLimits) ? [controlLinesPlugin] : [];
  // eslint-disable-next-line no-undef
  const tmpChart = new Chart(ctx, {
    type: meta.type,
    data: { labels: meta.labels, datasets: meta.datasets },
    options: { ...meta.options, responsive: false, maintainAspectRatio: false, animation: false },
    plugins,
  });

  const imgData = off.toDataURL('image/png');

  // eslint-disable-next-line no-undef
  const { jsPDF } = window.jspdf;
  const doc = new jsPDF({ orientation: 'l', unit: 'pt', format: 'letter' });

  const title = document.getElementById('chart-title').value || 'Report';
  const start = document.getElementById('start-date').value || '';
  const end = document.getElementById('end-date').value || '';
  const range = start || end ? `${start} to ${end}` : '';

  const logo = new Image();
  logo.src = '/static/images/company-logo.png';
  await logo.decode();
  const pageW = doc.internal.pageSize.getWidth();
  doc.addImage(logo, 'PNG', (pageW - 40) / 2, 20, 40, 40);
  doc.setFontSize(18);
  doc.text(title, pageW / 2, 70, { align: 'center' });
  if (range) {
    doc.setFontSize(12);
    doc.text(range, pageW / 2, 80, { align: 'center' });
  }

  doc.addPage();
  const pageH = doc.internal.pageSize.getHeight();
  const margin = 36;
  const usableW = pageW - margin * 2;
  const usableH = pageH - margin * 2;
  const scale = Math.min(usableW / off.width, usableH / off.height);
  const renderW = off.width * scale;
  const renderH = off.height * scale;
  const x = (pageW - renderW) / 2;
  const y = (pageH - renderH) / 2;
  doc.addImage(imgData, 'PNG', x, y, renderW, renderH, undefined, 'FAST');

  doc.addPage();
  const labels = meta.labels || currentData.labels;
  const dataset = meta.datasets && meta.datasets[0] && Array.isArray(meta.datasets[0].data)
    ? meta.datasets[0].data
    : currentData.values || [];
  const body = [];
  (labels || []).forEach((lab, i) => {
    const val = dataset[i];
    body.push([lab, val?.toFixed ? val.toFixed(4) : val]);
  });
  // eslint-disable-next-line no-undef
  doc.autoTable({ head: [['Label', 'Value']], body });

  doc.save(`${title}.pdf`);

  tmpChart.destroy();
  off.remove();
}

document.addEventListener('DOMContentLoaded', () => {
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

  // Handle XLSX upload
  const uploadForm = document.getElementById('upload-form');
  if (uploadForm) {
    uploadForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const fileInput = document.getElementById('upload-xlsx');
      if (!fileInput.files.length) { alert('Please select a file.'); return; }
      const fd = new FormData();
      fd.append('file', fileInput.files[0]);
      try {
        const res = await fetch('/ppm_reports/upload', { method: 'POST', body: fd });
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

  // Default preset or use URL preset
  const url = new URL(window.location.href);
  const preset = url.searchParams.get('preset');
  setPreset(preset === 'fc_parts_per_total_parts' ? 'fc_parts_per_total_parts' : 'avg_fc_per_board');

  document.getElementById('run-chart').addEventListener('click', runChart);
  document.getElementById('save-chart').addEventListener('click', saveQuery);
  document.getElementById('saved-search').addEventListener('input', filterSavedList);
  document.getElementById('expand-chart').addEventListener('click', () => expandModal(true));
  document.getElementById('modal-close').addEventListener('click', () => expandModal(false));
  document.getElementById('download-pdf').addEventListener('click', downloadPDF);
  document.getElementById('copy-image').addEventListener('click', copyChartImage);
  document.getElementById('modal-download-chart').addEventListener('click', downloadExpandedChart);
  document.getElementById('modal-download-csv').addEventListener('click', downloadTableCSV);

  // Initialize filters and saved preset list
  initFiltersUI();
  loadSavedQueries();
  runChart();
});
