/* global Chart */

function color(i) {
  const hue = (i * 53) % 360;
  return {
    stroke: `hsl(${hue} 75% 45%)`,
    fill: `hsl(${hue} 75% 65% / 0.25)`,
    solid: `hsl(${hue} 75% 55%)`,
  };
}

function renderEscapePareto(group) {
  fetch(`/analysis/aoi/grades/escape_pareto?group=${encodeURIComponent(group)}`)
    .then((r) => r.json())
    .then((res) => {
      const items = res.items || [];
      const labels = items.map((d) => d.key);
      const bars = items.map((d) => d.fi_rej);
      const cum = items.map((d) => Math.round((d.cum_share || 0) * 1000) / 10);
      const rate = items.map((d) => d.escape_rate_per_1k);
      const ctx = document.getElementById('escapePareto').getContext('2d');
      if (window._escapePareto) window._escapePareto.destroy();
      window._escapePareto = new Chart(ctx, {
        type: 'bar',
        data: {
          labels,
          datasets: [
            { type: 'bar', label: 'FI rejects', data: bars, yAxisID: 'y', backgroundColor: 'hsl(0 70% 55% / 0.6)' },
            { type: 'line', label: 'Cumulative %', data: cum, yAxisID: 'y1', borderColor: '#0077ff', tension: 0.2 },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: { mode: 'index', intersect: false },
          scales: {
            y: { beginAtZero: true, title: { display: true, text: 'FI rejects' } },
            y1: { beginAtZero: true, max: 100, position: 'right', grid: { drawOnChartArea: false }, ticks: { callback: (v) => `${v}%` }, title: { display: true, text: 'Cumulative %' } },
          },
          plugins: {
            tooltip: {
              callbacks: {
                footer: (items) => {
                  const i = items[0].dataIndex;
                  return `escape_rate_per_1k: ${rate[i].toFixed ? rate[i].toFixed(1) : rate[i]}`;
                },
              },
            },
            legend: { display: true },
          },
        },
      });
    });
}

function renderGapRisk() {
  fetch('/analysis/aoi/grades/gap_risk')
    .then((r) => r.json())
    .then((res) => {
      const labels = res.labels || [];
      const hist = res.histogram || [];
      const share = (res.fi_share || []).map((x) => Math.round(x * 1000) / 10);
      const ctx = document.getElementById('gapRisk').getContext('2d');
      if (window._gapRisk) window._gapRisk.destroy();
      window._gapRisk = new Chart(ctx, {
        type: 'bar',
        data: { labels, datasets: [ { label: 'Count', data: hist, backgroundColor: 'hsl(210 70% 55% / 0.6)' }, { type: 'line', label: 'FI Share %', data: share, yAxisID: 'y1', borderColor: '#ff9900', tension: 0.2 } ] },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: { mode: 'index', intersect: false },
          scales: {
            y: { beginAtZero: true, title: { display: true, text: 'Count' } },
            y1: { beginAtZero: true, max: 100, position: 'right', grid: { drawOnChartArea: false }, ticks: { callback: (v) => `${v}%` }, title: { display: true, text: 'FI Share %' } },
          },
          plugins: { legend: { display: true } },
        },
      });
    });
}

function renderLearningCurves() {
  fetch('/analysis/aoi/grades/learning_curves')
    .then((r) => r.json())
    .then((res) => {
      const labels = new Set();
      const ops = Object.keys(res);
      ops.forEach((op) => res[op].dates.forEach((d) => labels.add(d)));
      const sortedLabels = Array.from(labels).sort();
      const datasets = ops.map((op, i) => {
        const c = color(i);
        const idx = new Map(res[op].dates.map((d, j) => [d, j]));
        const data = sortedLabels.map((d) => (idx.has(d) ? res[op].rates[idx.get(d)] : null));
        const med = sortedLabels.map((d) => (idx.has(d) ? res[op].rolling_median[idx.get(d)] : null));
        return [
          { label: `${op} rate`, data, borderColor: c.stroke, backgroundColor: c.fill, tension: 0.2, spanGaps: true },
          { label: `${op} median`, data: med, borderColor: c.solid, borderDash: [4,2], tension: 0.2, spanGaps: true },
        ];
      }).flat();
      const ctx = document.getElementById('learningCurves').getContext('2d');
      if (window._learning) window._learning.destroy();
      window._learning = new Chart(ctx, { type: 'line', data: { labels: sortedLabels, datasets }, options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: true } }, scales: { y: { beginAtZero: true, title: { display: true, text: 'Escapes per 1k' } } } } });
    });
}

document.addEventListener('DOMContentLoaded', () => {
  const grp = document.getElementById('paretoGroup');
  if (grp) {
    grp.addEventListener('change', () => renderEscapePareto(grp.value));
    renderEscapePareto(grp.value || 'model');
  }
  if (document.getElementById('gapRisk')) renderGapRisk();
  if (document.getElementById('learningCurves')) renderLearningCurves();
  // Additional sections
  if (document.getElementById('smtThHeatmap')) renderSmtThHeatmap();
  if (document.getElementById('weekdayHeatmap')) renderShiftEffect();
  if (document.getElementById('programTrend')) renderProgramTrend();
  if (document.getElementById('adjustedRanking')) renderAdjustedRanking();
});

function renderProgramTrend() {
  const el = document.getElementById('programTrend');
  if (!el) return;
  fetch('/analysis/aoi/grades/program_trend')
    .then((r) => r.json())
    .then((res) => {
      const labels = res.months || [];
      const datasets = (res.datasets || []).map((d, i) => {
        const c = color(i);
        return { label: d.label, data: d.data, borderColor: c.stroke, backgroundColor: c.fill, tension: 0.2 };
      });
      if (window._programTrend) window._programTrend.destroy();
      window._programTrend = new Chart(el.getContext('2d'), {
        type: 'line', data: { labels, datasets }, options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: true } }, scales: { y: { title: { display: true, text: 'Escapes per 1k' } } } },
      });
    });
}

function renderAdjustedRanking() {
  const el = document.getElementById('adjustedRanking');
  if (!el) return;
  fetch('/analysis/aoi/grades/adjusted_operator_ranking')
    .then((r) => r.json())
    .then((res) => {
      const eff = res.effects || [];
      const labels = eff.map((e) => e.operator);
      const vals = eff.map((e) => e.effect);
      const lower = eff.map((e) => e.lower);
      const upper = eff.map((e) => e.upper);
      if (window._adjRank) window._adjRank.destroy();
      window._adjRank = new Chart(el.getContext('2d'), {
        type: 'bar',
        data: { labels, datasets: [ { label: 'Adjusted effect (escapes per 1k)', data: vals, backgroundColor: 'hsl(210 70% 55% / 0.6)' } ] },
        options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false, plugins: { legend: { display: true }, tooltip: { callbacks: { afterLabel: (ctx) => { const i = ctx.dataIndex; return `CI: [${lower[i].toFixed(1)}, ${upper[i].toFixed(1)}]`; } } } }, scales: { x: { title: { display: true, text: 'Effect (lower is better)' } } } },
      });
    });
}

function renderSmtThHeatmap() {
  const host = document.getElementById('smtThHeatmap');
  if (!host) return;
  fetch('/analysis/aoi/grades/smt_th_heatmap')
    .then((r) => r.json())
    .then((res) => {
      const stations = res.stations || [];
      const parts = res.part_types || [];
      const matrix = res.matrix || [];
      const max = Math.max(1, ...matrix.flat().map((v) => Number(v) || 0));
      let html = '<table class="data-table"><thead><tr><th>Station\\Part</th>' + parts.map((p) => `<th>${p}</th>`).join('') + '</tr></thead><tbody>';
      stations.forEach((s, i) => {
        html += `<tr><td><b>${s}</b></td>`;
        (matrix[i] || []).forEach((v) => {
          const val = Number(v) || 0;
          const intensity = Math.min(1, val / max);
          const bg = `hsl(${Math.round((1-intensity)*120)} 70% 60% / 0.9)`;
          html += `<td style="background:${bg}; text-align:right;">${val.toFixed ? val.toFixed(1) : val}</td>`;
        });
        html += '</tr>';
      });
      html += '</tbody></table>';
      host.innerHTML = html;
    });
}

function renderShiftEffect() {
  const host = document.getElementById('weekdayHeatmap');
  const box = document.getElementById('shiftBox');
  if (!host || !box) return;
  fetch('/analysis/aoi/grades/shift_effect')
    .then((r) => r.json())
    .then((res) => {
      const shifts = res.shifts || [];
      const stats = res.shift_stats || {};
      const labels = shifts;
      const q1 = labels.map((s) => (stats[s]?.q1 ?? 0));
      const med = labels.map((s) => (stats[s]?.median ?? 0));
      const q3 = labels.map((s) => (stats[s]?.q3 ?? 0));
      const ctx = box.getContext('2d');
      if (window._shiftBox) window._shiftBox.destroy();
      window._shiftBox = new Chart(ctx, {
        type: 'bar',
        data: { labels, datasets: [
          { label: 'Q1', data: q1, backgroundColor: 'hsl(210 70% 75% / 0.6)' },
          { label: 'Median', data: med, backgroundColor: 'hsl(210 70% 55% / 0.6)' },
          { label: 'Q3', data: q3, backgroundColor: 'hsl(210 70% 35% / 0.6)' },
        ] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: true } }, scales: { y: { beginAtZero: true, title: { display: true, text: 'Escapes per 1k' } } } },
      });

      const wd = res.weekday_labels || [];
      const cols = res.weekday_shifts || [];
      const mat = res.weekday_heat || [];
      const max = Math.max(1, ...mat.flat().map((v) => Number(v) || 0));
      let html = '<table class="data-table"><thead><tr><th>Weekday\\Shift</th>' + cols.map((c) => `<th>${c}</th>`).join('') + '</tr></thead><tbody>';
      wd.forEach((d, i) => {
        html += `<tr><td><b>${d}</b></td>`;
        (mat[i] || []).forEach((v) => {
          const val = Number(v) || 0;
          const intensity = Math.min(1, val / max);
          const bg = `hsl(${Math.round((1-intensity)*120)} 70% 60% / 0.9)`;
          html += `<td style="background:${bg}; text-align:right;">${val.toFixed ? val.toFixed(1) : val}</td>`;
        });
        html += '</tr>';
      });
      html += '</tbody></table>';
      host.innerHTML = html;
    });
}

function renderCustomerYield() {
  const el = document.getElementById('customerYield');
  if (!el) return;
  fetch('/analysis/aoi/grades/customer_yield')
    .then((r) => r.json())
    .then((res) => {
      const labels = res.labels || [];
      const yields = res.yields || [];
      if (window._customerYield) window._customerYield.destroy();
      window._customerYield = new Chart(el.getContext('2d'), {
        type: 'bar',
        data: { labels, datasets: [ { label: 'True Yield %', data: yields, backgroundColor: 'hsl(140 70% 50% / 0.6)' } ] },
        options: { responsive: true, maintainAspectRatio: false, scales: { y: { beginAtZero: true, max: 100, ticks: { callback: (v) => v + '%' } } } },
      });
    });
}

document.addEventListener('DOMContentLoaded', () => {
  if (document.getElementById('customerYield')) renderCustomerYield();
});
