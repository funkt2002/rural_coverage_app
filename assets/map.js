const BASEMAPS = {
    light: "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
    streets: "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
    satellite: {
        version: 8,
        sources: {imagery: {type: "raster", tileSize: 256, maxzoom: 19, attribution: "Esri, Maxar, Earthstar Geographics",
                            tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"]}},
        layers: [{id: "imagery", type: "raster", source: "imagery"}],
    },
};

let map = null;
let ready = false; 
let current = {};  
let shown_county = null;
let shown_basemap = null;
let markers = [];


function add_layers() {  
    const data= current.data;
    const ramp= ["interpolate", ["linear"], ["get", "pop_night"]];
    data.ramp.forEach(([count, color]) => ramp.push(count, color));  // POP_RAMP stops from app.py, colors blend in between

    map.addSource("cells", {type: "geojson", data: `/data/${data.county}/cells.geojson`});
    map.addSource("border", {type: "geojson", data: `/data/${data.county}/boundary.geojson`});
    map.addLayer({id: "population", type: "fill", source: "cells", filter: [">=", ["get", "pop_night"], 1],
                  paint: {"fill-color": ramp, "fill-opacity": 0.8}});
    map.addLayer({id: "wildfire", type: "line", source: "cells", filter: [">=", ["get", "wildfires"], 1],
                  paint: {"line-color": data.colors.wildfire, "line-width": ["interpolate", ["linear"], ["zoom"], 8, 0.5, 12, 1.5]}});  // thin at county zoom so resident counts show
    map.addLayer({id: "border", type: "line", source: "border", paint: {"line-color": data.colors.border, "line-width": 2}});
    map.addLayer({id: "cells-hover", type: "fill", source: "cells", paint: {"fill-opacity": 0}});  // invisible, catches the mouse
}


function hover_popup() {
    const popup = new maplibregl.Popup({closeButton: false, closeOnClick: false});
    map.on("mousemove", "cells-hover", event => {
        const cell = event.features[0].properties;
        popup.setLngLat(event.lngLat).setHTML(`${Math.round(cell.pop_night).toLocaleString()} residents<br>${cell.wildfires} wildfires`).addTo(map);
    });
    map.on("mouseleave","cells-hover",() => popup.remove());
}


function station_marker(station) {
    const element = document.createElement("div");
    element.title = station.station + (station.closed ? ", closed" : ", open");
    element.className = station.closed ? "station closed" : "station open";
    if (station.closed) {
        element.innerHTML = `<span class="x">✕</span><span class="name">${station.label}</span>`;
        return new maplibregl.Marker({element: element, anchor: "left", offset: [-10, 0]}).setLngLat([station.lon, station.lat]);  // centers the X on the station
    }
    return new maplibregl.Marker({element: element}).setLngLat([station.lon, station.lat]);}


function apply() {
    const data = current.data;
    if (!map.getSource("cells")) { add_layers(); }
    if (shown_county !== data.county) { 
        map.getSource("cells").setData(`/data/${data.county}/cells.geojson`);
        map.getSource("border").setData(`/data/${data.county}/boundary.geojson`);
        map.jumpTo({center: data.center, zoom: data.zoom});
        shown_county = data.county;
    }

    markers.forEach(marker => marker.remove());
    markers = data.stations.map(station => station_marker(station).addTo(map));
    for (const layer of ["population", "wildfire", "border"]) {
        map.setLayoutProperty(layer, "visibility", current.layers.includes(layer) ? "visible" : "none");
    }
    const any_cells = current.layers.includes("population") || current.layers.includes("wildfire");
    map.setLayoutProperty("cells-hover", "visibility", any_cells ? "visible" : "none");
    map.getContainer().classList.toggle("hide-open", !current.layers.includes("open"));
    map.getContainer().classList.toggle("hide-closed", !current.layers.includes("closed"));
}


function draw(data, layers, basemap) {
    if (!data){ return null; }  // wait for the first plan from Dash
    current={data: data, layers: layers, basemap: basemap};

    if (!map) {
        map = new maplibregl.Map({container: "map", style: BASEMAPS[basemap], center: data.center, zoom: data.zoom});
        shown_county = data.county;
        shown_basemap = basemap;
        map.addControl(new maplibregl.NavigationControl({showCompass: false}));
        map.addControl(new maplibregl.ScaleControl({unit: "imperial"}), "bottom-left");
        map.on("style.load", () => { ready = true; apply(); });
        hover_popup();
        return null;
    }
    if (shown_basemap !== basemap) {
        ready = false;
        shown_basemap = basemap;
        map.setStyle(BASEMAPS[basemap], {diff: false});  // style.load puts our layers back
        return null;
    }
    if (ready) { apply(); }
    return null;
}


window.dash_clientside = Object.assign({}, window.dash_clientside, {maplibre: {draw: draw}});
