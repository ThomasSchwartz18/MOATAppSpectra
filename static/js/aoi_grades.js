document.addEventListener('DOMContentLoaded', () => {
  fetch('/analysis/aoi/grades')
    .then((r) => r.json())
    .then((data) => {
      const labels = Object.keys(data);
      const grades = labels.map((op) => (data[op].grade * 100).toFixed(1));
      const inspected = labels.map((op) => data[op].inspected);
      const missed = labels.map((op) => data[op].weighted_missed);

      const ctx = document.getElementById('gradesChart').getContext('2d');
      // eslint-disable-next-line no-undef
      new Chart(ctx, {
        type: 'bar',
        data: {
          labels,
          datasets: [{ label: 'Grade %', data: grades, backgroundColor: 'rgba(54,162,235,0.6)' }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: { y: { beginAtZero: true, max: 100, ticks: { callback: (v) => v + '%' } } },
        },
      });

      const tbody = document.querySelector('#gradesTable tbody');
      labels.forEach((op, i) => {
        const tr = document.createElement('tr');
        const inspectedVal = inspected[i];
        const missedVal = missed[i];
        tr.innerHTML = `<td>${op}</td><td>${inspectedVal}</td><td>${missedVal.toFixed ? missedVal.toFixed(1) : missedVal}</td><td>${grades[i]}%</td>`;
        tbody.appendChild(tr);
      });
    });
});
