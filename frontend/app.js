const API = "http://localhost:8000/api";
const KARNATAKA_CENTER = [14.9, 75.7];
const OVERVIEW_ZOOM = 7;

const map = L.map("map", { zoomControl: true }).setView(KARNATAKA_CENTER, OVERVIEW_ZOOM);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution: "&copy; OpenStreetMap contributors",
  maxZoom: 18,
}).addTo(map);

const districtLayer = L.layerGroup().addTo(map);
const hotspotLayer = L.layerGroup().addTo(map);
const schoolLayer = L.layerGroup().addTo(map);
const hubLayer = L.layerGroup();

const ledgerBody = document.getElementById("ledgerBody");
const deployBody = document.getElementById("deployBody");
const resetBtn = document.getElementById("resetView");
const legendEl = document.querySelector(".legend");

let hotspots = [];
let maxLift = 1;
let activeClusterId = null;
let activeTab = "hotspots";
let lastOptimizeResult = null;

// ---- color helpers -------------------------------------------------

const RISK_LOW = [46, 125, 99];   // --risk-low
const RISK_MID = [212, 160, 23];  // --risk-mid
const RISK_HIGH = [178, 58, 46];  // --risk-high

function lerp(a, b, t) { return a + (b - a) * t; }

function colorForT(t) {
  t = Math.max(0, Math.min(1, t));
  const [c1, c2] = t < 0.5 ? [RISK_LOW, RISK_MID] : [RISK_MID, RISK_HIGH];
  const tt = t < 0.5 ? t / 0.5 : (t - 0.5) / 0.5;
  const rgb = c1.map((v, i) => Math.round(lerp(v, c2[i], tt)));
  return `rgb(${rgb.join(",")})`;
}

const TIER_COLOR = { Low: colorForT(0), Medium: colorForT(0.5), High: colorForT(1) };

// ---- data loading ----------------------------------------------------

async function loadStats() {
  const r = await fetch(`${API}/stats`);
  const s = await r.json();
  document.getElementById("statTotal").textContent = s.total_schools.toLocaleString();
  document.getElementById("statHigh").textContent = (s.risk_tier_counts.High || 0).toLocaleString();
  document.getElementById("statHotspots").textContent = s.hotspot_count;
  document.getElementById("statDistricts").textContent = s.districts;
}

async function loadHotspots() {
  const r = await fetch(`${API}/hotspots`);
  hotspots = await r.json();
  maxLift = Math.max(...hotspots.map((h) => h.risk_lift), 0.01);
  drawHotspots();
  drawLedger();
}

async function loadDistrictChoropleth() {
  const r = await fetch(`${API}/districts/geojson`);
  const geojson = await r.json();

  const risks = geojson.features.map((f) => f.properties.avg_risk);
  const lo = Math.min(...risks), hi = Math.max(...risks);
  const norm = (v) => (hi > lo ? (v - lo) / (hi - lo) : 0.5);

  L.geoJSON(geojson, {
    style: (feature) => ({
      color: "#8A9490",
      weight: 1,
      fillColor: colorForT(norm(feature.properties.avg_risk)),
      fillOpacity: 0.45,
    }),
    onEachFeature: (feature, layer) => {
      const p = feature.properties;
      layer.bindTooltip(
        `<strong>${p.display_name}</strong><br/>${p.school_count.toLocaleString()} schools · avg risk ${p.avg_risk}`,
        { sticky: true }
      );
      layer.on("mouseover", () => layer.setStyle({ weight: 2, fillOpacity: 0.65 }));
      layer.on("mouseout", () => layer.setStyle({ weight: 1, fillOpacity: 0.45 }));
      layer.on("click", () => map.flyToBounds(layer.getBounds(), { duration: 0.6, maxZoom: 9 }));
    },
  }).addTo(districtLayer);
}

// ---- map drawing ----------------------------------------------------

function drawHotspots() {
  hotspotLayer.clearLayers();
  hotspots.forEach((h) => {
    const t = h.risk_lift / maxLift;
    const circle = L.circleMarker([h.centroid_lat, h.centroid_lon], {
      radius: 8 + Math.sqrt(h.school_count) * 2.2,
      color: "#14181C",
      weight: 1,
      fillColor: colorForT(t),
      fillOpacity: 0.75,
    });
    circle.bindTooltip(
      `<strong>${h.district}</strong><br/>${h.school_count} schools · risk lift +${h.risk_lift.toFixed(2)}`,
      { sticky: true }
    );
    circle.on("click", () => selectHotspot(h.cluster_id));
    circle.addTo(hotspotLayer);
  });
}

function drawSchools(list) {
  schoolLayer.clearLayers();
  list.forEach((s) => {
    const marker = L.circleMarker([s.lat, s.lon], {
      radius: 6,
      color: "#14181C",
      weight: 1,
      fillColor: TIER_COLOR[s.risk_tier] || TIER_COLOR.Medium,
      fillOpacity: 0.85,
    });
    marker.bindPopup(`
      <div class="school-popup">
        <span class="name">${s.schname}</span>
        <span class="meta">${s.district} · ${s.rural_urban} · ${s.management}</span>
        <span class="meta">${s.school_cat}</span>
        <span class="risk">Demo risk score: ${s.risk_score} (${s.risk_tier})</span>
      </div>
    `);
    marker.addTo(schoolLayer);
  });
}

// ---- ledger panel -----------------------------------------------------

function drawLedger() {
  ledgerBody.innerHTML = "";
  hotspots.forEach((h, i) => {
    const row = document.createElement("li");
    row.className = "ledger-row";
    row.dataset.clusterId = h.cluster_id;
    row.setAttribute("tabindex", "0");
    row.innerHTML = `
      <span class="rank">${i + 1}</span>
      <span class="name">${h.district}</span>
      <span class="count">${h.school_count}</span>
      <span class="lift" style="color:${colorForT(h.risk_lift / maxLift)}">+${h.risk_lift.toFixed(2)}</span>
    `;
    row.addEventListener("click", () => selectHotspot(h.cluster_id));
    row.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") selectHotspot(h.cluster_id);
    });
    ledgerBody.appendChild(row);
  });
}

function setActiveLedgerRow(clusterId) {
  document.querySelectorAll(".ledger-row").forEach((row) => {
    row.classList.toggle("active", Number(row.dataset.clusterId) === clusterId);
  });
}

// ---- interaction -----------------------------------------------------

async function selectHotspot(clusterId) {
  activeClusterId = clusterId;
  const hotspot = hotspots.find((h) => h.cluster_id === clusterId);
  if (!hotspot) return;

  const r = await fetch(`${API}/schools?cluster_id=${clusterId}`);
  const schools = await r.json();
  drawSchools(schools);

  map.flyTo([hotspot.centroid_lat, hotspot.centroid_lon], 12, { duration: 0.6 });
  setActiveLedgerRow(clusterId);
  resetBtn.hidden = false;
}

resetBtn.addEventListener("click", () => {
  activeClusterId = null;
  schoolLayer.clearLayers();
  map.flyTo(KARNATAKA_CENTER, OVERVIEW_ZOOM, { duration: 0.6 });
  setActiveLedgerRow(null);
  resetBtn.hidden = true;
});

document.getElementById("toggleAbout").addEventListener("click", (e) => {
  const panel = document.getElementById("aboutPanel");
  const expanded = e.target.getAttribute("aria-expanded") === "true";
  panel.hidden = expanded;
  e.target.setAttribute("aria-expanded", String(!expanded));
});

// ---- deploy-units tab ------------------------------------------------

const HOTSPOT_LEGEND = `
  <span class="legend-title">Risk lift vs. state average</span>
  <div class="legend-scale"><span class="swatch low"></span><span class="swatch mid"></span><span class="swatch high"></span></div>
  <div class="legend-labels"><span>lower</span><span>higher</span></div>
  <div class="legend-labels" style="margin-top:4px;"><span>shaded districts = avg risk · circles = hotspot cells</span></div>
`;
const DEPLOY_LEGEND = `
  <span class="legend-title">Deployment plan</span>
  <div class="legend-labels" style="margin-top:6px;"><span>&#9670; chosen unit base</span></div>
  <div class="legend-labels"><span>dashed circle = service radius</span></div>
`;

function switchTab(tab) {
  activeTab = tab;
  const isHotspots = tab === "hotspots";

  document.getElementById("tabHotspots").classList.toggle("active", isHotspots);
  document.getElementById("tabHotspots").setAttribute("aria-selected", String(isHotspots));
  document.getElementById("tabDeploy").classList.toggle("active", !isHotspots);
  document.getElementById("tabDeploy").setAttribute("aria-selected", String(!isHotspots));
  document.getElementById("hotspotsPanel").hidden = !isHotspots;
  document.getElementById("deployPanel").hidden = isHotspots;

  if (isHotspots) {
    map.addLayer(districtLayer);
    map.addLayer(hotspotLayer);
    map.addLayer(schoolLayer);
    map.removeLayer(hubLayer);
    legendEl.innerHTML = HOTSPOT_LEGEND;
    resetBtn.hidden = activeClusterId === null;
  } else {
    map.removeLayer(districtLayer);
    map.removeLayer(hotspotLayer);
    map.removeLayer(schoolLayer);
    map.addLayer(hubLayer);
    resetBtn.hidden = true;
    legendEl.innerHTML = DEPLOY_LEGEND;
    if (lastOptimizeResult) map.flyTo(KARNATAKA_CENTER, OVERVIEW_ZOOM, { duration: 0.4 });
  }
}

document.getElementById("tabHotspots").addEventListener("click", () => switchTab("hotspots"));
document.getElementById("tabDeploy").addEventListener("click", () => switchTab("deploy"));

document.getElementById("equityInput").addEventListener("change", (e) => {
  document.getElementById("capInput").disabled = !e.target.checked;
});

function drawHubs(chosenSites, radiusKm) {
  hubLayer.clearLayers();
  chosenSites.forEach((s) => {
    L.circle([s.lat, s.lon], {
      radius: radiusKm * 1000,
      color: "#2B3A4A",
      weight: 1,
      dashArray: "4,4",
      fillColor: "#2B3A4A",
      fillOpacity: 0.06,
    }).addTo(hubLayer);

    const hub = L.circleMarker([s.lat, s.lon], {
      radius: 9,
      color: "#14181C",
      weight: 1.5,
      fillColor: "#D4A017",
      fillOpacity: 0.95,
    });
    hub.bindTooltip(
      `<strong>${s.district}</strong><br/>base for 1 unit · covers up to ${s.school_count} schools nearby`,
      { sticky: true }
    );
    hub.addTo(hubLayer);
  });
}

function drawDeployLedger(chosenSites) {
  deployBody.innerHTML = "";
  chosenSites.forEach((s, i) => {
    const row = document.createElement("li");
    row.className = "ledger-row";
    row.setAttribute("tabindex", "0");
    row.innerHTML = `
      <span class="rank">${i + 1}</span>
      <span class="name">${s.district}</span>
      <span class="count">${s.school_count}</span>
      <span class="lift">${s.demand.toFixed(0)}</span>
    `;
    row.addEventListener("click", () => {
      map.flyTo([s.lat, s.lon], 10, { duration: 0.6 });
    });
    deployBody.appendChild(row);
  });
}

async function runOptimize() {
  const btn = document.getElementById("runOptimize");
  const hint = document.getElementById("deployHint");
  const k = document.getElementById("kInput").value;
  const radius = document.getElementById("radiusInput").value;
  const equity = document.getElementById("equityInput").checked;
  const cap = document.getElementById("capInput").value;

  btn.disabled = true;
  btn.textContent = "Solving…";
  hint.textContent = "Running the ILP over candidate sites — usually under a second.";

  try {
    const url = `${API}/optimize?k=${k}&radius_km=${radius}&equity=${equity}&max_per_district=${cap}`;
    const r = await fetch(url);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const result = await r.json();
    lastOptimizeResult = result;

    document.getElementById("deployResults").hidden = false;
    document.getElementById("resultIlpPct").textContent = `${result.ilp_coverage_pct}%`;
    document.getElementById("resultGreedyPct").textContent = `${result.greedy_coverage_pct}%`;
    document.getElementById("resultGap").textContent =
      result.gap > 0.05 ? `+${result.gap.toFixed(1)} risk-units` : "matched greedy";
    document.getElementById("resultTime").textContent = `${result.solve_seconds}s (${result.status})`;

    drawHubs(result.chosen_sites, Number(radius));
    drawDeployLedger(result.chosen_sites);
    hint.textContent = `${result.chosen_sites.length} units placed, covering ${result.ilp_coverage_pct}% of statewide weighted risk.`;
  } catch (err) {
    hint.textContent = "Couldn't reach the optimizer endpoint — is the backend running on :8000?";
    console.error("optimize failed", err);
  } finally {
    btn.disabled = false;
    btn.textContent = "Run optimizer";
  }
}

document.getElementById("runOptimize").addEventListener("click", runOptimize);

// ---- boot -----------------------------------------------------------

loadStats().catch((err) => console.error("stats failed — is the backend running on :8000?", err));
loadHotspots().catch((err) => console.error("hotspots failed — is the backend running on :8000?", err));
loadDistrictChoropleth().catch((err) => console.error("district choropleth failed — is the backend running on :8000?", err));
