export function showSpinner(btnId) {
  const spinner = document.getElementById('download-spinner');
  const btn = document.getElementById(btnId);
  if (spinner) spinner.hidden = false;
  if (btn) btn.disabled = true;
}

export function hideSpinner(btnId) {
  const spinner = document.getElementById('download-spinner');
  const btn = document.getElementById(btnId);
  if (spinner) spinner.hidden = true;
  if (btn) btn.disabled = false;
}
