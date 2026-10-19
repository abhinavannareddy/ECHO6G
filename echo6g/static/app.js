const form = document.querySelector("#scenario-form");
const compareButton = form.querySelector("button[type=submit]");
const errorBanner = document.querySelector("#error-banner");
const recommendationCard = document.querySelector("#recommendation-card");
const recommendationTitle = document.querySelector("#recommendation-title");
const recommendationReason = document.querySelector("#recommendation-reason");
const recommendationPolicy = document.querySelector("#recommendation-policy");
const recommendationResource = document.querySelector("#recommendation-resource");
const recommendationFit = document.querySelector("#recommendation-fit");
const recommendationBadge = document.querySelector("#recommendation-badge");
const optionsBody = document.querySelector("#options-body");
const exportButton = document.querySelector("#export-button");
const channel = document.querySelector("#channel_quality");
const channelOutput = document.querySelector("#channel-output");

const labels = {
  energy_saver: ["Energy saver", "Lowest provisioning baseline"],
  fixed_middle: ["Fixed middle", "Fixed provisioning baseline"],
  performance_first: ["Performance first", "Maximum provisioning baseline"],
  echo_adaptive: ["ECHO adaptive", "Chooses a level from earlier examples"],
};
let latestResult = null;

channel.addEventListener("input", () => { channelOutput.value = Number(channel.value).toFixed(2); });

function clearError() {
  errorBanner.hidden = true;
  errorBanner.textContent = "";
}

function showError(message) {
  errorBanner.textContent = message;
  errorBanner.hidden = false;
  errorBanner.scrollIntoView({ behavior: "smooth", block: "center" });
}

function formatPercent(value) { return `${(value * 100).toFixed(1)}%`; }
function formatNumber(value, digits = 2) { return Number(value).toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits }); }

function render(data) {
  latestResult = data;
  const fitCount = data.options.filter((option) => option.sla_met).length;
  const isFit = data.recommendation.status === "meets_sla";
  recommendationCard.setAttribute("aria-busy", "false");
  recommendationTitle.textContent = isFit ? "Requirements met in the model" : "No tested option meets all targets";
  recommendationReason.textContent = data.recommendation.reason;
  recommendationPolicy.textContent = labels[data.recommendation.policy]?.[0] ?? data.recommendation.policy;
  recommendationResource.textContent = `Level ${data.recommendation.resource_level}`;
  recommendationFit.textContent = `${fitCount} of ${data.options.length}`;
  recommendationBadge.textContent = isFit ? "Model fit found" : "Review requirement gap";
  recommendationBadge.className = `recommendation-badge ${isFit ? "good" : "caution"}`;

  optionsBody.replaceChildren();
  for (const option of data.options) {
    const row = document.createElement("tr");
    const label = labels[option.policy_name] ?? [option.policy_name, option.description];
    const cells = [
      { className: "strategy-cell", content: [label[0], label[1]] },
      { content: [option.sla_met ? "Meets targets" : "Below target", option.sla_met ? "yes" : "no"] },
      { text: `${formatNumber(option.latency_ms)} ms` },
      { text: formatPercent(option.reliability) },
      { text: formatNumber(option.energy_units) },
    ];
    cells.forEach((cell, index) => {
      const td = document.createElement("td");
      if (index === 0) {
        td.className = cell.className;
        const strong = document.createElement("strong");
        strong.textContent = cell.content[0];
        const detail = document.createElement("span");
        detail.textContent = cell.content[1];
        td.append(strong, detail);
      } else if (index === 1) {
        const tag = document.createElement("span");
        tag.className = `fit-tag ${cell.content[1]}`;
        tag.textContent = cell.content[0];
        td.append(tag);
      } else {
        td.textContent = cell.text;
      }
      row.append(td);
    });
    optionsBody.append(row);
  }
  exportButton.disabled = false;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearError();
  if (!form.reportValidity()) return;
  const data = Object.fromEntries(new FormData(form).entries());
  for (const key of Object.keys(data)) data[key] = Number(data[key]);
  compareButton.disabled = true;
  compareButton.querySelector("span:first-child").textContent = "Comparing…";
  recommendationCard.setAttribute("aria-busy", "true");
  try {
    const response = await fetch("/api/evaluate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "The scenario could not be evaluated.");
    render(result);
  } catch (error) {
    recommendationCard.setAttribute("aria-busy", "false");
    showError(error instanceof Error ? error.message : "Could not reach the decision service. Please try again.");
  } finally {
    compareButton.disabled = false;
    compareButton.querySelector("span:first-child").textContent = "Compare options";
  }
});

exportButton.addEventListener("click", () => {
  if (!latestResult) return;
  const rows = [
    ["strategy", "sla_met", "throughput_mbps", "latency_ms", "reliability", "relative_energy_units", "resource_level", "fallback_used"],
    ...latestResult.options.map((option) => [
      labels[option.policy_name]?.[0] ?? option.policy_name,
      option.sla_met,
      option.throughput_mbps,
      option.latency_ms,
      option.reliability,
      option.energy_units,
      option.resource_level,
      option.fallback_used,
    ]),
  ];
  const csv = rows.map((row) => row.map((value) => `"${String(value).replaceAll('"', '""')}"`).join(",")).join("\r\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = "echo6g-scenario-comparison.csv";
  link.click();
  URL.revokeObjectURL(url);
});

form.requestSubmit();
