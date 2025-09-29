import { setupReportRunner } from './report_runner.js';
import {
  configureReportFormatSelector,
  getPreferredReportFormat,
} from './utils.js';

document.addEventListener('DOMContentLoaded', () => {
  const selectors = {
    previewContainer: 'preview',
    previewData: 'preview-data',
  };
  configureReportFormatSelector({ noteId: 'file-format-note' });
  const previewDetails = document.getElementById(selectors.previewContainer);
  const previewData = document.getElementById(selectors.previewData);
  let reportData = null;

  function clearPreview() {
    if (previewData) {
      previewData.textContent = '';
      previewData.classList.remove('preview-message');
    }
    if (previewDetails) {
      previewDetails.open = false;
    }
  }

  function showPreviewMessage(message) {
    if (!previewData) return;
    previewData.textContent = message;
    previewData.classList.add('preview-message');
    if (previewDetails) {
      previewDetails.open = true;
    }
  }

  const collectParams = () => {
    const start = document.getElementById('start-date')?.value || '';
    const end = document.getElementById('end-date')?.value || '';
    const format =
      document.getElementById('file-format')?.value || getPreferredReportFormat();
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
        previewData.classList.remove('preview-message');
      }
      if (previewDetails) {
        previewDetails.open = true;
      }
    },
    onPreviewError: (err) => {
      reportData = null;
      const reason = err?.message
        ? `\nDetails: ${err.message}`
        : '';
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
      return `/reports/line/export?${params.toString()}`;
    },
    downloadOptions: {
      spinnerId: 'download-spinner',
    },
    showDownloadControlsOnValidation: true,
  });
});
