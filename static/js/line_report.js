import { downloadFile } from './utils.js';

document.addEventListener('DOMContentLoaded', () => {
  const runBtn = document.getElementById('run-line-report');
  const downloadControls = document.getElementById('download-controls');
  const downloadBtn = document.getElementById('download-report');
  const previewDetails = document.getElementById('line-preview');
  const previewData = document.getElementById('line-preview-data');
  let reportData = null;

  if (downloadControls) downloadControls.style.display = 'none';

  function clearPreview() {
    if (previewData) {
      previewData.textContent = '';
    }
    if (previewDetails) {
      previewDetails.open = false;
    }
  }

  runBtn?.addEventListener('click', async () => {
    const start = document.getElementById('start-date').value;
    const end = document.getElementById('end-date').value;
    if (!start || !end) {
      alert('Please select a date range.');
      return;
    }

    clearPreview();

    try {
      const response = await fetch(`/api/reports/line?start_date=${start}&end_date=${end}`);
      if (!response.ok) throw new Error('Failed to run report');
      reportData = await response.json();

      if (previewData) {
        previewData.textContent = JSON.stringify(reportData, null, 2);
      }
      if (previewDetails) {
        previewDetails.open = true;
      }
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
