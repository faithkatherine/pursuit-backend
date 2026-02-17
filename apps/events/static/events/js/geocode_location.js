document.addEventListener('DOMContentLoaded', function () {
    const locationField = document.getElementById('id_location_name');
    if (!locationField) return;

    // Create search button
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.textContent = 'Find on map';
    btn.style.cssText = 'margin-left: 8px; padding: 4px 12px; cursor: pointer;';
    locationField.parentNode.insertBefore(btn, locationField.nextSibling);

    btn.addEventListener('click', function () {
        const query = locationField.value.trim();
        if (!query) return;

        btn.textContent = 'Searching...';
        btn.disabled = true;

        fetch('https://nominatim.openstreetmap.org/search?format=json&limit=1&email=admin@pursuit.app&q=' + encodeURIComponent(query))
            .then(function (res) {
                if (!res.ok) throw new Error('HTTP ' + res.status);
                return res.json();
            })
            .then(function (data) {
                if (!data.length) {
                    alert('Location not found. Try a more specific address.');
                    return;
                }

                const lat = parseFloat(data[0].lat);
                const lon = parseFloat(data[0].lon);

                // Transform coordinates to the map's projection (EPSG:3857)
                const coords = ol.proj.fromLonLat([lon, lat]);

                // Find the MapWidget instance via the hidden textarea
                const geoInput = document.getElementById('id_location');
                if (!geoInput) return;

                // Find the map container — it's the div with id ending in '_map'
                const mapDiv = document.getElementById('id_location_map');
                if (!mapDiv) return;

                // Get all ol.Map instances by looking at the map target
                const maps = document.querySelectorAll('.ol-viewport');
                for (var i = 0; i < maps.length; i++) {
                    var viewport = maps[i];
                    if (mapDiv.contains(viewport) || mapDiv === viewport.parentElement) {
                        // We found our map's viewport
                        break;
                    }
                }

                // Create the point geometry in GeoJSON (the format Django's widget uses)
                var point = new ol.geom.Point(coords);
                var geojson = new ol.format.GeoJSON();
                geoInput.value = geojson.writeGeometry(point);

                // Trigger a change event so Django picks it up
                geoInput.dispatchEvent(new Event('change'));

                // Try to access the map to center it and add the feature visually
                // Django's MapWidget stores itself — we need to find it
                // The widget creates the map on the div with id 'id_location_map'
                if (typeof geodjango_location !== 'undefined') {
                    // geodjango_location is the MapWidget instance
                    var widget = geodjango_location;
                    widget.map.getView().setCenter(coords);
                    widget.map.getView().setZoom(15);

                    // Clear existing features and add the new point
                    widget.featureCollection.clear();
                    var feature = new ol.Feature({ geometry: point });
                    widget.featureOverlay.getSource().addFeature(feature);
                    widget.serializeFeatures();
                    widget.disableDrawing();
                }
            })
            .catch(function (err) {
                console.error('Geocoding error:', err);
                alert('Geocoding request failed: ' + err.message);
            })
            .finally(function () {
                btn.textContent = 'Find on map';
                btn.disabled = false;
            });
    });
});
