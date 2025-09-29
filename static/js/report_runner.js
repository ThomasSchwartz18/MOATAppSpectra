import { downloadFile } from './utils.js';

function alertValidationResult(result) {
  if (typeof result === 'string' && result) {
    alert(result);
  }
}

export function setupReportRunner({
  runButtonId = 'run-report',
  downloadButtonId = 'download-report',
  downloadControlsId = 'download-controls',
  collectParams = () => ({}),
  validateParams,
  beforePreview,
  buildPreviewUrl,
  fetchPreview = (url) => fetch(url),
  onPreviewSuccess,
  onPreviewError,
  buildDownloadUrl,
  downloadOptions = {},
  showDownloadControlsOnValidation = false,
} = {}) {
  const runBtn = document.getElementById(runButtonId);
  const downloadBtn = document.getElementById(downloadButtonId);
  const downloadControls = downloadControlsId
    ? document.getElementById(downloadControlsId)
    : null;

  if (downloadControls) downloadControls.style.display = 'none';

  async function handleRun(event) {
    event?.preventDefault?.();
    const params = collectParams();
    const validationResult = validateParams
      ? validateParams(params, { isDownload: false })
      : true;
    if (validationResult !== true) {
      alertValidationResult(validationResult);
      return;
    }

    if (downloadControls && showDownloadControlsOnValidation) {
      downloadControls.style.display = 'flex';
    }

    beforePreview?.(params);

    const previewUrl =
      typeof buildPreviewUrl === 'function'
        ? buildPreviewUrl(params)
        : buildPreviewUrl;

    if (!previewUrl) {
      console.warn('setupReportRunner: preview URL was not provided.');
      if (downloadControls && !showDownloadControlsOnValidation) {
        downloadControls.style.display = 'none';
      }
      return;
    }

    try {
      const response = await fetchPreview(previewUrl, params);
      if (!response.ok) {
        throw new Error(`Preview request failed with status ${response.status}`);
      }
      const data = await response.json();
      if (onPreviewSuccess) {
        await onPreviewSuccess(data, params);
      }
      if (downloadControls) downloadControls.style.display = 'flex';
    } catch (err) {
      console.error(err);
      if (onPreviewError) {
        onPreviewError(err, params);
      } else {
        alert('Failed to run report.');
      }
      if (downloadControls && !showDownloadControlsOnValidation) {
        downloadControls.style.display = 'none';
      }
    }
  }

  runBtn?.addEventListener('click', handleRun);

  async function handleDownload(event) {
    event?.preventDefault?.();
    const params = collectParams();
    const validationResult = validateParams
      ? validateParams(params, { isDownload: true })
      : true;
    if (validationResult !== true) {
      alertValidationResult(validationResult);
      return;
    }

    const downloadUrl =
      typeof buildDownloadUrl === 'function'
        ? buildDownloadUrl(params)
        : buildDownloadUrl;

    if (!downloadUrl) {
      console.warn('setupReportRunner: download URL was not provided.');
      return;
    }

    await downloadFile(downloadUrl, {
      buttonId: downloadButtonId,
      ...downloadOptions,
    });
  }

  downloadBtn?.addEventListener('click', handleDownload);

  return {
    run: handleRun,
    download: handleDownload,
  };
}
