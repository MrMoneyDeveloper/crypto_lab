/* static/dashboard.js
 *
 *  – Fetches /api/data/<coin> JSON
 *  – Plots historical price (solid) + 24 h forecast (dashed)
 *  – Auto-updates once per minute
 */

(() => {
  const ctx = document.getElementById("chart").getContext("2d");
  const select = document.getElementById("coinSelect");
  let chart;                 // Chart.js instance
  const REFRESH_MS = 60_000; // 1 minute

  /* turn two parallel arrays into Chart.js-compatible dataset */
  function buildDataset(label, data, style = {}) {
    return {
      label,
      data,
      borderWidth: 2,
      spanGaps: true,
      tension: 0.3,
      ...style,
    };
  }

  async function load(coin) {
    try {
      const res = await fetch(`/api/data/${coin}`);
      if (!res.ok) throw new Error(await res.text());
      const json = await res.json();

      const histTs = json.history.ts;       // array of ISO strings
      const histPx = json.history.price;    // floats
      const fcTs   = json.forecast.ts;      // array
      const fcPx   = json.forecast.price;   // floats

      // Merge labels: history + forecast
      const labels = histTs.concat(fcTs);

      // To align datasets, pad forecast with nulls up to history length-1
      const fcAligned = new Array(histPx.length - 1).fill(null).concat(fcPx);

      const datasets = [
        buildDataset(`${coin} price`, histPx, { borderColor: "#0d6efd" }),
        buildDataset("24 h forecast", fcAligned, {
          borderDash: [6, 4],
          borderColor: "#6c757d",
          pointRadius: 0,
        }),
      ];

      if (chart) {
        chart.data.labels = labels;
        chart.data.datasets = datasets;
        chart.update();
      } else {
        chart = new Chart(ctx, {
          type: "line",
          data: { labels, datasets },
          options: {
            responsive: true,
            interaction: { mode: "index", intersect: false },
            scales: {
              x: { display: true, ticks: { maxRotation: 45, minRotation: 45 } },
              y: { title: { display: true, text: `Price (${json.currency ?? "usd"})` } },
            },
          },
        });
      }
    } catch (err) {
      console.error("Dashboard load error:", err);
    }
  }

  /* initial draw */
  load(select.value);

  /* dropdown handler */
  select.addEventListener("change", () => load(select.value));

  /* periodic refresh */
  setInterval(() => load(select.value), REFRESH_MS);
})();
