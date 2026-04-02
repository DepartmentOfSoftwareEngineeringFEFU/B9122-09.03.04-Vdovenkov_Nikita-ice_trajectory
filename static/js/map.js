const map = L.map("map").setView([50, 140], 5);

L.tileLayer("https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png", {
    attribution: "© OpenStreetMap © CARTO"
}).addTo(map);