document.addEventListener('DOMContentLoaded', () => {
  const runBtn = document.getElementById('run-report');
  const downloadControls = document.getElementById('download-controls');
  const downloadBtn = document.getElementById('download-report');
  let reportData = null;
  let yieldChart, operatorChart, modelChart, fcVsNgChart, fcNgRatioChart;

  if (downloadControls) downloadControls.style.display = 'none';

  runBtn?.addEventListener('click', () => {
    const start = document.getElementById('start-date').value;
    const end = document.getElementById('end-date').value;
    if (!start || !end) {
      alert('Please select a date range.');
      return;
    }

    fetch(`/api/reports/integrated?start_date=${start}&end_date=${end}`)
      .then((res) => res.json())
      .then((data) => {
        reportData = { ...data, start, end };
        computeSummary(reportData);
        renderCharts(reportData);
        downloadControls.style.display = 'flex';
      })
      .catch(() => alert('Failed to run report.'));
  });

  downloadBtn?.addEventListener('click', () => {
    const fmt = document.getElementById('file-format').value;
    const start = document.getElementById('start-date').value;
    const end = document.getElementById('end-date').value;
    const params = new URLSearchParams({ format: fmt });
    if (start) params.append('start_date', start);
    if (end) params.append('end_date', end);
    window.location = `/reports/integrated/export?${params.toString()}`;
  });

  document.getElementById('email-report')?.addEventListener('click', () => {
    alert('Email sent (placeholder).');
  });

  function setDesc(id, lines) {
    const el = document.getElementById(id);
    if (!el) return;
    el.innerHTML = lines.map((line) => `<span>${line}</span>`).join('');
  }

  function computeSummary(data) {
    const yields = data.yieldData.yields || [];
    const dates = data.yieldData.dates || [];
    const avgYield =
      yields.reduce((a, b) => a + b, 0) / (yields.length || 1);
    let worstIdx = 0;
    yields.forEach((v, i) => {
      if (v < yields[worstIdx]) worstIdx = i;
    });
    const worstDay = {
      date: dates[worstIdx] || null,
      yield: yields[worstIdx] || 0,
    };
    let worstAsm = { assembly: null, yield: Infinity };
    Object.entries(data.yieldData.assemblyYields || {}).forEach(([k, v]) => {
      if (v < worstAsm.yield) worstAsm = { assembly: k, yield: v };
    });
    data.yieldSummary = { avg: avgYield, worstDay, worstAssembly: worstAsm };

    const ops = (data.operators || []).map((o) => ({
      ...o,
      rate: o.inspected ? (o.rejected / o.inspected) * 100 : 0,
    }));
    // Sort operators by inspected count so charts and exports share the order
    ops.sort((a, b) => b.inspected - a.inspected);
    data.operators = ops;
    const totalBoards = ops.reduce((a, o) => a + o.inspected, 0);
    const avgRate =
      ops.reduce((a, o) => a + o.rate, 0) / (ops.length || 1);
    let minOp = ops[0] || { name: '', rate: 0 };
    let maxOp = ops[0] || { name: '', rate: 0 };
    ops.forEach((o) => {
      if (o.rate < minOp.rate) minOp = o;
      if (o.rate > maxOp.rate) maxOp = o;
    });
    data.operatorSummary = { totalBoards, avgRate, min: minOp, max: maxOp };

    const avgFc =
      (data.models || []).reduce((a, m) => a + m.falseCalls, 0) /
      ((data.models || []).length || 1);
    const problemAssemblies = (data.models || []).filter(
      (m) => m.falseCalls > 20
    );
    const over20 = problemAssemblies.map((m) => m.name);
    data.modelSummary = { avgFalseCalls: avgFc, over20 };
    data.problemAssemblies = problemAssemblies;

    const fc = data.fcVsNgRate || {};
    const ngVals = fc.ngPpm || [];
    const fcVals = fc.fcPpm || [];
    const n = Math.min(ngVals.length, fcVals.length);
    let corr = 0;
    if (n > 1) {
      const avgNg = ngVals.reduce((a, b) => a + b, 0) / n;
      const avgFc = fcVals.reduce((a, b) => a + b, 0) / n;
      let num = 0;
      let denNg = 0;
      let denFc = 0;
      for (let i = 0; i < n; i += 1) {
        const x = ngVals[i] - avgNg;
        const y = fcVals[i] - avgFc;
        num += x * y;
        denNg += x * x;
        denFc += y * y;
      }
      const den = Math.sqrt(denNg * denFc);
      corr = den ? num / den : 0;
    }
    const fcTrend =
      fcVals.length > 1
        ? fcVals[0] < fcVals[fcVals.length - 1]
          ? 'increased'
          : 'decreased'
        : 'stable';
    data.fcVsNgSummary = { correlation: corr, fcTrend };

    const ratioData = data.fcNgRatio || {};
    const rModels = ratioData.models || [];
    const rFcParts = ratioData.fcParts || [];
    const rNgParts = ratioData.ngParts || [];
    const rRatios =
      ratioData.ratios ||
      rModels.map((_, i) => {
        const fcPart = rFcParts[i] || 0;
        const ngPart = rNgParts[i] || 0;
        return ngPart ? fcPart / ngPart : 0;
      });
    const combined = rModels
      .map((m, i) => ({
        model: m,
        fc: rFcParts[i] || 0,
        ng: rNgParts[i] || 0,
        ratio: rRatios[i],
      }))
      .filter((item) => item.ng > 2);
    combined.sort((a, b) => b.ratio - a.ratio);
    const top = combined.slice(0, 10);
    data.fcNgRatio = {
      models: top.map((t) => t.model),
      fcParts: top.map((t) => t.fc),
      ngParts: top.map((t) => t.ng),
      ratios: top.map((t) => t.ratio),
    };
    data.fcNgRatioSummary = { top: combined.slice(0, 3) };
  }

  function renderCharts(data) {
    const {
      yieldData,
      operators,
      models,
      yieldSummary,
      operatorSummary,
      modelSummary,
      problemAssemblies,
      fcVsNgRate,
      fcVsNgSummary,
      fcNgRatio,
      fcNgRatioSummary,
      start,
      end,
    } = data;

    yieldChart?.destroy();
    operatorChart?.destroy();
    modelChart?.destroy();
    fcVsNgChart?.destroy();
    fcNgRatioChart?.destroy();

    const yieldCanvas = document.getElementById('yieldTrendChart');
    yieldCanvas.width = 800;
    yieldCanvas.height = 400;
    const yieldCtx = yieldCanvas.getContext('2d');
    yieldChart = new Chart(yieldCtx, {
      type: 'line',
      data: {
        labels: yieldData.dates,
        datasets: [
          {
            label: 'Yield %',
            data: yieldData.yields,
            borderColor: 'blue',
            fill: false,
          },
        ],
      },
    });
    const yd = yieldSummary || {};
    setDesc('yieldTrendDesc', [
      `<strong>Date range:</strong> ${start} - ${end}`,
      `<strong>Average yield:</strong> ${yd.avg?.toFixed(2) ?? '0.00'}%`,
      `<strong>Lowest yield date:</strong> ${
        yd.worstDay?.date || 'N/A'
      } (${yd.worstDay?.yield?.toFixed(2) ?? '0.00'}%)`,
      `<strong>Worst assembly:</strong> ${
        yd.worstAssembly?.assembly || 'N/A'
      } (${yd.worstAssembly?.yield?.toFixed(2) ?? '0.00'}%)`,
    ]);

    const yTable = document.getElementById('yieldTrendTable');
    const yTbody = yTable.querySelector('tbody');
    yTbody.innerHTML = '';
    (yieldData.dates || []).forEach((d, i) => {
      const tr = document.createElement('tr');
      const dateTd = document.createElement('td');
      dateTd.textContent = d;
      const yieldTd = document.createElement('td');
      yieldTd.textContent = (yieldData.yields[i] ?? 0).toFixed(2);
      tr.appendChild(dateTd);
      tr.appendChild(yieldTd);
      yTbody.appendChild(tr);
    });
    yTable.style.display = (yieldData.dates || []).length ? 'table' : 'none';

    const operatorCanvas = document.getElementById('operatorRejectChart');
    operatorCanvas.width = 800;
    operatorCanvas.height = 400;
    const operatorCtx = operatorCanvas.getContext('2d');
    const accepted = operators.map((o) => o.inspected - o.rejected);
    const rejected = operators.map((o) => o.rejected);
    operatorChart = new Chart(operatorCtx, {
      type: 'bar',
      data: {
        labels: operators.map((o) => o.name),
        datasets: [
          { label: 'Accepted', data: accepted, backgroundColor: 'green' },
          { label: 'Rejected', data: rejected, backgroundColor: 'red' },
        ],
      },
      options: {
        scales: {
          x: { stacked: true },
          y: { stacked: true },
        },
      },
    });
    const os = operatorSummary || {};
    setDesc('operatorRejectDesc', [
      `<strong>Date range:</strong> ${start} - ${end}`,
      `<strong>Total boards:</strong> ${os.totalBoards ?? 0}`,
      `<strong>Average reject rate:</strong> ${
        os.avgRate?.toFixed(2) ?? '0.00'
      }%`,
      `<strong>Min reject rate:</strong> ${
        os.min?.name || 'N/A'
      } (${os.min?.rate?.toFixed(2) ?? '0.00'}%)`,
      `<strong>Max reject rate:</strong> ${
        os.max?.name || 'N/A'
      } (${os.max?.rate?.toFixed(2) ?? '0.00'}%)`,
    ]);

    const oTable = document.getElementById('operatorRejectTable');
    const oTbody = oTable.querySelector('tbody');
    oTbody.innerHTML = '';
    (operators || []).forEach((op) => {
      const tr = document.createElement('tr');
      const nameTd = document.createElement('td');
      nameTd.textContent = op.name;
      const inspTd = document.createElement('td');
      inspTd.textContent = op.inspected;
      const rejTd = document.createElement('td');
      rejTd.textContent = op.rejected;
      const rateTd = document.createElement('td');
      rateTd.textContent = `${op.rate?.toFixed(2) ?? '0.00'}%`;
      tr.appendChild(nameTd);
      tr.appendChild(inspTd);
      tr.appendChild(rejTd);
      tr.appendChild(rateTd);
      oTbody.appendChild(tr);
    });
    oTable.style.display = (operators || []).length ? 'table' : 'none';

    const modelCanvas = document.getElementById('modelFalseCallsChart');
    modelCanvas.width = 800;
    modelCanvas.height = 400;
    const modelCtx = modelCanvas.getContext('2d');

    // Calculate control limits for false calls by model
    const falseCalls = models.map((m) => m.falseCalls);
    const mean =
      falseCalls.reduce((sum, v) => sum + v, 0) / (falseCalls.length || 1);
    const stdDev = Math.sqrt(
      falseCalls.reduce((sum, v) => sum + Math.pow(v - mean, 2), 0) /
        (falseCalls.length || 1)
    );
    const upperCL = mean + 3 * stdDev;
    const lowerCL = Math.max(mean - 3 * stdDev, 0);

    modelChart = new Chart(modelCtx, {
      type: 'line',
      data: {
        labels: models.map((m) => m.name),
        datasets: [
          {
            label: 'False Calls',
            data: falseCalls,
            borderColor: 'orange',
            backgroundColor: 'orange',
            tension: 0,
            fill: false,
          },
          {
            label: 'Mean',
            data: Array(falseCalls.length).fill(mean),
            borderColor: 'blue',
            borderDash: [5, 5],
            pointRadius: 0,
            fill: false,
          },
          {
            label: '+3σ',
            data: Array(falseCalls.length).fill(upperCL),
            borderColor: 'green',
            borderDash: [5, 5],
            pointRadius: 0,
            fill: false,
          },
          {
            label: '-3σ',
            data: Array(falseCalls.length).fill(lowerCL),
            borderColor: 'red',
            borderDash: [5, 5],
            pointRadius: 0,
            fill: false,
          },
        ],
      },
      options: {
        scales: {
          x: {
            ticks: { display: false },
            grid: { display: false },
          },
        },
      },
    });
    const ms = modelSummary || {};
    setDesc('modelFalseCallsDesc', [
      `<strong>Date range:</strong> ${start} - ${end}`,
      `<strong>Average false calls/board:</strong> ${
        ms.avgFalseCalls?.toFixed(2) ?? '0.00'
      }`,
      'Line chart shows mean and ±3σ control limits; models outside may need review.',
      `<strong>Problem assemblies (>20 false calls/board):</strong> ${
        ms.over20?.join(', ') || 'None'
      }`,
    ]);

    const table = document.getElementById('problem-assemblies');
    const tbody = table.querySelector('tbody');
    tbody.innerHTML = '';
    (problemAssemblies || []).forEach((m) => {
      const tr = document.createElement('tr');
      const nameTd = document.createElement('td');
      nameTd.textContent = m.name;
      const fcTd = document.createElement('td');
      fcTd.textContent = m.falseCalls;
      tr.appendChild(nameTd);
      tr.appendChild(fcTd);
      tbody.appendChild(tr);
    });
    table.style.display = (problemAssemblies || []).length ? 'table' : 'none';

    const fcCanvas = document.getElementById('fcVsNgRateChart');
    fcCanvas.width = 800;
    fcCanvas.height = 400;
    const fcCtx = fcCanvas.getContext('2d');
    fcVsNgChart = new Chart(fcCtx, {
      type: 'line',
      data: {
        labels: fcVsNgRate?.dates || [],
        datasets: [
          {
            label: 'NG PPM',
            data: fcVsNgRate?.ngPpm || [],
            borderColor: 'red',
            fill: false,
          },
          {
            label: 'FalseCall PPM',
            data: fcVsNgRate?.fcPpm || [],
            borderColor: 'blue',
            fill: false,
          },
        ],
      },
    });
    const fr = fcVsNgSummary || {};
    setDesc('fcVsNgDesc', [
      `<strong>Date range:</strong> ${start} - ${end}`,
      `<strong>Correlation (FC vs NG):</strong> ${
        fr.correlation?.toFixed(2) ?? '0.00'
      }`,
      `<strong>False call rate has</strong> ${fr.fcTrend} over period`,
    ]);

    const fcTable = document.getElementById('fcVsNgRateTable');
    const fcTbody = fcTable.querySelector('tbody');
    fcTbody.innerHTML = '';
    (fcVsNgRate?.dates || []).forEach((d, i) => {
      const tr = document.createElement('tr');
      const dateTd = document.createElement('td');
      dateTd.textContent = d;
      const ngTd = document.createElement('td');
      ngTd.textContent = (fcVsNgRate?.ngPpm[i] ?? 0).toFixed(2);
      const fcTd = document.createElement('td');
      fcTd.textContent = (fcVsNgRate?.fcPpm[i] ?? 0).toFixed(2);
      tr.appendChild(dateTd);
      tr.appendChild(ngTd);
      tr.appendChild(fcTd);
      fcTbody.appendChild(tr);
    });
    fcTable.style.display = (fcVsNgRate?.dates || []).length ? 'table' : 'none';

    const ratioCanvas = document.getElementById('fcNgRatioChart');
    ratioCanvas.width = 800;
    ratioCanvas.height = 400;
    const ratioCtx = ratioCanvas.getContext('2d');
    fcNgRatioChart = new Chart(ratioCtx, {
      type: 'bar',
      data: {
        labels: fcNgRatio?.models || [],
        datasets: [
          {
            label: 'FC/NG Ratio',
            data: fcNgRatio?.ratios || [],
            backgroundColor: 'teal',
          },
        ],
      },
    });
    const nr = fcNgRatioSummary || {};
    setDesc('fcNgRatioDesc', [
      `<strong>Date range:</strong> ${start} - ${end}`,
      `<strong>Top ratios:</strong> ${(nr.top || [])
        .map((m) => `${m.name} (${m.ratio.toFixed(2)})`)
        .join(', ') || 'None'}`,
    ]);

    const ratioTable = document.getElementById('fcNgRatioTable');
    const ratioTbody = ratioTable.querySelector('tbody');
    ratioTbody.innerHTML = '';
    (fcNgRatio?.models || []).forEach((m, i) => {
      const tr = document.createElement('tr');
      const modelTd = document.createElement('td');
      modelTd.textContent = m;
      const fcTd = document.createElement('td');
      fcTd.textContent = (fcNgRatio.fcParts?.[i] ?? 0).toFixed(2);
      const ngTd = document.createElement('td');
      ngTd.textContent = (fcNgRatio.ngParts?.[i] ?? 0).toFixed(2);
      const ratioTd = document.createElement('td');
      ratioTd.textContent = (fcNgRatio.ratios?.[i] ?? 0).toFixed(2);
      tr.append(modelTd, fcTd, ngTd, ratioTd);
      ratioTbody.appendChild(tr);
    });
    ratioTable.style.display = (fcNgRatio?.models || []).length ? 'table' : 'none';
  }
});

