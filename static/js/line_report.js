import { setupReportRunner } from './report_runner.js';

document.addEventListener('DOMContentLoaded', () => {
  const selectors = {
    previewContainer: 'preview',
    previewData: 'preview-data',
  };
  const previewDetails = document.getElementById(selectors.previewContainer);
  const previewData = document.getElementById(selectors.previewData);
  let reportData = null;

  function clearPreview() {
    if (previewData) {
      previewData.textContent = '';
    }
    if (previewDetails) {
      previewDetails.open = false;
    }
  }

  const collectParams = () => {
    const start = document.getElementById('start-date')?.value || '';
    const end = document.getElementById('end-date')?.value || '';
    const format = document.getElementById('file-format')?.value || 'pdf';
    return { start, end, format };
  };

  const validateParams = ({ start, end }) => {
    if (!start || !end) {
      return 'Please select a date range.';
    }
    return true;
  };

  setupReportRunner({
    collectParams,
    validateParams,
    beforePreview: () => {
      clearPreview();
    },
    buildPreviewUrl: ({ start, end }) => {
      const params = new URLSearchParams({ start_date: start, end_date: end });
      return `/api/reports/line?${params.toString()}`;
    },
    onPreviewSuccess: (data) => {
      reportData = data;
      if (previewData) {
        previewData.textContent = JSON.stringify(reportData, null, 2);
      }
      if (previewDetails) {
        previewDetails.open = true;
      }
    },
    onPreviewError: () => alert('Failed to run line report.'),
    buildDownloadUrl: ({ start, end, format }) => {
      const selected = (format || '').toLowerCase();
      const fmt = ['pdf', 'html'].includes(selected) ? selected : 'pdf';
      const params = new URLSearchParams({ format: fmt });
      if (start) params.append('start_date', start);
      if (end) params.append('end_date', end);
      return `/reports/line/export?${params.toString()}`;
    },
    downloadOptions: {
      spinnerId: 'download-spinner',
    },
  });
});
