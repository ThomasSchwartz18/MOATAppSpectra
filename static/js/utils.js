export function showSpinner(btnId, spinnerId = 'download-spinner') {
  const spinner = spinnerId ? document.getElementById(spinnerId) : null;
  const btn = btnId ? document.getElementById(btnId) : null;
  if (spinner) spinner.hidden = false;
  if (btn) btn.disabled = true;
}

export function hideSpinner(btnId, spinnerId = 'download-spinner') {
  const spinner = spinnerId ? document.getElementById(spinnerId) : null;
  const btn = btnId ? document.getElementById(btnId) : null;
  if (spinner) spinner.hidden = true;
  if (btn) btn.disabled = false;
}

export function isLikelyLinuxClient() {
  if (typeof navigator === 'undefined') {
    return true;
  }

  const platform = navigator?.platform || '';
  const userAgent = navigator?.userAgent || '';
  const combined = `${platform} ${userAgent}`.toLowerCase();

  return combined.includes('linux');
}

export function getPreferredReportFormat() {
  return isLikelyLinuxClient() ? 'pdf' : 'html';
}

export function configureReportFormatSelector({
  selectId = 'file-format',
  noteId,
  disablePdf = true,
} = {}) {
  const select = selectId ? document.getElementById(selectId) : null;
  if (!select) return;

  const noteEl = noteId ? document.getElementById(noteId) : null;
  const pdfOption = select.querySelector('option[value="pdf"]');
  const htmlOption = select.querySelector('option[value="html"]');
  const linuxClient = isLikelyLinuxClient();

  const message =
    'PDF exports are only available on Linux hosts configured with the required PDF dependencies.';

  if (linuxClient) {
    if (pdfOption) pdfOption.disabled = false;
    if (pdfOption) select.value = pdfOption.value;
    if (noteEl) noteEl.hidden = true;
    if (!noteEl) select.removeAttribute('title');
    return;
  }

  if (htmlOption) select.value = htmlOption.value;
  if (pdfOption && disablePdf) {
    pdfOption.disabled = true;
  }

  if (noteEl) {
    noteEl.textContent = message;
    noteEl.hidden = false;
  } else {
    select.title = message;
  }
}

function decodeFileName(disposition) {
  if (!disposition) return null;
  // RFC 5987 style: filename*=UTF-8''...
  const encodedMatch = /filename\*=UTF-8''([^;]+)/i.exec(disposition);
  if (encodedMatch && encodedMatch[1]) {
    try {
      return decodeURIComponent(encodedMatch[1]);
    } catch (err) {
      console.warn('Failed to decode RFC5987 filename', err);
    }
  }
  const quotedMatch = /filename="?([^";]+)"?/i.exec(disposition);
  if (quotedMatch && quotedMatch[1]) {
    return quotedMatch[1];
  }
  return null;
}

export async function downloadFile(url, { buttonId, spinnerId = 'download-spinner', filename } = {}) {
  showSpinner(buttonId, spinnerId);
  try {
    const response = await fetch(url, {
      method: 'GET',
      credentials: 'same-origin',
    });
    if (!response.ok) {
      throw new Error(`Download failed with status ${response.status}`);
    }
    const blob = await response.blob();
    let downloadName = filename;
    if (!downloadName) {
      downloadName = decodeFileName(response.headers.get('Content-Disposition'));
    }
    if (!downloadName) {
      const parsed = new URL(url, window.location.origin);
      const parts = parsed.pathname.split('/').filter(Boolean);
      downloadName = parts.length ? parts[parts.length - 1] : 'download';
    }
    const blobUrl = window.URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = blobUrl;
    anchor.download = downloadName;
    anchor.rel = 'noopener';
    anchor.style.display = 'none';
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.URL.revokeObjectURL(blobUrl);
    return true;
  } catch (err) {
    console.error('Download failed', err);
    alert('Failed to download file. Please try again.');
    return false;
  } finally {
    hideSpinner(buttonId, spinnerId);
  }
}
