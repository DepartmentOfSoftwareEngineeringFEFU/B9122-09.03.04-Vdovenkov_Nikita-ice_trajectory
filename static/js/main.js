map.on("click", function(e) {
    if (AppState.pickingMode === "start") {
        AppState.routeStart = e.latlng;
        document.getElementById("start-coords").textContent =
            e.latlng.lat.toFixed(4) + ", " + e.latlng.lng.toFixed(4);

        if (AppState.startMarker) map.removeLayer(AppState.startMarker);
        AppState.startMarker = L.circleMarker(e.latlng, {
            radius: 8, color: "green", fillColor: "green", fillOpacity: 1
        }).addTo(map).bindPopup("Начало маршрута").openPopup();

        AppState.pickingMode = null;
        document.getElementById("pick-start-btn").classList.remove("selecting");
        document.getElementById("pick-start-btn").textContent = "Выбрать начало";
        checkRunBtn();
        return;
    }

    if (AppState.pickingMode === "end") {
        AppState.routeEnd = e.latlng;
        document.getElementById("end-coords").textContent =
            e.latlng.lat.toFixed(4) + ", " + e.latlng.lng.toFixed(4);

        if (AppState.endMarker) map.removeLayer(AppState.endMarker);
        AppState.endMarker = L.circleMarker(e.latlng, {
            radius: 8, color: "red", fillColor: "red", fillOpacity: 1
        }).addTo(map).bindPopup("Конец маршрута").openPopup();

        AppState.pickingMode = null;
        document.getElementById("pick-end-btn").classList.remove("selecting");
        document.getElementById("pick-end-btn").textContent = "Выбрать конец";
        checkRunBtn();
        return;
    }

    if (AppState.currentMode === "circle" && AppState.drawMode !== "ice") {
        AppState.circleCenter = e.latlng;
        document.getElementById("save-circle-block").style.display = "flex";
        updateCirclePreview();
    }
});

document.getElementById("water-area-select").addEventListener("change", () => {
    const areaId = document.getElementById("water-area-select").value;
    const runBtn = document.getElementById("run-btn");
    const status = document.getElementById("status");

    runBtn.disabled = true;
    clearRoute();

    if (AppState.areaLayer) { map.removeLayer(AppState.areaLayer); AppState.areaLayer = null; }

    AppState.routeStart = null;
    AppState.routeEnd = null;
    document.getElementById("start-coords").textContent = "не выбрано";
    document.getElementById("end-coords").textContent = "не выбрано";
    document.getElementById("route-points-block").style.display = "none";

    updateLayerToggles(areaId);

    document.getElementById('clear-routes-btn').style.display = areaId ? 'block' : 'none';

    if (!areaId) {
        status.textContent = "";
        loadIceZones(null);
        document.getElementById("ice-type-select").style.display = "none";
        document.getElementById("ice-hint").style.display = "block";
        document.getElementById("draw-mode-toggle").style.display = "none";
        AppState.drawMode = null;
        return;
    }

    const selected = document.getElementById("water-area-select").options[
        document.getElementById("water-area-select").selectedIndex
    ];

    const pointsData = selected.dataset.points;
    if (pointsData) {
        const pts = JSON.parse(pointsData).map(p => [parseFloat(p.latitude), parseFloat(p.longitude)]);
        AppState.areaLayer = L.polygon(pts, { color: "#2196F3", weight: 2, fillOpacity: 0.05 }).addTo(map);
        map.fitBounds(AppState.areaLayer.getBounds());
    } else {
        const bounds = [
            [parseFloat(selected.dataset.latMin), parseFloat(selected.dataset.lonMin)],
            [parseFloat(selected.dataset.latMax), parseFloat(selected.dataset.lonMax)]
        ];
        AppState.areaLayer = L.rectangle(bounds, { color: "#2196F3", weight: 2, fillOpacity: 0.05 }).addTo(map);
        map.fitBounds(bounds);
    }

    document.getElementById("route-points-block").style.display = "block";
    document.getElementById("ice-hint").style.display = "none";
    document.getElementById("ice-type-select").style.display = "flex";
    document.getElementById("draw-mode-toggle").style.display = "flex";
    AppState.drawMode = "ice";
    document.getElementById("draw-ice-btn").style.background = "#1976D2";
    document.getElementById("draw-area-btn").style.background = "#43a047";

    loadIceZones(areaId);
    loadSavedRoutes(selected.text);
    status.textContent = "";
});

loadWaterAreas();

fetch("/api/ship-types/")
    .then(res => res.json())
    .then(data => {
        const sel = document.getElementById("ice-class-select");
        sel.innerHTML = "";
        const items = data.results || data;
        items.forEach(st => {
            const opt = document.createElement("option");
            opt.value = st.code;
            opt.text = st.code;
            sel.appendChild(opt);
        });
    });