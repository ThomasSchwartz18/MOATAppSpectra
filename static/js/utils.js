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
