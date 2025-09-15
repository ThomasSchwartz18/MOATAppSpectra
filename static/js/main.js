function renderLinePreview({ endpoint, canvasId, infoId, onClickHref }) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;

  if (onClickHref) {
    canvas.style.cursor = 'pointer';
    canvas.addEventListener('click', () => {
      window.location.href = onClickHref;
    });
  }

  if (!endpoint) return;

  fetch(endpoint)
    .then((res) => {
      if (!res.ok) {
        throw new Error(`Request failed with status ${res.status}`);
      }
      return res.json();
    })
    .then((data) => {
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      const isFalseCallPreview = Array.isArray(data.avg_false_calls);
      const labels =
        data.labels || (isFalseCallPreview ? data.models : undefined) || [];
      const values =
        data.values ||
        (isFalseCallPreview
          ? data.avg_false_calls
          : data.yields || data.avg_false_calls) || [];

      const chartConfig = {
        type: 'line',
        data: {
          labels,
          datasets: [
            {
              data: values,
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
          scales: isFalseCallPreview
            ? {
                x: { display: false, grid: { display: false }, ticks: { display: false } },
                y: { beginAtZero: true, display: false, grid: { display: false }, ticks: { display: false } },
              }
            : {
                x: {
                  display: true,
                  title: { display: true, text: 'Date' },
                  grid: { display: false },
                  ticks: { display: true },
                  border: { display: true },
                },
                y: {
                  beginAtZero: true,
                  display: true,
                  title: { display: true, text: 'Yield' },
                  grid: { display: false },
                  ticks: { display: true },
                  border: { display: true },
                },
              },
        },
        plugins: [],
      };

      if (isFalseCallPreview) {
        chartConfig.plugins.push({
          id: 'hLines',
          afterDraw(chart) {
            const {
              ctx: chartCtx,
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

            chartCtx.save();
            chartCtx.setLineDash([4, 4]);
            lines.forEach((line) => {
              const y = yScale.getPixelForValue(line.value);
              if (y >= top && y <= bottom) {
                chartCtx.beginPath();
                chartCtx.moveTo(left, y);
                chartCtx.lineTo(right, y);
                chartCtx.strokeStyle = line.color;
                chartCtx.lineWidth = 1;
                chartCtx.stroke();
              }
            });
            chartCtx.restore();
          },
        });
      }

      // eslint-disable-next-line no-undef
      new Chart(ctx, chartConfig);

      if (infoId) {
        const infoEl = document.getElementById(infoId);
        if (infoEl) {
          if (isFalseCallPreview) {
            const avg = Number.isFinite(Number(data.overall_avg))
              ? Number(data.overall_avg).toFixed(2)
              : '0';
            const start = data.start_date || 'N/A';
            const end = data.end_date || 'N/A';
            infoEl.textContent = `${start} to ${end} | Avg False Calls: ${avg}`;
          } else if (data && Object.prototype.hasOwnProperty.call(data, 'avg_yield')) {
            const avgYield = Number.isFinite(Number(data.avg_yield))
              ? Number(data.avg_yield).toFixed(1)
              : '0';
            const start = data.start_date || 'N/A';
            const end = data.end_date || 'N/A';
            infoEl.textContent = `${start} to ${end} | Avg Yield: ${avgYield}%`;
          }
        }
      }
    })
    .catch((err) => {
      // eslint-disable-next-line no-console
      console.error('Failed to load preview', err);
    });
}

document.addEventListener('DOMContentLoaded', () => {
  const previewConfigs = [
    {
      endpoint: '/moat_preview',
      canvasId: 'ppmAnalysisPreview',
      onClickHref: '/analysis/ppm?preset=avg_false_calls_per_assembly',
    },
    {
      endpoint: '/aoi_preview',
      canvasId: 'aoiFiAnalysisPreview',
      onClickHref: '/analysis/aoi/grades/view',
    },
    {
      endpoint: '/daily_reports_preview',
      canvasId: 'dailyReportsPreview',
      onClickHref: '/reports/aoi_daily',
    },
    {
      endpoint: '/forecast_preview',
      canvasId: 'assemblyForecastPreview',
      onClickHref: '/tools/assembly-forecast',
    },
  ];

  previewConfigs.forEach((config) => {
    renderLinePreview(config);
  });

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
