import { setupReportRunner } from './report_runner.js';
import {
  configureReportFormatSelector,
  getPreferredReportFormat,
} from './utils.js';

document.addEventListener('DOMContentLoaded', () => {
  const previewBox = document.getElementById('preview-data');

  configureReportFormatSelector({ noteId: 'file-format-note' });

  const collectParams = () => {
    const date = document.getElementById('report-date')?.value || '';
    const format =
      document.getElementById('file-format')?.value || getPreferredReportFormat();
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
        format: format || getPreferredReportFormat(),
        date,
        show_cover: 'true',
      });
      return `/reports/aoi_daily/export?${params.toString()}`;
    },
  });
});
