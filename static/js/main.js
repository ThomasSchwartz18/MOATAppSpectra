function renderPreview(endpoint, canvasId, infoId) {
  fetch(endpoint)
    .then((res) => res.json())
    .then((data) => {
      const ctx = document.getElementById(canvasId).getContext('2d');
      const hLinePlugin = {
        id: 'hLines',
        afterDraw(chart) {
          const {
            ctx,
            chartArea: { left, right, top, bottom },
            scales,
          } = chart;
          const yScale = scales.y;
          if (!yScale) return;
          const lines = [
            { value: 20, color: 'red' },
            { value: 10, color: 'gold' },
            { value: 5, color: 'green' },
          ];
          ctx.save();
          ctx.setLineDash([4, 4]);
          lines.forEach((ln) => {
            const y = yScale.getPixelForValue(ln.value);
            if (y >= top && y <= bottom) {
              ctx.beginPath();
              ctx.moveTo(left, y);
              ctx.lineTo(right, y);
              ctx.strokeStyle = ln.color;
              ctx.lineWidth = 1;
              ctx.stroke();
            }
          });
          ctx.restore();
        },
      };

      // eslint-disable-next-line no-undef
      const chart = new Chart(ctx, {
        type: 'line',
        data: {
          labels: data.models,
          datasets: [
            {
              data: data.avg_false_calls,
              borderColor: '#000',
              backgroundColor: '#000',
              pointBackgroundColor: '#000',
              pointBorderColor: '#000',
              pointRadius: 3,
              fill: false,
              tension: 0,
              borderWidth: 2,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: { enabled: false },
          },
          elements: {
            line: { borderWidth: 2 },
          },
          scales: {
            x: { display: false, grid: { display: false }, ticks: { display: false } },
            y: { beginAtZero: true, display: false, grid: { display: false }, ticks: { display: false } },
          },
        },
        plugins: [hLinePlugin],
      });

      const infoEl = document.getElementById(infoId);
      if (infoEl) {
        const avg = data.overall_avg ? data.overall_avg.toFixed(2) : '0';
        infoEl.textContent = `${data.start_date} to ${data.end_date} | Avg False Calls: ${avg}`;
      }

      // Navigate to PPM Analysis if "many" points are above red (20)
      const overRed = (data.avg_false_calls || []).filter((v) => Number(v) > 20).length;
      const canvas = document.getElementById(canvasId);
      if (canvas) {
        canvas.style.cursor = overRed >= 3 ? 'pointer' : 'default';
        canvas.addEventListener('click', () => {
          if (overRed >= 3) {
            window.location.href = '/analysis/ppm?preset=avg_false_calls_per_assembly';
          }
        });
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
  // Auto-hide navbar on scroll down; reveal on scroll up
  const nav = document.querySelector('.navbar');
  if (nav) {
    let lastY = window.scrollY;
    window.addEventListener('scroll', () => {
      const y = window.scrollY;
      const goingDown = y > lastY;
      if (goingDown && y > 10) nav.classList.add('navbar--hidden');
      else nav.classList.remove('navbar--hidden');
      lastY = y;
    }, { passive: true });
  }
});
