const map = L.map("map").setView([50, 140], 5);

L.tileLayer("https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png", {
    attribution: "© OpenStreetMap © CARTO"
}).addTo(map);

const AppState = {
    trackLayer: null,
    areaLayer: null,
    startMarker: null,
    endMarker: null,
    drawnRect: null,
    drawnBounds: null,
    octagonPreview: null,
    circlePreviewLayer: null,
    drawMode: null,
    currentMode: "rect",
    selectedIceType: "light",
    iceLayers: {},
    routeStart: null,
    routeEnd: null,
    pickingMode: null,
    circleCenter: null,
};

const ICE_COLORS = {
    none:  { color: "#2196F3", fillColor: "#2196F3" },
    light: { color: "#4caf50", fillColor: "#4caf50" },
    heavy: { color: "#f44336", fillColor: "#f44336" },
};

const drawnItems = new L.FeatureGroup();
map.addLayer(drawnItems);

const drawControl = new L.Control.Draw({
    draw: {
        rectangle: true,
        polygon: false,
        polyline: false,
        circle: false,
        circlemarker: false,
        marker: false,
    },
    edit: { featureGroup: drawnItems }
});
map.addControl(drawControl);

function clearRoute() {
    if (AppState.trackLayer) {
        map.removeLayer(AppState.trackLayer);
        AppState.trackLayer = null;
    }
}