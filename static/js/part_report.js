import { setupReportRunner } from './report_runner.js';
import {
  configureReportFormatSelector,
  getPreferredReportFormat,
} from './utils.js';

let defectChart = null;
let falseCallChart = null;

function formatPercent(value) {
  return `${(value * 100).toFixed(1)}%`;
}

function resetCharts() {
  defectChart?.destroy();
  falseCallChart?.destroy();
  defectChart = null;
  falseCallChart = null;
}

function updateMetric(id, value, formatter = (v) => v) {
  const el = document.getElementById(id);
  if (el) {
    el.textContent = formatter(value);
  }
}

function renderDistributionTable(tableId, rows = []) {
  const table = document.getElementById(tableId);
  if (!table) return;
  const tbody = table.querySelector('tbody');
  if (!tbody) return;
  tbody.innerHTML = '';
  rows.slice(0, 10).forEach((row) => {
    const tr = document.createElement('tr');
    const labelCell = document.createElement('td');
    labelCell.textContent = row.label || 'Unknown';
    const countCell = document.createElement('td');
    countCell.textContent = row.count?.toLocaleString() || '0';
    const shareCell = document.createElement('td');
    shareCell.textContent = formatPercent(row.share || 0);
    tr.append(labelCell, countCell, shareCell);
    tbody.appendChild(tr);
  });
}

function renderBarChart(canvasId, rows = [], label) {
  const canvas = document.getElementById(canvasId);
  if (!canvas || !window.Chart) return null;
  const labels = rows.slice(0, 10).map((row) => row.label || 'Unknown');
  const values = rows.slice(0, 10).map((row) => row.count || 0);
  if (!labels.length) {
    return null;
  }
  const chart = new Chart(canvas.getContext('2d'), {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label,
          data: values,
          backgroundColor: '#0d9ba8',
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          ticks: {
            autoSkip: true,
            maxRotation: 0,
          },
        },
        y: {
          beginAtZero: true,
          ticks: {
            precision: 0,
          },
        },
      },
      plugins: {
        legend: {
          display: false,
        },
      },
    },
  });
  return chart;
}

function populatePreview(data) {
  const highlight = document.getElementById('part-report-highlight');
  if (highlight) {
    const insights = data?.insights?.highlights || [];
    highlight.textContent = insights[0] || '';
  }

  updateMetric('metric-total-records', data?.meta?.totalRecords || 0, (v) =>
    (v || 0).toLocaleString(),
  );
  updateMetric('metric-false-calls', data?.meta?.totalFalseCalls || 0, (v) =>
    (v || 0).toLocaleString(),
  );
  updateMetric(
    'metric-defects-per-board',
    data?.yieldReliability?.defectsPerBoard || 0,
    (v) => v.toFixed(2),
  );
  updateMetric('metric-unique-parts', data?.meta?.uniquePartNumbers || 0, (v) =>
    (v || 0).toLocaleString(),
  );

  const defectRows = data?.defectDistributions?.byDefectCode || [];
  renderDistributionTable('defectCodeTable', defectRows);
  const falseCallRows = data?.falseCallPatterns?.byPartNumber || [];
  renderDistributionTable('falseCallTable', falseCallRows);

  resetCharts();
  defectChart = renderBarChart('defectCodeChart', defectRows, 'Defects');
  falseCallChart = renderBarChart('falseCallChart', falseCallRows, 'False Calls');
}

document.addEventListener('DOMContentLoaded', () => {
  const previewDetails = document.getElementById('preview');
  const previewData = document.getElementById('preview-data');
  configureReportFormatSelector({ noteId: 'file-format-note' });

  function showPreviewMessage(message) {
    if (!previewData) return;
    previewData.textContent = message;
    previewData.classList.add('preview-message');
    if (previewDetails) previewDetails.open = true;
  }

  setupReportRunner({
    collectParams: () => {
      const start = document.getElementById('start-date')?.value || '';
      const end = document.getElementById('end-date')?.value || '';
      const format =
        document.getElementById('file-format')?.value || getPreferredReportFormat();
      return { start, end, format };
    },
    validateParams: ({ start, end }) => {
      if (!start || !end) {
        return 'Please select a date range.';
      }
      return true;
    },
    beforePreview: () => {
      resetCharts();
      if (previewData) {
        previewData.textContent = '';
        previewData.classList.remove('preview-message');
      }
      if (previewDetails) previewDetails.open = false;
    },
    buildPreviewUrl: ({ start, end }) => {
      const params = new URLSearchParams({ start_date: start, end_date: end });
      return `/api/reports/part?${params.toString()}`;
    },
    onPreviewSuccess: (data) => {
      if (previewData) {
        previewData.textContent = JSON.stringify(data, null, 2);
        previewData.classList.remove('preview-message');
      }
      if (previewDetails) previewDetails.open = true;
      populatePreview(data);
    },
    onPreviewError: (err) => {
      const reason = err?.message ? `\nDetails: ${err.message}` : '';
      showPreviewMessage(
        `We couldn't generate a preview for the selected dates, but you can still download the report.${reason}`,
      );
    },
    buildDownloadUrl: ({ start, end, format }) => {
      const selected = (format || '').toLowerCase();
      const preferred = getPreferredReportFormat();
      const fmt = ['pdf', 'html'].includes(selected) ? selected : preferred;
      const params = new URLSearchParams({ format: fmt });
      if (start) params.append('start_date', start);
      if (end) params.append('end_date', end);
      return `/reports/part/export?${params.toString()}`;
    },
    downloadOptions: {
      spinnerId: 'download-spinner',
    },
    showDownloadControlsOnValidation: true,
  });
});
