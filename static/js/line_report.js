import { downloadFile } from './utils.js';

document.addEventListener('DOMContentLoaded', () => {
  const runBtn = document.getElementById('run-line-report');
  const downloadControls = document.getElementById('download-controls');
  const downloadBtn = document.getElementById('download-report');
  const previewDetails = document.getElementById('line-preview');
  let reportData = null;
  let yieldChart = null;
  let falseCallChart = null;
  let qualityChart = null;
  let trendChart = null;

  if (downloadControls) downloadControls.style.display = 'none';

  const numberFormatter = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 });
  const decimalFormatter = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 });

  const sections = {
    metrics: document.getElementById('line-metrics-section'),
    assembly: document.getElementById('assembly-comparison-section'),
    crossLine: document.getElementById('cross-line-section'),
    trend: document.getElementById('trend-section'),
    benchmarking: document.getElementById('benchmarking-section'),
  };

  function showSection(section) {
    if (section) section.hidden = false;
    if (previewDetails && !previewDetails.open) {
      previewDetails.open = true;
    }
  }

  function hideSections() {
    Object.values(sections).forEach((section) => {
      if (section) {
        section.hidden = true;
        const tables = section.querySelectorAll('tbody');
        tables.forEach((tbody) => {
          tbody.innerHTML = '';
        });
        const containers = section.querySelectorAll('[data-clear-on-run]');
        containers.forEach((el) => {
          el.innerHTML = '';
        });
      }
    });
  }

  function fmtPercent(value) {
    if (value === null || value === undefined) return '--';
    return `${decimalFormatter.format(value)}%`;
  }

  function fmtNumber(value, fractionDigits = 2) {
    if (value === null || value === undefined) return '--';
    const formatter = fractionDigits === 0
      ? numberFormatter
      : new Intl.NumberFormat('en-US', { maximumFractionDigits: fractionDigits });
    return formatter.format(value);
  }

  function getDefectsPerBoard(metric = {}) {
    return metric.defectsPerBoard
      ?? metric.confirmedDefectsPerBoard
      ?? metric.defectPerBoard
      ?? null;
  }

  function getDefectsPerBoardDelta(metric = {}) {
    return metric.defectsPerBoardDelta
      ?? metric.confirmedDefectsPerBoardDelta
      ?? metric.defectPerBoardDelta
      ?? null;
  }

  function clearCharts() {
    yieldChart?.destroy();
    falseCallChart?.destroy();
    qualityChart?.destroy();
    trendChart?.destroy();
  }

  function renderLineMetrics(metrics) {
    const tbody = document.getElementById('line-metrics-body');
    if (!tbody) return;
    tbody.innerHTML = '';
    metrics.forEach((metric) => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${metric.line}</td>
        <td>${fmtPercent(metric.windowYield ?? metric.yield)}</td>
        <td>${fmtPercent(metric.partYield)}</td>
        <td>${fmtNumber(metric.confirmedDefects, 0)}</td>
        <td>${fmtNumber(getDefectsPerBoard(metric))}</td>
        <td>${fmtNumber(metric.falseCallsPerBoard)}</td>
        <td>${fmtNumber(metric.falseCallDpm)}</td>
        <td>${fmtNumber(metric.defectDpm)}</td>
        <td>${fmtNumber(metric.boardsPerDay)}</td>
        <td>${fmtNumber(metric.totalWindows)}</td>
        <td>${fmtNumber(metric.totalParts)}</td>
      `;
      tbody.appendChild(tr);
    });
    showSection(sections.metrics);
  }

  function renderLineCharts(metrics) {
    const yieldCtx = document.getElementById('lineYieldChart')?.getContext('2d');
    const falseCallCtx = document.getElementById('lineFalseCallChart')?.getContext('2d');
    const qualityCtx = document.getElementById('lineQualityChart')?.getContext('2d');
    clearCharts();
    if (yieldCtx) {
      yieldChart = new Chart(yieldCtx, {
        type: 'bar',
        data: {
          labels: metrics.map((m) => m.line),
          datasets: [
            {
              label: 'Window Yield %',
              data: metrics.map((m) => m.windowYield ?? m.yield ?? null),
              backgroundColor: '#0ea5e9',
            },
          ],
        },
        options: {
          responsive: true,
          plugins: { legend: { display: false } },
          scales: { y: { title: { display: true, text: 'Window Yield %' } } },
        },
      });
    }
    if (falseCallCtx) {
      falseCallChart = new Chart(falseCallCtx, {
        type: 'bar',
        data: {
          labels: metrics.map((m) => m.line),
          datasets: [
            {
              label: 'False Calls / Board',
              data: metrics.map((m) => m.falseCallsPerBoard),
              backgroundColor: '#f97316',
            },
          ],
        },
        options: {
          responsive: true,
          plugins: { legend: { display: false } },
          scales: { y: { title: { display: true, text: 'False Calls / Board' } } },
        },
      });
    }
    if (qualityCtx) {
      qualityChart = new Chart(qualityCtx, {
        type: 'bar',
        data: {
          labels: metrics.map((m) => m.line),
          datasets: [
            {
              label: 'False Call DPM',
              data: metrics.map((m) => m.falseCallDpm ?? null),
              backgroundColor: '#1d4ed8',
            },
            {
              label: 'Defect DPM',
              data: metrics.map((m) => m.defectDpm ?? null),
              backgroundColor: '#059669',
            },
          ],
        },
        options: {
          responsive: true,
          scales: {
            y: {
              title: { display: true, text: 'Defects per Million' },
            },
          },
        },
      });
    }
  }

  function renderAssemblyComparisons(comparisons) {
    const container = document.getElementById('assembly-comparisons');
    if (!container) return;
    container.innerHTML = '';
    if (!comparisons.length) {
      container.innerHTML = '<p class="empty-state">No multi-line assemblies available for comparison.</p>';
      showSection(sections.assembly);
      return;
    }

    comparisons.forEach((item) => {
      const details = document.createElement('details');
      details.className = 'comparison-block';
      const summary = document.createElement('summary');
      summary.textContent = item.assembly;
      details.appendChild(summary);

      const table = document.createElement('table');
      table.className = 'data-table';
      table.innerHTML = `
        <thead>
          <tr>
            <th>Line</th>
            <th>Window Yield %</th>
            <th>Defects / Board</th>
            <th>False Calls / Board</th>
            <th>False Call DPM</th>
            <th>Defect DPM</th>
          </tr>
        </thead>
        <tbody></tbody>
      `;
      const tbody = table.querySelector('tbody');
      Object.entries(item.lines).forEach(([line, metrics]) => {
        const row = document.createElement('tr');
        row.innerHTML = `
          <td>${line}</td>
          <td>${fmtPercent(metrics.windowYield ?? metrics.yield)}</td>
          <td>${fmtNumber(getDefectsPerBoard(metrics))}</td>
          <td>${fmtNumber(metrics.falseCallsPerBoard)}</td>
          <td>${fmtNumber(metrics.falseCallDpm)}</td>
          <td>${fmtNumber(metrics.defectDpm)}</td>
        `;
        tbody.appendChild(row);
      });
      details.appendChild(table);

      const defectMixWrap = document.createElement('div');
      defectMixWrap.className = 'defect-mix';
      Object.entries(item.lines).forEach(([line, metrics]) => {
        const mix = metrics.defectMix || {};
        const entries = Object.entries(mix);
        if (!entries.length) return;
        const block = document.createElement('div');
        block.className = 'defect-mix-card';
        const list = entries
          .sort((a, b) => b[1] - a[1])
          .slice(0, 5)
          .map(([defect, share]) => `<li>${defect}: ${fmtPercent(share * 100)}</li>`) // share already 0-1? we convert to percentage.
          .join('');
        block.innerHTML = `
          <h4>${line} Defect Mix</h4>
          <ul>${list || '<li>No defect data</li>'}</ul>
        `;
        defectMixWrap.appendChild(block);
      });
      if (defectMixWrap.children.length) {
        details.appendChild(defectMixWrap);
      }

      container.appendChild(details);
    });
    if (comparisons.length) showSection(sections.assembly);
  }

  function renderCrossLine(data) {
    const container = document.getElementById('cross-line-content');
    if (!container) return;
    container.innerHTML = '';

    const varianceBlock = document.createElement('div');
    varianceBlock.className = 'variance-grid';
    const yieldList = (data.yieldVariance || []).slice(0, 5)
      .map((item) => `<li>${item.assembly}: σ = ${fmtNumber(item.stddev)}</li>`)
      .join('') || '<li>No multi-line assemblies</li>';
    const fcList = (data.falseCallVariance || []).slice(0, 5)
      .map((item) => `<li>${item.assembly}: σ = ${fmtNumber(item.stddev)}</li>`)
      .join('') || '<li>No multi-line assemblies</li>';
    varianceBlock.innerHTML = `
      <div>
        <h4>Yield Variance (Top)</h4>
        <ul>${yieldList}</ul>
      </div>
      <div>
        <h4>False Call Variance (Top)</h4>
        <ul>${fcList}</ul>
      </div>
    `;
    container.appendChild(varianceBlock);

    const similarity = data.defectSimilarity || [];
    if (similarity.length) {
      const simWrapper = document.createElement('div');
      simWrapper.className = 'similarity-grid';
      similarity.slice(0, 5).forEach((entry) => {
        const card = document.createElement('div');
        card.className = 'similarity-card';
        const pairs = entry.pairs
          .map((pair) => `${pair.lines.join(' vs ')} → ${fmtNumber(pair.similarity * 100)}%`)
          .join('<br>');
        card.innerHTML = `<h4>${entry.assembly}</h4><p>${pairs}</p>`;
        simWrapper.appendChild(card);
      });
      container.appendChild(simWrapper);
    }

    if (container.children.length) showSection(sections.crossLine);
  }

  function renderTrends(lineTrends, insights) {
    const trendCtx = document.getElementById('lineTrendChart')?.getContext('2d');
    const labels = lineTrends.length ? lineTrends[0].entries.map((entry) => entry.date) : [];
    const datasets = lineTrends.map((trend) => ({
      label: trend.line,
      data: trend.entries.map((entry) => entry.windowYield ?? entry.yield ?? null),
      spanGaps: true,
      tension: 0.15,
    }));
    if (trendCtx && datasets.length) {
      trendChart = new Chart(trendCtx, {
        type: 'line',
        data: { labels, datasets },
        options: {
          responsive: true,
          plugins: { legend: { position: 'bottom' } },
          scales: {
            y: { title: { display: true, text: 'Window Yield %' } },
          },
        },
      });
    }

    const container = document.getElementById('trend-insights');
    if (!container) return;
    container.innerHTML = '';
    container.setAttribute('data-clear-on-run', '');

    const drift = insights.lineDrift || [];
    if (drift.length) {
      const list = document.createElement('ul');
      list.className = 'insight-list';
      drift.slice(0, 5).forEach((item) => {
        const li = document.createElement('li');
        li.textContent = `${item.line}: ${fmtPercent(item.start)} → ${fmtPercent(item.end)} (Δ ${fmtPercent(item.change)})`;
        list.appendChild(li);
      });
      container.appendChild(Object.assign(document.createElement('h4'), { textContent: 'Line Yield Drift' }));
      container.appendChild(list);
    }

    const learning = insights.assemblyLearning || [];
    if (learning.length) {
      const list = document.createElement('ul');
      list.className = 'insight-list';
      learning.slice(0, 5).forEach((item) => {
        const li = document.createElement('li');
        li.textContent = `${item.assembly} on ${item.line}: ${fmtPercent(item.start[1])} → ${fmtPercent(item.end[1])}`;
        list.appendChild(li);
      });
      container.appendChild(Object.assign(document.createElement('h4'), { textContent: 'Assembly Learning Curves' }));
      container.appendChild(list);
    }

    if (container.children.length) showSection(sections.trend);
  }

  function renderBenchmarking(benchmarking, averages) {
    const container = document.getElementById('benchmarking-content');
    if (!container) return;
    container.innerHTML = '';
    container.setAttribute('data-clear-on-run', '');

    const kpiList = document.createElement('ul');
    kpiList.className = 'insight-list';
    if (benchmarking.bestYield) {
      const bestYieldValue = benchmarking.bestYield.windowYield ?? benchmarking.bestYield.partYield ?? benchmarking.bestYield.yield;
      kpiList.innerHTML += `<li>Best Window Yield: ${benchmarking.bestYield.line} (${fmtPercent(bestYieldValue)})</li>`;
    }
    if (benchmarking.lowestFalseCalls) {
      kpiList.innerHTML += `<li>Lowest False Calls / Board: ${benchmarking.lowestFalseCalls.line} (${fmtNumber(benchmarking.lowestFalseCalls.falseCallsPerBoard)})</li>`;
    }
    if (benchmarking.mostConsistent) {
      kpiList.innerHTML += `<li>Most Consistent: ${benchmarking.mostConsistent.line} (σ ${fmtNumber(benchmarking.mostConsistent.stddev)})</li>`;
    }
    container.appendChild(kpiList);

    const table = document.createElement('table');
    table.className = 'data-table';
    table.innerHTML = `
      <thead>
        <tr>
          <th>Line</th>
          <th>Window Yield Δ</th>
          <th>Defects / Board Δ</th>
          <th>False Call Δ (/board)</th>
          <th>False Call DPM Δ</th>
          <th>Defect DPM Δ</th>
        </tr>
      </thead>
      <tbody></tbody>
    `;
    const tbody = table.querySelector('tbody');
    (benchmarking.lineVsCompany || []).forEach((entry) => {
      const row = document.createElement('tr');
      row.innerHTML = `
        <td>${entry.line}</td>
        <td>${fmtNumber(entry.windowYieldDelta)}</td>
        <td>${fmtNumber(getDefectsPerBoardDelta(entry))}</td>
        <td>${fmtNumber(entry.falseCallDelta)}</td>
        <td>${fmtNumber(entry.falseCallDpmDelta)}</td>
        <td>${fmtNumber(entry.defectDpmDelta)}</td>
      `;
      tbody.appendChild(row);
    });
    container.appendChild(table);

    const avg = document.createElement('p');
    avg.className = 'kpi-summary';
    avg.textContent = `Company averages — Window Yield: ${fmtPercent(averages.windowYield ?? averages.yield)}, Defects / Board: ${fmtNumber(averages.defectsPerBoard)}, False Calls / Board: ${fmtNumber(averages.falseCallsPerBoard)}, False Call DPM: ${fmtNumber(averages.falseCallDpm)}, Defect DPM: ${fmtNumber(averages.defectDpm)}`;
    container.appendChild(avg);

    showSection(sections.benchmarking);
  }

  runBtn?.addEventListener('click', async () => {
    const start = document.getElementById('start-date').value;
    const end = document.getElementById('end-date').value;
    if (!start || !end) {
      alert('Please select a date range.');
      return;
    }
    hideSections();
    clearCharts();
    if (previewDetails) {
      previewDetails.open = false;
    }
    try {
      const response = await fetch(`/api/reports/line?start_date=${start}&end_date=${end}`);
      if (!response.ok) throw new Error('Failed to run report');
      reportData = await response.json();
      renderLineMetrics(reportData.lineMetrics || []);
      renderLineCharts(reportData.lineMetrics || []);
      renderAssemblyComparisons(reportData.assemblyComparisons || []);
      renderCrossLine(reportData.crossLine || {});
      renderTrends(reportData.lineTrends || [], reportData.trendInsights || {});
      renderBenchmarking(reportData.benchmarking || {}, reportData.companyAverages || {});
      if (downloadControls) downloadControls.style.display = 'flex';
    } catch (err) {
      console.error(err);
      alert('Failed to run line report.');
    }
  });

  downloadBtn?.addEventListener('click', async () => {
    const fmtSelect = document.getElementById('file-format');
    const selectedFormat = fmtSelect?.value;
    const fmt = ['pdf', 'html'].includes(selectedFormat) ? selectedFormat : 'pdf';
    const start = document.getElementById('start-date').value;
    const end = document.getElementById('end-date').value;
    const params = new URLSearchParams({ format: fmt });
    if (start) params.append('start_date', start);
    if (end) params.append('end_date', end);
    await downloadFile(`/reports/line/export?${params.toString()}`, {
      buttonId: 'download-report',
      spinnerId: 'download-spinner',
    });
  });
});
