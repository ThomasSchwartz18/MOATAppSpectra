import { setupReportRunner } from './report_runner.js';

document.addEventListener('DOMContentLoaded', () => {
  const previewBox = document.getElementById('preview-data');

  const collectParams = () => {
    const date = document.getElementById('report-date')?.value || '';
    const format = document.getElementById('file-format')?.value || 'pdf';
    return { date, format };
  };

  const validateParams = ({ date }) => {
    if (!date) {
      return 'Please select a date.';
    }
    return true;
  };

  setupReportRunner({
    collectParams,
    validateParams,
    buildPreviewUrl: ({ date }) => {
      const params = new URLSearchParams({ date });
      return `/api/reports/aoi_daily?${params.toString()}`;
    },
    onPreviewSuccess: (data) => {
      if (previewBox) previewBox.textContent = JSON.stringify(data, null, 2);
    },
    onPreviewError: () => alert('Failed to run report.'),
    buildDownloadUrl: ({ date, format }) => {
      const params = new URLSearchParams({
        format: format || 'pdf',
        date,
        show_cover: 'true',
      });
      return `/reports/aoi_daily/export?${params.toString()}`;
    },
  });
});
