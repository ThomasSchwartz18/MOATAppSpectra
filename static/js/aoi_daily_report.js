import { downloadFile } from './utils.js';

document.addEventListener('DOMContentLoaded', () => {
  const runBtn = document.getElementById('run-report');
  const downloadBtn = document.getElementById('download-report');
  const downloadControls = document.getElementById('download-controls');
  const previewBox = document.getElementById('preview-data');

  if (downloadControls) downloadControls.style.display = 'none';

  runBtn?.addEventListener('click', () => {
    const date = document.getElementById('report-date').value;
    if (!date) {
      alert('Please select a date.');
      return;
    }
    const params = new URLSearchParams({ date });
    fetch(`/api/reports/aoi_daily?${params.toString()}`)
      .then((res) => res.json())
      .then((data) => {
        if (previewBox) previewBox.textContent = JSON.stringify(data, null, 2);
        if (downloadControls) downloadControls.style.display = 'flex';
      })
      .catch(() => alert('Failed to run report.'));
  });

  downloadBtn?.addEventListener('click', async () => {
    const fmt = document.getElementById('file-format').value;
    const date = document.getElementById('report-date').value;
    if (!date) {
      alert('Please select a date.');
      return;
    }
    const params = new URLSearchParams({ format: fmt, date, show_cover: 'true' });
    await downloadFile(`/reports/aoi_daily/export?${params.toString()}`, {
      buttonId: 'download-report',
    });
  });
});
