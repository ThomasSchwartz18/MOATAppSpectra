function renderPreview(endpoint, canvasId, infoId) {
  fetch(endpoint)
    .then((res) => res.json())
    .then((data) => {
      const ctx = document.getElementById(canvasId).getContext('2d');
      // eslint-disable-next-line no-undef
      new Chart(ctx, {
        type: 'line',
        data: {
          labels: data.models,
          datasets: [
            {
              label: 'Avg False Calls',
              data: data.avg_false_calls,
              borderColor: 'rgba(75, 192, 192, 1)',
              backgroundColor: 'rgba(75, 192, 192, 0.2)',
              fill: false,
              tension: 0,
            },
          ],
        },
        options: {
          responsive: true,
          scales: {
            y: { beginAtZero: true },
          },
        },
      });

      const infoEl = document.getElementById(infoId);
      if (infoEl) {
        const avg = data.overall_avg ? data.overall_avg.toFixed(2) : '0';
        infoEl.textContent = `${data.start_date} to ${data.end_date} | Avg False Calls: ${avg}`;
      }
    })
    .catch((err) => {
      // eslint-disable-next-line no-console
      console.error('Failed to load preview', err);
    });
}

document.addEventListener('DOMContentLoaded', () => {
  if (document.getElementById('moatChart')) {
    renderPreview('/moat_preview', 'moatChart', 'moat-info');
  }
});

