/* Frontend for the NGO Funding Tracker: search, detail panel, Cytoscape graph. */

const TYPE_COLORS = {
  ngo: "#3fb950",
  foundation: "#a371f7",
  person: "#f0883e",
  government: "#58a6ff",
  corporation: "#db61a2",
};

const els = {
  search: document.getElementById("search-input"),
  typeFilter: document.getElementById("type-filter"),
  results: document.getElementById("results"),
  detail: document.getElementById("detail"),
  detailName: document.getElementById("detail-name"),
  detailMeta: document.getElementById("detail-meta"),
  detailDesc: document.getElementById("detail-desc"),
  detailFunded: document.getElementById("detail-funded"),
  detailReceived: document.getElementById("detail-received"),
  upgrade: document.getElementById("upgrade"),
  upgradeMsg: document.getElementById("upgrade-msg"),
  depth: document.getElementById("depth"),
  depthValue: document.getElementById("depth-value"),
  apiKey: document.getElementById("api-key"),
  exportBtn: document.getElementById("export-btn"),
  emptyState: document.getElementById("empty-state"),
  tooltip: document.getElementById("edge-tooltip"),
};

let cy = null;
let currentEntityId = null;
let searchTimer = null;

function formatUsd(value) {
  if (value >= 1e9) return `$${(value / 1e9).toFixed(1)}B`;
  if (value >= 1e6) return `$${(value / 1e6).toFixed(1)}M`;
  if (value >= 1e3) return `$${(value / 1e3).toFixed(0)}K`;
  return `$${value.toFixed(0)}`;
}

function headers() {
  const key = els.apiKey.value.trim();
  return key ? { "X-API-Key": key } : {};
}

async function apiGet(path) {
  const response = await fetch(path, { headers: headers() });
  const body = await response.json();
  if (!response.ok) {
    const error = new Error(body.error?.message || "Request failed");
    error.code = body.error?.code;
    throw error;
  }
  return body;
}

async function runSearch() {
  const q = els.search.value.trim();
  if (q.length < 2) {
    els.results.innerHTML = "";
    return;
  }
  const type = els.typeFilter.value;
  const params = new URLSearchParams({ q });
  if (type) params.set("type", type);
  try {
    const data = await apiGet(`/api/search?${params}`);
    renderResults(data.results);
  } catch (err) {
    els.results.innerHTML = `<li><span class="r-name">${err.message}</span></li>`;
  }
}

function renderResults(results) {
  els.results.innerHTML = "";
  if (results.length === 0) {
    els.results.innerHTML = '<li><span class="r-name">No matches.</span></li>';
    return;
  }
  for (const entity of results) {
    const li = document.createElement("li");
    li.innerHTML = `<span class="r-name">${entity.name}</span><span class="r-type">${entity.type}</span>`;
    li.addEventListener("click", () => selectEntity(entity.id));
    els.results.appendChild(li);
  }
}

async function selectEntity(entityId) {
  currentEntityId = entityId;
  hideUpgrade();
  hideTooltip();
  try {
    const [detail, network] = await Promise.all([
      apiGet(`/api/entities/${entityId}`),
      apiGet(`/api/entities/${entityId}/network?depth=${els.depth.value}`),
    ]);
    renderDetail(detail);
    renderGraph(network);
  } catch (err) {
    if (err.code === "forbidden") showUpgrade(err.message);
    else showUpgrade(err.message);
  }
}

function renderDetail(detail) {
  els.detail.classList.remove("hidden");
  els.detailName.textContent = detail.name;
  els.detailMeta.textContent = [detail.type, detail.country].filter(Boolean).join(" · ");
  els.detailDesc.textContent = detail.description || "";
  els.detailFunded.textContent = formatUsd(detail.total_funded_usd);
  els.detailReceived.textContent = formatUsd(detail.total_received_usd);
}

function renderGraph(network) {
  els.emptyState.classList.add("hidden");
  const maxAmount = Math.max(...network.edges.map((e) => e.amount_usd), 1);
  const received = {};
  for (const edge of network.edges) {
    received[edge.target_id] = (received[edge.target_id] || 0) + edge.amount_usd;
    received[edge.source_id] = received[edge.source_id] || 0;
  }
  const maxReceived = Math.max(...Object.values(received), 1);

  const nodes = network.nodes.map((node) => ({
    data: {
      id: String(node.id),
      label: node.name,
      color: TYPE_COLORS[node.type] || "#8b949e",
      size: 28 + 34 * Math.sqrt((received[node.id] || 0) / maxReceived),
      isRoot: node.id === network.root_id,
    },
  }));
  const edges = network.edges.map((edge, i) => ({
    data: {
      id: `e${i}`,
      source: String(edge.source_id),
      target: String(edge.target_id),
      width: 1.5 + 6 * Math.sqrt(edge.amount_usd / maxAmount),
      amount: edge.amount_usd,
      year: edge.year,
      purpose: edge.purpose,
      citation: edge.citation,
    },
  }));

  if (cy) cy.destroy();
  cy = cytoscape({
    container: document.getElementById("graph"),
    elements: { nodes, edges },
    style: [
      {
        selector: "node",
        style: {
          "background-color": "data(color)",
          label: "data(label)",
          color: "#e6edf3",
          "font-size": "11px",
          "text-valign": "bottom",
          "text-margin-y": 6,
          width: "data(size)",
          height: "data(size)",
          "text-wrap": "wrap",
          "text-max-width": "120px",
          "border-width": 2,
          "border-color": "#0d1117",
        },
      },
      {
        selector: "node[?isRoot]",
        style: { "border-width": 4, "border-color": "#e6edf3" },
      },
      {
        selector: "edge",
        style: {
          width: "data(width)",
          "line-color": "#3d4654",
          "target-arrow-color": "#3d4654",
          "target-arrow-shape": "triangle",
          "curve-style": "bezier",
          "arrow-scale": 0.9,
        },
      },
      {
        selector: "edge:selected",
        style: { "line-color": "#58a6ff", "target-arrow-color": "#58a6ff" },
      },
    ],
    layout: { name: "cose", animate: false, padding: 50, nodeRepulsion: 12000 },
  });

  cy.on("tap", "node", (event) => {
    const id = Number(event.target.id());
    if (id !== currentEntityId) selectEntity(id);
  });

  cy.on("tap", "edge", (event) => {
    const data = event.target.data();
    const pos = event.renderedPosition;
    els.tooltip.innerHTML = `
      <div><span class="amount">${formatUsd(data.amount)}</span> · ${data.year}</div>
      ${data.purpose ? `<div>${data.purpose}</div>` : ""}
      <div><a href="${data.citation}" target="_blank" rel="noopener">Source</a></div>`;
    els.tooltip.style.left = `${pos.x + 12}px`;
    els.tooltip.style.top = `${pos.y + 12}px`;
    els.tooltip.classList.remove("hidden");
  });

  cy.on("tap", (event) => {
    if (event.target === cy) hideTooltip();
  });
}

function showUpgrade(message) {
  els.upgrade.classList.remove("hidden");
  els.upgradeMsg.textContent = message;
}

function hideUpgrade() {
  els.upgrade.classList.add("hidden");
}

function hideTooltip() {
  els.tooltip.classList.add("hidden");
}

async function exportCsv() {
  if (!currentEntityId) {
    showUpgrade("Select an entity first, then export its network.");
    return;
  }
  const response = await fetch(
    `/api/entities/${currentEntityId}/export.csv?depth=${els.depth.value}`,
    { headers: headers() }
  );
  if (!response.ok) {
    const body = await response.json();
    showUpgrade(body.error?.message || "Export failed.");
    return;
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `network_${currentEntityId}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

els.search.addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(runSearch, 250);
});
els.typeFilter.addEventListener("change", runSearch);
els.depth.addEventListener("input", () => {
  els.depthValue.textContent = els.depth.value;
});
els.depth.addEventListener("change", () => {
  if (currentEntityId) selectEntity(currentEntityId);
});
els.exportBtn.addEventListener("click", exportCsv);
