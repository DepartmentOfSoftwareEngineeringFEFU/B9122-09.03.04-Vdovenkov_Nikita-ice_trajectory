function switchMode(mode) {
    AppState.currentMode = mode;
    document.getElementById("mode-rect").style.display = mode === "rect" ? "block" : "none";
    document.getElementById("mode-circle").style.display = mode === "circle" ? "block" : "none";
    document.getElementById("tab-rect").classList.toggle("active", mode === "rect");
    document.getElementById("tab-circle").classList.toggle("active", mode === "circle");

    if (AppState.circlePreviewLayer) { map.removeLayer(AppState.circlePreviewLayer); AppState.circlePreviewLayer = null; }
    if (AppState.drawnRect) { drawnItems.removeLayer(AppState.drawnRect); AppState.drawnRect = null; }
    if (AppState.octagonPreview) { map.removeLayer(AppState.octagonPreview); AppState.octagonPreview = null; }
    AppState.drawnBounds = null;
    AppState.circleCenter = null;

    document.getElementById("save-area-block").style.display = "none";
    document.getElementById("save-circle-block").style.display = "none";
    document.getElementById("sliders-block").style.display = "none";
    document.getElementById("draw-hint").style.display = mode === "rect" ? "block" : "none";
}

function updateOctagon() {
    if (!AppState.drawnBounds) return;

    const cutTL = parseInt(document.getElementById("cut-tl").value);
    const cutTR = parseInt(document.getElementById("cut-tr").value);
    const cutBL = parseInt(document.getElementById("cut-bl").value);
    const cutBR = parseInt(document.getElementById("cut-br").value);

    document.getElementById("cut-tl-val").textContent = cutTL + "%";
    document.getElementById("cut-tr-val").textContent = cutTR + "%";
    document.getElementById("cut-bl-val").textContent = cutBL + "%";
    document.getElementById("cut-br-val").textContent = cutBR + "%";

    const pts = computeOctagon(AppState.drawnBounds, cutTL, cutTR, cutBL, cutBR);

    if (AppState.octagonPreview) map.removeLayer(AppState.octagonPreview);
    AppState.octagonPreview = L.polygon(pts, {
        color: "#2196F3", weight: 2, fillOpacity: 0.1, dashArray: "5,5"
    }).addTo(map);
}

map.on(L.Draw.Event.CREATED, function(e) {
    if (AppState.currentMode !== "rect") return;

    if (AppState.drawnRect) drawnItems.removeLayer(AppState.drawnRect);
    AppState.drawnRect = e.layer;
    drawnItems.addLayer(AppState.drawnRect);
    AppState.drawnBounds = AppState.drawnRect.getBounds();

    if (AppState.drawMode === "ice") {
        document.getElementById("save-ice-block").style.display = "flex";
    } else {
        AppState.drawMode = "area";
        document.getElementById("draw-hint").style.display = "none";
        document.getElementById("sliders-block").style.display = "block";
        document.getElementById("save-area-block").style.display = "flex";
        document.getElementById("area-name-input").focus();
        updateOctagon();
    }
});

document.getElementById("save-area-btn").addEventListener("click", () => {
    const name = document.getElementById("area-name-input").value.trim();
    if (!name) { alert("Введите название акватории"); return; }
    if (!AppState.drawnBounds) return;

    const cutTL = parseInt(document.getElementById("cut-tl").value);
    const cutTR = parseInt(document.getElementById("cut-tr").value);
    const cutBL = parseInt(document.getElementById("cut-bl").value);
    const cutBR = parseInt(document.getElementById("cut-br").value);
    const pts = computeOctagon(AppState.drawnBounds, cutTL, cutTR, cutBL, cutBR);

    saveAreaFromPoints(name, pts);
});

document.getElementById("cancel-area-btn").addEventListener("click", () => {
    if (AppState.drawnRect) { drawnItems.removeLayer(AppState.drawnRect); AppState.drawnRect = null; }
    if (AppState.octagonPreview) { map.removeLayer(AppState.octagonPreview); AppState.octagonPreview = null; }
    AppState.drawnBounds = null;
    document.getElementById("save-area-block").style.display = "none";
    document.getElementById("sliders-block").style.display = "none";
    document.getElementById("draw-hint").style.display = "block";
    document.getElementById("area-name-input").value = "";
});

function updateCirclePreview() {
    const radiusVal = document.getElementById("circle-radius").value;
    const cutVal = document.getElementById("circle-cut").value;
    document.getElementById("circle-radius-val").textContent = radiusVal;
    document.getElementById("circle-cut-val").textContent = cutVal + "%";

    if (!AppState.circleCenter) return;

    const pts = computeOctagonFromCenter(AppState.circleCenter, parseInt(radiusVal), parseInt(cutVal));
    if (AppState.circlePreviewLayer) map.removeLayer(AppState.circlePreviewLayer);
    AppState.circlePreviewLayer = L.polygon(pts, {
        color: "#2196F3", weight: 2, fillOpacity: 0.1, dashArray: "5,5"
    }).addTo(map);
}

document.getElementById("save-circle-btn").addEventListener("click", () => {
    const name = document.getElementById("circle-name-input").value.trim();
    if (!name) { alert("Введите название акватории"); return; }
    if (!AppState.circleCenter) return;

    const radiusVal = parseInt(document.getElementById("circle-radius").value);
    const cutVal = parseInt(document.getElementById("circle-cut").value);
    const pts = computeOctagonFromCenter(AppState.circleCenter, radiusVal, cutVal);

    saveAreaFromPoints(name, pts);
});

document.getElementById("cancel-circle-btn").addEventListener("click", () => {
    if (AppState.circlePreviewLayer) { map.removeLayer(AppState.circlePreviewLayer); AppState.circlePreviewLayer = null; }
    AppState.circleCenter = null;
    document.getElementById("save-circle-block").style.display = "none";
    document.getElementById("circle-name-input").value = "";
});

function saveAreaFromPoints(name, pts) {
    const lats = pts.map(p => p[0]);
    const lons = pts.map(p => p[1]);

    fetch("/api/water-areas/", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCookie("csrftoken"),
        },
        body: JSON.stringify({
            name: name,
            lat_min: Math.min(...lats).toFixed(6),
            lat_max: Math.max(...lats).toFixed(6),
            lon_min: Math.min(...lons).toFixed(6),
            lon_max: Math.max(...lons).toFixed(6),
        }),
    })
    .then(res => res.json())
    .then(data => {
        if (!data.id) { alert("Ошибка: " + JSON.stringify(data)); return; }

        saveOctagonPoints(data.id, pts).then(() => {
            if (AppState.drawnRect) { drawnItems.removeLayer(AppState.drawnRect); AppState.drawnRect = null; }
            if (AppState.octagonPreview) { map.removeLayer(AppState.octagonPreview); AppState.octagonPreview = null; }
            if (AppState.circlePreviewLayer) { map.removeLayer(AppState.circlePreviewLayer); AppState.circlePreviewLayer = null; }
            AppState.drawnBounds = null;
            AppState.circleCenter = null;
            document.getElementById("save-area-block").style.display = "none";
            document.getElementById("save-circle-block").style.display = "none";
            document.getElementById("sliders-block").style.display = "none";
            document.getElementById("draw-hint").style.display = AppState.currentMode === "rect" ? "block" : "none";
            document.getElementById("area-name-input").value = "";
            document.getElementById("circle-name-input").value = "";
            loadWaterAreas();
        });
    });
}

function deleteArea(id, name) {
    if (!confirm(`Удалить акваторию "${name}"?`)) return;
    fetch(`/api/water-areas/${id}/`, {
        method: "DELETE",
        headers: { "X-CSRFToken": getCookie("csrftoken") },
    }).then(() => {
        loadWaterAreas();
        const sel = document.getElementById("water-area-select");
        if (sel.value == id) {
            sel.value = "";
            sel.dispatchEvent(new Event("change"));
        }
    });
}

function selectIceType(type, btn) {
    AppState.selectedIceType = type;
    document.querySelectorAll(".ice-color-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
}

document.getElementById("cancel-ice-btn").addEventListener("click", () => {
    if (AppState.drawnRect) { drawnItems.removeLayer(AppState.drawnRect); AppState.drawnRect = null; }
    AppState.drawnBounds = null;
    document.getElementById("save-ice-block").style.display = "none";
    AppState.drawMode = null;
});

document.getElementById("save-ice-btn").addEventListener("click", () => {
    const areaId = document.getElementById("water-area-select").value;
    if (!areaId) { alert("Сначала выберите акваторию"); return; }
    if (!AppState.drawnBounds) return;

    fetch("/api/ice-zones/", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCookie("csrftoken"),
        },
        body: JSON.stringify({
            area: areaId,
            ice_type: AppState.selectedIceType,
            lat_min: AppState.drawnBounds.getSouth().toFixed(6),
            lat_max: AppState.drawnBounds.getNorth().toFixed(6),
            lon_min: AppState.drawnBounds.getWest().toFixed(6),
            lon_max: AppState.drawnBounds.getEast().toFixed(6),
        }),
    })
    .then(res => res.json())
    .then(data => {
        if (data.id) {
            if (AppState.drawnRect) { drawnItems.removeLayer(AppState.drawnRect); AppState.drawnRect = null; }
            AppState.drawnBounds = null;
            document.getElementById("save-ice-block").style.display = "none";
            AppState.drawMode = null;
            loadIceZones(areaId);
        } else {
            alert("Ошибка: " + JSON.stringify(data));
        }
    });
});

function deleteIceZone(id) {
    if (!confirm("Удалить ледовую зону?")) return;
    fetch(`/api/ice-zones/${id}/`, {
        method: "DELETE",
        headers: { "X-CSRFToken": getCookie("csrftoken") },
    }).then(() => {
        if (AppState.iceLayers[id]) { map.removeLayer(AppState.iceLayers[id]); delete AppState.iceLayers[id]; }
        loadIceZones(document.getElementById("water-area-select").value);
    });
}

function loadWaterAreas() {
    fetch("/api/water-areas/")
        .then(res => res.json())
        .then(data => {
            const items = data.results || data;
            const sel = document.getElementById("water-area-select");
            const current = sel.value;

            sel.innerHTML = "<option value=''>— выберите акваторию —</option>";
            items.forEach(area => {
                const option = document.createElement("option");
                option.value = area.id;
                option.text = area.name;
                option.dataset.latMin = area.lat_min;
                option.dataset.latMax = area.lat_max;
                option.dataset.lonMin = area.lon_min;
                option.dataset.lonMax = area.lon_max;
                if (area.points && area.points.length > 0) {
                    option.dataset.points = JSON.stringify(area.points);
                }
                sel.appendChild(option);
            });
            sel.value = current;

            const areaList = document.getElementById("area-list");
            areaList.innerHTML = "";
            items.forEach(area => {
                const div = document.createElement("div");
                div.className = "area-item";
                div.innerHTML = `
                    <span>${area.name}</span>
                    <button class="btn-red" onclick="deleteArea(${area.id}, '${area.name}')">Удалить</button>
                `;
                areaList.appendChild(div);
            });
        });
}

function loadIceZones(areaId) {
    Object.values(AppState.iceLayers).forEach(l => map.removeLayer(l));
    AppState.iceLayers = {};
    document.getElementById("ice-zone-list").innerHTML = "";

    if (!areaId) return;

    fetch(`/api/ice-zones/?water_area=${areaId}`)
        .then(res => res.json())
        .then(data => {
            const items = data.results || data;
            items.forEach(zone => {
                const colors = ICE_COLORS[zone.ice_type];
                const bounds = [
                    [parseFloat(zone.lat_min), parseFloat(zone.lon_min)],
                    [parseFloat(zone.lat_max), parseFloat(zone.lon_max)],
                ];
                const layer = L.rectangle(bounds, {
                    color: colors.color,
                    fillColor: colors.fillColor,
                    fillOpacity: 0.3,
                    weight: 2,
                }).addTo(map);
                AppState.iceLayers[zone.id] = layer;

                const labels = { none: "Открытая вода", light: "Молодой", heavy: "Толстый" };
                const div = document.createElement("div");
                div.className = "ice-item";
                div.innerHTML = `
                    <div class="ice-label">
                        <span class="ice-dot" style="background:${colors.color}"></span>
                        <span>${labels[zone.ice_type]}</span>
                    </div>
                    <button class="btn-red" onclick="deleteIceZone(${zone.id})">Удалить</button>
                `;
                document.getElementById("ice-zone-list").appendChild(div);
            });
        });
}