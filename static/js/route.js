document.getElementById("pick-start-btn").addEventListener("click", () => {
    if (AppState.pickingMode === "start") {
        AppState.pickingMode = null;
        document.getElementById("pick-start-btn").classList.remove("selecting");
        document.getElementById("pick-start-btn").textContent = "Выбрать начало";
    } else {
        AppState.pickingMode = "start";
        document.getElementById("pick-start-btn").classList.add("selecting");
        document.getElementById("pick-start-btn").textContent = "Кликните на карте...";
        document.getElementById("pick-end-btn").classList.remove("selecting");
        document.getElementById("pick-end-btn").textContent = "Выбрать конец";
    }
});

document.getElementById("pick-end-btn").addEventListener("click", () => {
    if (AppState.pickingMode === "end") {
        AppState.pickingMode = null;
        document.getElementById("pick-end-btn").classList.remove("selecting");
        document.getElementById("pick-end-btn").textContent = "Выбрать конец";
    } else {
        AppState.pickingMode = "end";
        document.getElementById("pick-end-btn").classList.add("selecting");
        document.getElementById("pick-end-btn").textContent = "Кликните на карте...";
        document.getElementById("pick-start-btn").classList.remove("selecting");
        document.getElementById("pick-start-btn").textContent = "Выбрать начало";
    }
});

function checkRunBtn() {
    const areaId = document.getElementById("water-area-select").value;
    document.getElementById("run-btn").disabled = !(areaId && AppState.routeStart && AppState.routeEnd);
}

function setStatus(msg, pct, isError) {
    const statusEl = document.getElementById("status");
    if (pct !== undefined) {
        statusEl.style.color = "";
        statusEl.innerHTML = `
            <div>${msg}</div>
            <div style="margin-top:6px; background:#ddd; border-radius:4px; height:8px; width:100%;">
                <div style="background:#3388ff; height:8px; border-radius:4px; width:${pct}%; transition:width 0.3s;"></div>
            </div>
            <div style="font-size:11px; color:#888; margin-top:2px;">${pct}%</div>`;
    } else {
        statusEl.style.color = isError ? "#e53935" : "";
        statusEl.textContent = msg;
    }
}

AppState.savedRouteLayers = {};

function drawSavedRoute(route) {
    if (AppState.savedRouteLayers[route.id]) return;

    const coords = route.points.map(p => [p.latitude, p.longitude]);
    if (coords.length < 2) return;

    const line = L.polyline(coords, { color: "blue", weight: 3, opacity: 0.7 }).addTo(map);

    const startMarker = L.circleMarker(coords[0], {
        radius: 8, color: "green", fillColor: "green", fillOpacity: 1
    }).addTo(map);

    const endMarker = L.circleMarker(coords[coords.length - 1], {
        radius: 8, color: "red", fillColor: "red", fillOpacity: 1
    }).addTo(map);

    AppState.savedRouteLayers[route.id] = { line, startMarker, endMarker };
    map.fitBounds(line.getBounds());
}

function clearSavedRoutes() {
    Object.values(AppState.savedRouteLayers).forEach(({ line, startMarker, endMarker }) => {
        map.removeLayer(line);
        map.removeLayer(startMarker);
        map.removeLayer(endMarker);
    });
    AppState.savedRouteLayers = {};
}

function loadSavedRoutes(areaName) {
    if (!areaName) return;
    fetch(`/api/routes/?area_name=${encodeURIComponent(areaName)}`)
        .then(res => res.json())
        .then(data => {
            const routes = data.results || data;
            routes.forEach(drawSavedRoute);
        });
}

function saveRoute(areaName, sLat, sLon, eLat, eLon, routePoints) {
    const points = routePoints.map((p, idx) => ({
        order: idx,
        latitude: p.latitude,
        longitude: p.longitude,
        point_type: { start: "начальная", end: "конечная", cluster: "промежуточная" }[p.type] || "промежуточная",
    }));

    fetch("/api/routes/", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCookie("csrftoken"),
        },
        body: JSON.stringify({
            area_name: areaName,
            start_lat: sLat,
            start_lon: sLon,
            end_lat:   eLat,
            end_lon:   eLon,
            points,
        }),
    })
    .then(res => res.json())
    .then(saved => drawSavedRoute(saved))
    .catch(err => console.error("Ошибка сохранения маршрута:", err));
}

document.getElementById("run-btn").addEventListener("click", () => {
    const areaId   = document.getElementById("water-area-select").value;
    const iceClass = document.getElementById("ice-class-select").value;

    if (!areaId || !AppState.routeStart || !AppState.routeEnd) return;

    const areaName = document.getElementById("water-area-select")
        .options[document.getElementById("water-area-select").selectedIndex].text;

    clearRoute();
    setStatus("Запуск...", 0);
    document.getElementById("run-btn").disabled = true;

    const { lat: sLat, lng: sLon } = AppState.routeStart;
    const { lat: eLat, lng: eLon } = AppState.routeEnd;

    const dlat = (eLat - sLat) * Math.PI / 180;
    const dlon = (eLon - sLon) * Math.PI / 180;
    const sinDlat = Math.sin(dlat / 2);
    const sinDlon = Math.sin(dlon / 2);
    const a = sinDlat * sinDlat + Math.cos(sLat * Math.PI / 180) * Math.cos(eLat * Math.PI / 180) * sinDlon * sinDlon;
    const distKm = 6371 * 2 * Math.asin(Math.sqrt(a));
    if (distKm < 1.0) {
        setStatus("Начальная и конечная точки слишком близко, учитывайте минимальное расстояние в 1 км");
        document.getElementById("run-btn").disabled = false;
        return;
    }

    const url = `/api/route-progress/?water_area=${areaId}&ice_class=${iceClass}&start_lat=${sLat}&start_lon=${sLon}&end_lat=${eLat}&end_lon=${eLon}`;
    const es = new EventSource(url);

    es.onmessage = (event) => {
        const data = JSON.parse(event.data);

        if (data.type === "progress") {
            setStatus(data.msg, data.pct);

        } else if (data.type === "done") {
            es.close();
            document.getElementById("run-btn").disabled = false;

            const route = data.route;
            if (!route || route.length === 0) {
                setStatus("Маршрут не найден, т.к все зоны непроходимы для данного класса судна", undefined, true);
                return;
            }

            saveRoute(areaName, sLat, sLon, eLat, eLon, route);
            setStatus(`Маршрут построен (${route.length} точек)`);


        } else if (data.type === "warning") {
            es.close();
            document.getElementById("run-btn").disabled = false;
            setStatus(data.msg);

        } else if (data.type === "error") {
            es.close();
            document.getElementById("run-btn").disabled = false;
            setStatus("Ошибка: " + data.msg, undefined, true);
        }
    };

    es.onerror = () => {
        es.close();
        document.getElementById("run-btn").disabled = false;
        setStatus("Ошибка соединения", undefined, true);
    };
});

document.getElementById("clear-routes-btn").addEventListener("click", () => {
    const areaName = document.getElementById("water-area-select")
        .options[document.getElementById("water-area-select").selectedIndex].text;

    if (!areaName || !confirm(`Удалить все маршруты для акватории "${areaName}"?`)) return;

    fetch(`/api/routes/clear/?area_name=${encodeURIComponent(areaName)}`, {
        method: "DELETE",
        headers: { "X-CSRFToken": getCookie("csrftoken") },
    })
    .then(res => res.json())
    .then(data => {
        clearSavedRoutes();
        setStatus(`Удалено маршрутов: ${data.deleted}`);
    });
});