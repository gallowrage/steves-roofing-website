let map2D;
let geocoder;
let markers = [];
let polygon2D;
let isClosed = false;
let lastFlatAreaSqFt = 0; // flat footprint area from the last closed trace, reapplied when pitch changes
let lastGeocodedLocation = null; // { lat, lng } of the last successfully searched address

// Configurable Cloud Function endpoint
const AI_VISUALIZER_FUNCTION_URL = window.AI_VISUALIZER_FUNCTION_URL || "/api/generateRoofVisualization";

// --- 3D Product Preview state ---
let map3D;
let polygon3D;
let ridgeLine3D;
let is3DAvailable = false;

// Base hex colors matching the panelColor dropdown; alpha suffixes applied when used as fill/stroke
const panelColorHex = {
    "Galvalume": "#95a5a6",
    "Charcoal Gray": "#2c3e50",
    "Burnished Slate": "#3e2723",
    "Crimson Red": "#c0392b",
    "Hunter Green": "#27ae60",
    "Matte Black": "#111111"
};

// Reflects the selected panel color onto the 3D roof plane and ridge cap line, if the 3D preview is available
function updateRoofColor3D() {
    if (!is3DAvailable || !polygon3D) return;
    const hex = panelColorHex[document.getElementById('panelColor').value] || panelColorHex["Galvalume"];
    polygon3D.fillColor = hex + "CC"; // ~80% opacity
    polygon3D.strokeColor = hex + "FF";
    if (ridgeLine3D) ridgeLine3D.strokeColor = hex + "FF";
}

// Drapes the traced roof footprint as a flat, product-colored plane at an illustrative eave height (not a
// survey-accurate elevation), with a pitch-estimated ridge line along the footprint's long axis for a real
// roof silhouette instead of a flat lid, then frames the 3D camera on it
function syncRoof3D(path, pitchMultiplier, bounds, heightMeters, widthMeters) {
    if (!is3DAvailable || !polygon3D || !map3D) return;
    const eaveHeightMeters = 4.5;
    const minDimMeters = Math.min(heightMeters, widthMeters);
    const maxDimMeters = Math.max(heightMeters, widthMeters);
    const ridgeRiseMeters = (minDimMeters / 2) * (pitchMultiplier - 1) * 2;
    const ridgeHeightMeters = eaveHeightMeters + ridgeRiseMeters;
    
    polygon3D.path = path.getArray().map(ll => ({ lat: ll.lat(), lng: ll.lng(), altitude: eaveHeightMeters }));
    
    const ne = bounds.getNorthEast();
    const sw = bounds.getSouthWest();
    const midLat = (ne.lat() + sw.lat()) / 2;
    const midLng = (ne.lng() + sw.lng()) / 2;
    ridgeLine3D.path = heightMeters >= widthMeters
        ? [{ lat: sw.lat(), lng: midLng, altitude: ridgeHeightMeters }, { lat: ne.lat(), lng: midLng, altitude: ridgeHeightMeters }]
        : [{ lat: midLat, lng: sw.lng(), altitude: ridgeHeightMeters }, { lat: midLat, lng: ne.lng(), altitude: ridgeHeightMeters }];
    
    updateRoofColor3D();
    
    const center = bounds.getCenter();
    map3D.center = { lat: center.lat(), lng: center.lng(), altitude: eaveHeightMeters };
    map3D.range = Math.max(80, maxDimMeters * 1.8);
    map3D.tilt = 55;
}

// Shared bounding-box/complexity heuristic for lineal footage, used for both Solar API and hand-traced footprints
function estimateRoofLineals(maxDimFt, minDimFt, complexityTier) {
    let eaves = 0, ridges = 0, rakes = 0, valleys = 0;

    if (complexityTier <= 2) {
        // Gable estimate
        eaves = maxDimFt * 2;
        ridges = maxDimFt;
        rakes = minDimFt * 2;
    } else if (complexityTier <= 4) {
        // Hip estimate
        eaves = (maxDimFt + minDimFt) * 2;
        ridges = Math.max(0, maxDimFt - minDimFt);
        valleys = minDimFt * 2.5; // Hips
    } else {
        // Complex estimate
        eaves = (maxDimFt + minDimFt) * 2.5;
        ridges = maxDimFt * 1.5;
        rakes = minDimFt * 1.5;
        valleys = minDimFt * 2;
    }

    return { eaves, ridges, rakes, valleys };
}

async function initMap() {
    // Import libraries
    const { Map } = await google.maps.importLibrary("maps");
    const { Geocoder } = await google.maps.importLibrary("geocoding");
    
    geocoder = new Geocoder();
    const defaultCenter = { lat: 35.5951, lng: -82.5515 };



    // --- 2D Map Setup (For Measurement) ---
    map2D = new Map(document.getElementById("map2d-container"), {
        zoom: 19,
        center: defaultCenter,
        mapTypeId: "satellite",
        tilt: 0,
        mapId: "DEMO_MAP_ID"
    });

    polygon2D = new google.maps.Polygon({
        map: map2D,
        paths: [],
        strokeColor: "#73000A",
        strokeOpacity: 0.8,
        strokeWeight: 3,
        fillColor: "#73000A",
        fillOpacity: 0.3,
        clickable: false
    });

    // 2D Drawing logic
    const { AdvancedMarkerElement, PinElement } = await google.maps.importLibrary("marker");
    map2D.addListener("click", (e) => {
        if (isClosed) return;
        addPoint(e.latLng, AdvancedMarkerElement, PinElement);
    });

    // --- 3D Product Preview Setup (best-effort; the 2D tool still works if this fails) ---
    try {
        const { Map3DElement, Polygon3DElement, Polyline3DElement } = await google.maps.importLibrary("maps3d");
        map3D = new Map3DElement({
            center: { lat: defaultCenter.lat, lng: defaultCenter.lng, altitude: 0 },
            range: 200,
            tilt: 65,
            heading: 0,
            mode: "HYBRID"
        });
        document.getElementById('map3d-container').appendChild(map3D);

        polygon3D = new Polygon3DElement({
            strokeWidth: 3,
            extruded: false,
            altitudeMode: "RELATIVE_TO_GROUND",
            drawsOccludedSegments: true
        });
        map3D.append(polygon3D);

        ridgeLine3D = new Polyline3DElement({
            strokeWidth: 6,
            altitudeMode: "RELATIVE_TO_GROUND",
            drawsOccludedSegments: true
        });
        map3D.append(ridgeLine3D);

        updateRoofColor3D();
        is3DAvailable = true;
    } catch (error) {
        console.warn("3D Product Preview unavailable:", error);
        document.getElementById('tab3dBtn').disabled = true;
        document.getElementById('tab3dBtn').title = "3D preview is unavailable in this browser/session";
    }

    // --- Map Tabs (2D Measurement / 3D Product Preview / AI Roof Visualizer) ---
    function showTab(tab) {
        const panels = {
            tab2dBtn: ['map2d-container', 'controls2d'],
            tab3dBtn: ['map3d-container', 'controls3d'],
            tabAiBtn: ['aiVisualizerContainer', 'controlsAi']
        };
        Object.keys(panels).forEach(btnId => {
            const isActive = btnId === tab;
            document.getElementById(btnId).classList.toggle('active-tab', isActive);
            panels[btnId].forEach(elId => document.getElementById(elId).classList.toggle('hidden', !isActive));
        });
    }
    document.getElementById('tab2dBtn').addEventListener('click', () => showTab('tab2dBtn'));
    document.getElementById('tab3dBtn').addEventListener('click', () => {
        if (!is3DAvailable) return;
        showTab('tab3dBtn');
    });
    document.getElementById('tabAiBtn').addEventListener('click', () => showTab('tabAiBtn'));

    // --- AI Roof Visualizer ---
    document.getElementById('generateAiBtn').addEventListener('click', async () => {
        if (!lastGeocodedLocation) {
            alert("Please search for the customer's address first, then come back to this tab.");
            return;
        }
        const generateBtn = document.getElementById('generateAiBtn');
        const placeholder = document.getElementById('aiVisualizerPlaceholder');
        const resultImg = document.getElementById('aiVisualizerImage');
        const source = document.querySelector('input[name="aiSource"]:checked').value;

        generateBtn.disabled = true;
        resultImg.classList.add('hidden');
        placeholder.classList.remove('hidden');
        placeholder.innerText = "Generating AI visualization\u2026 this can take up to 30 seconds.";

        try {
            const response = await fetch(AI_VISUALIZER_FUNCTION_URL, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    lat: lastGeocodedLocation.lat,
                    lng: lastGeocodedLocation.lng,
                    source,
                    material: document.getElementById('panelStyle').value,
                    color: document.getElementById('panelColor').value
                })
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || `Request failed (HTTP ${response.status})`);

            resultImg.src = `data:${data.mimeType};base64,${data.imageBase64}`;
            resultImg.classList.remove('hidden');
            placeholder.classList.add('hidden');
        } catch (error) {
            console.error("AI visualization failed:", error); // technical detail stays in the console, not on screen
            placeholder.innerText = "Sorry, that didn't work. Please try again, or use the 3D Preview tab instead.";
        } finally {
            generateBtn.disabled = false;
        }
    });

    // --- Search Logic ---
    document.getElementById("searchBtn").addEventListener("click", () => {
        const address = document.getElementById("addressInput").value;
        if (!address) return;
        
        const searchBtn = document.getElementById("searchBtn");
        searchBtn.disabled = true; // Avoid duplicate billed Geocoding/Solar API calls from rapid clicks
        
        geocoder.geocode({ address: address }, async (results, status) => {
            searchBtn.disabled = false;
            if (status === "OK") {
                const loc = results[0].geometry.location;
                lastGeocodedLocation = { lat: loc.lat(), lng: loc.lng() };

                // Move 2D map
                map2D.setCenter(loc);
                
                // Reframe the 3D preview on the searched address too
                if (is3DAvailable && map3D) {
                    map3D.center = { lat: loc.lat(), lng: loc.lng(), altitude: 0 };
                    map3D.range = 200;
                    map3D.tilt = 65;
                    map3D.heading = 0;
                }
                
                // Fetch Solar API Data for Building Insights
                try {
                    const apiKey = window.GOOGLE_MAPS_API_KEY || "";
                    const solarUrl = `https://solar.googleapis.com/v1/buildingInsights:findClosest?location.latitude=${loc.lat()}&location.longitude=${loc.lng()}&requiredQuality=HIGH&key=${apiKey}`;
                    const response = await fetch(solarUrl);
                    const data = await response.json();
                    
                    if (data && data.solarPotential && data.solarPotential.wholeRoofStats) {
                        const areaSqMeters = data.solarPotential.wholeRoofStats.areaMeters2;
                        const areaSqFt = areaSqMeters * 10.7639;
                        const roundedArea = Math.round(areaSqFt);
                        
                        document.getElementById('roofArea').value = roundedArea;
                        
                        // Smart Estimation of Lineals using Bounding Box and Segments
                        const { spherical } = await google.maps.importLibrary("geometry");
                        const sw = data.boundingBox.sw;
                        const ne = data.boundingBox.ne;
                        
                        const swLatLng = new google.maps.LatLng(sw.latitude, sw.longitude);
                        const nwLatLng = new google.maps.LatLng(ne.latitude, sw.longitude);
                        const seLatLng = new google.maps.LatLng(sw.latitude, ne.longitude);
                        
                        const heightMeters = spherical.computeDistanceBetween(swLatLng, nwLatLng);
                        const widthMeters = spherical.computeDistanceBetween(swLatLng, seLatLng);
                        
                        const maxDimFt = Math.max(heightMeters, widthMeters) * 3.28084;
                        const minDimFt = Math.min(heightMeters, widthMeters) * 3.28084;
                        
                        const segments = data.solarPotential.roofSegmentStats.length;
                        const { eaves, ridges, rakes, valleys } = estimateRoofLineals(maxDimFt, minDimFt, segments);
                        
                        document.getElementById('eaveLength').value = Math.round(eaves);
                        document.getElementById('ridgeLength').value = Math.round(ridges);
                        document.getElementById('rakeLength').value = Math.round(rakes);
                        document.getElementById('valleyLength').value = Math.round(valleys);
                        
                        document.getElementById('areaText').innerText = `Area: ${roundedArea} Sq Ft (Solar AI Estimated Lineals)`;
                        
                        console.log("Solar API Roof Stats:", data.solarPotential);
                    } else if (data.error) {
                        console.warn("Solar API returned an error:", data.error.message);
                    }
                } catch (error) {
                    console.error("Error fetching Solar API data:", error);
                }
            } else {
                alert("Geocode was not successful: " + status);
            }
        });
    });



    // --- 2D Clear Shape ---
    document.getElementById('clearBtn').addEventListener('click', () => {
        markers.forEach(marker => marker.map = null);
        markers = [];
        isClosed = false;
        lastFlatAreaSqFt = 0;
        polygon2D.setPath([]);
        document.getElementById('perimeterText').innerText = "Perimeter: 0 LF";
        document.getElementById('areaText').innerText = "Area: 0 Sq Ft";
        if (is3DAvailable && polygon3D) polygon3D.path = [];
        if (is3DAvailable && ridgeLine3D) ridgeLine3D.path = [];
    });

    // --- Takeoff Calculation ---
    document.getElementById("calculateBtn").addEventListener("click", () => {
        if (!isClosed) {
            const proceed = confirm("No roof outline has been traced on the map. Generate the proposal using the manually entered measurements instead?");
            if (!proceed) return;
        }
        generateExactTakeoff();
    });
}

// --- 2D Drawing Functions ---
function addPoint(position, AdvancedMarkerElement, PinElement) {
    const isFirstPoint = markers.length === 0;
    
    const pin = new PinElement({
        background: isFirstPoint ? "#f1c40f" : "#73000A",
        borderColor: isFirstPoint ? "#f39c12" : "#000000",
        glyphColor: "white",
        scale: 0.8
    });

    const marker = new AdvancedMarkerElement({
        map: map2D,
        position: position,
        content: pin.element,
        gmpClickable: true
    });

    marker.addListener("click", async () => {
        if (markers.length >= 3 && marker === markers[0] && !isClosed) {
            isClosed = true;
            updatePolygon2D();
            const closedPin = new PinElement({ background: "#73000A", borderColor: "#000000", glyphColor: "white", scale: 0.8 });
            markers[0].content = closedPin.element;
            
            await calculateMapMeasurements();
        }
    });

    markers.push(marker);
    updatePolygon2D();
}

async function calculateMapMeasurements() {
    if (!isClosed || !polygon2D) return;
    const { spherical } = await google.maps.importLibrary("geometry");
    const path = polygon2D.getPath();
    
    const areaSqMeters = spherical.computeArea(path);
    const perimeterMeters = spherical.computeLength(path);
    
    const flatAreaSqFt = areaSqMeters * 10.7639;
    const pitchMultiplier = parseFloat(document.getElementById('roofPitch').value) || 1.12;
    const areaSqFt = flatAreaSqFt * pitchMultiplier;
    
    const perimeterFt = perimeterMeters * 3.28084;
    
    document.getElementById('areaText').innerText = `Area: ${Math.round(areaSqFt)} Sq Ft`;
    document.getElementById('perimeterText').innerText = `Perimeter: ${Math.round(perimeterFt)} LF`;
    
    // Auto-fill form
    lastFlatAreaSqFt = flatAreaSqFt;
    document.getElementById('roofArea').value = Math.round(areaSqFt);
    
    // Same bounding-box/complexity heuristic used for the Solar API path, driven off the traced footprint
    const bounds = new google.maps.LatLngBounds();
    path.forEach(latLng => bounds.extend(latLng));
    const ne = bounds.getNorthEast();
    const sw = bounds.getSouthWest();
    const nwLatLng = new google.maps.LatLng(ne.lat(), sw.lng());
    const heightMeters = spherical.computeDistanceBetween(sw, nwLatLng);
    const widthMeters = spherical.computeDistanceBetween(nwLatLng, ne);
    const maxDimFt = Math.max(heightMeters, widthMeters) * 3.28084;
    const minDimFt = Math.min(heightMeters, widthMeters) * 3.28084;
    
    // Vertex count of the traced corners stands in for Solar API's roof segment count
    const vertexCount = markers.length;
    const complexityTier = vertexCount <= 4 ? 2 : (vertexCount <= 6 ? 4 : 6);
    const { eaves, ridges, rakes, valleys } = estimateRoofLineals(maxDimFt, minDimFt, complexityTier);
    
    document.getElementById('eaveLength').value = Math.round(eaves);
    document.getElementById('ridgeLength').value = Math.round(ridges);
    document.getElementById('rakeLength').value = Math.round(rakes);
    document.getElementById('valleyLength').value = Math.round(valleys);
    
    // Project the traced footprint onto the 3D preview, colored with the selected product
    syncRoof3D(path, pitchMultiplier, bounds, heightMeters, widthMeters);
    
    // Also auto-recalculate the final quote
    generateExactTakeoff();
}

// Pitch affects sloped area only; re-apply it to the last traced footprint without touching lineal measurements
document.getElementById('roofPitch').addEventListener('change', () => {
    if (lastFlatAreaSqFt > 0) {
        const pitchMultiplier = parseFloat(document.getElementById('roofPitch').value) || 1.12;
        const areaSqFt = lastFlatAreaSqFt * pitchMultiplier;
        document.getElementById('roofArea').value = Math.round(areaSqFt);
        document.getElementById('areaText').innerText = `Area: ${Math.round(areaSqFt)} Sq Ft`;
    }
    generateExactTakeoff();
});

// Update visibility of the Over-Shingle Recover Advantage badge
function updatePurlinSavingsBadge() {
    const isTearOff = document.getElementById('isTearOff').checked;
    const panelStyle = document.getElementById('panelStyle').value;
    const badge = document.getElementById('purlinSavingsBadge');
    if (!badge) return;
    if (isTearOff || panelStyle === 'shingles') {
        badge.style.display = 'none';
    } else {
        badge.style.display = 'block';
    }
}

// Bind remaining inputs to instantly update the proposal (these don't affect geometry, so never overwrite traced measurements)
['complexity', 'panelStyle', 'panelColor', 'isTearOff'].forEach(id => {
    document.getElementById(id).addEventListener('change', () => {
        updatePurlinSavingsBadge();
        generateExactTakeoff();
    });
});

// Panel color changes should also instantly recolor the 3D roof preview
document.getElementById('panelColor').addEventListener('change', updateRoofColor3D);

['roofArea', 'eaveLength', 'ridgeLength', 'rakeLength', 'valleyLength'].forEach(id => {
    document.getElementById(id).addEventListener('input', () => {
        generateExactTakeoff();
    });
});

function updatePolygon2D() {
    const path = markers.map(m => m.position);
    if (isClosed && path.length > 0) path.push(path[0]);
    polygon2D.setPath(path);
}

// --- Digital Signature Pad State & Handlers ---
let isDrawing = false;
let hasSignature = false;
const sigCanvas = document.getElementById('signatureCanvas');
const sigCtx = sigCanvas ? sigCanvas.getContext('2d') : null;

function getCanvasCoordinates(e) {
    if (!sigCanvas) return { x: 0, y: 0 };
    const rect = sigCanvas.getBoundingClientRect();
    const scaleX = sigCanvas.width / rect.width;
    const scaleY = sigCanvas.height / rect.height;
    const clientX = e.clientX ?? (e.touches && e.touches[0] ? e.touches[0].clientX : 0);
    const clientY = e.clientY ?? (e.touches && e.touches[0] ? e.touches[0].clientY : 0);
    return {
        x: (clientX - rect.left) * scaleX,
        y: (clientY - rect.top) * scaleY
    };
}

function handlePointerDown(e) {
    if (!sigCtx) return;
    isDrawing = true;
    hasSignature = true;
    const { x, y } = getCanvasCoordinates(e);
    sigCtx.beginPath();
    sigCtx.moveTo(x, y);
    sigCtx.strokeStyle = '#0d47a1';
    sigCtx.lineWidth = 2.5;
    sigCtx.lineCap = 'round';
    sigCtx.lineJoin = 'round';

    const placeholder = document.getElementById('sigPlaceholder');
    if (placeholder) placeholder.style.display = 'none';

    const statusLabel = document.getElementById('sigStatusLabel');
    if (statusLabel) {
        statusLabel.innerText = 'Signed & Verified';
        statusLabel.style.color = '#2e7d32';
    }
    const timestamp = document.getElementById('signedTimestamp');
    if (timestamp) {
        timestamp.innerText = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }
}

function handlePointerMove(e) {
    if (!isDrawing || !sigCtx) return;
    e.preventDefault();
    const { x, y } = getCanvasCoordinates(e);
    sigCtx.lineTo(x, y);
    sigCtx.stroke();
}

function handlePointerUp() {
    if (isDrawing && sigCtx) {
        isDrawing = false;
        sigCtx.closePath();
    }
}

if (sigCanvas) {
    sigCanvas.addEventListener('pointerdown', handlePointerDown);
    sigCanvas.addEventListener('pointermove', handlePointerMove);
    sigCanvas.addEventListener('pointerup', handlePointerUp);
    sigCanvas.addEventListener('pointercancel', handlePointerUp);
    sigCanvas.addEventListener('pointerleave', handlePointerUp);
}

const clearSignatureBtn = document.getElementById('clearSignatureBtn');
if (clearSignatureBtn) {
    clearSignatureBtn.addEventListener('click', () => {
        if (!sigCtx) return;
        sigCtx.clearRect(0, 0, sigCanvas.width, sigCanvas.height);
        hasSignature = false;
        const placeholder = document.getElementById('sigPlaceholder');
        if (placeholder) placeholder.style.display = 'block';
        const statusLabel = document.getElementById('sigStatusLabel');
        if (statusLabel) {
            statusLabel.innerText = 'Unsigned';
            statusLabel.style.color = '#c0392b';
        }
        const timestamp = document.getElementById('signedTimestamp');
        if (timestamp) timestamp.innerText = '';
        const printImg = document.getElementById('printSignatureImg');
        if (printImg) {
            printImg.src = '';
            printImg.classList.add('hidden');
        }
    });
}

// Steve's Contractor Pro View Toggle
const toggleContractorProBtn = document.getElementById('toggleContractorProBtn');
const contractorProSection = document.getElementById('contractorProSection');
if (toggleContractorProBtn && contractorProSection) {
    toggleContractorProBtn.addEventListener('click', () => {
        contractorProSection.classList.toggle('hidden');
        const isHidden = contractorProSection.classList.contains('hidden');
        toggleContractorProBtn.innerText = isHidden ?
            "🛠️ Toggle Steve's Contractor Pro View (Wholesale & Cut-Lists)" :
            "👁️ Hide Steve's Contractor Pro View (Customer Mode)";
    });
}

// --- Takeoff Calculation ---
function generateExactTakeoff() {
    // Inputs (clamped to non-negative so a stray minus sign can't produce a negative-priced proposal)
    const area = Math.max(0, parseFloat(document.getElementById('roofArea').value) || 0);
    const eaves = Math.max(0, parseFloat(document.getElementById('eaveLength').value) || 0);
    const ridges = Math.max(0, parseFloat(document.getElementById('ridgeLength').value) || 0);
    const rakes = Math.max(0, parseFloat(document.getElementById('rakeLength').value) || 0);
    const valleys = Math.max(0, parseFloat(document.getElementById('valleyLength').value) || 0);
    
    const panelStyle = document.getElementById('panelStyle').value;
    const color = document.getElementById('panelColor').value;
    
    const isStandingSeam = panelStyle === 'standing_seam';
    const isShingles = panelStyle === 'shingles';

    // BestBuy Metals / Shingle Exact Pricing Logic
    let panelCostPerSqFt = 1.85;
    if (isStandingSeam) panelCostPerSqFt = 3.50;
    if (isShingles) panelCostPerSqFt = 1.20; // Avg cost per sqft for Architectural Shingles
    
    // Base waste comes from the Roof Complexity selection; valleys/hips add a bounded amount more
    const complexityWaste = parseFloat(document.getElementById('complexity').value) || 1.10;
    let wasteMultiplier = complexityWaste;
    if (valleys > 0 && area > 0) wasteMultiplier += Math.min((valleys / area) * 2, 0.10);
    const billableArea = area * wasteMultiplier;
    
    // Calculate Trim Costs (Lineal Feet)
    const eaveTrimCost = isShingles ? (eaves * 1.50) : (eaves * (isStandingSeam ? 4.50 : 2.50)); 
    const ridgeCapCost = isShingles ? (ridges * 2.00) : (ridges * (isStandingSeam ? 6.50 : 3.50)); 
    const rakeTrimCost = isShingles ? (rakes * 1.50) : (rakes * (isStandingSeam ? 5.50 : 3.00)); 
    const valleyTrimCost = isShingles ? (valleys * 2.50) : (valleys * (isStandingSeam ? 7.00 : 4.00)); 
    
    // Accessories
    const underlaymentRolls = Math.ceil(billableArea / 1000);
    const underlaymentCost = underlaymentRolls * 150.00; // Over existing shingles
    
    // Best Buy Metals Cut-Lists & Geometry
    // Panel coverage width: 36" (3.0 ft) for 29ga Tuff-Rib; 16" (1.333 ft) for 26ga Standing Seam
    const coverageWidth = isStandingSeam ? 1.3333 : 3.0;
    const panelQuantity = eaves > 0 ? Math.ceil(eaves / coverageWidth) : 0;
    
    // True Rake slope length: use measured rakes or area/eaves heuristic
    const trueRakeLength = rakes > 0 ? (rakes >= 24 ? rakes / 4 : rakes / 2) : (area > 0 && eaves > 0 ? area / eaves : 16);
    // Panel Cut Length: True Rake + 0.166 ft (2" overhang) - 0.083 ft (1" ridge clearance)
    const panelCutLength = trueRakeLength + 0.166 - 0.083;
    
    // Steve's Over-Shingle Purlin Recover Framing (Rule 3)
    // 1x4 wood purlin framing spaced at maximum 24 inches on-center over existing shingles
    const isTearOff = document.getElementById('isTearOff').checked;
    let purlinLF = 0;
    let purlinCost = 0;
    let purlinRows = 0;
    if (!isShingles && !isTearOff) {
        purlinRows = Math.ceil(trueRakeLength / 2.0) + 1; // starter row at eave + 24" O.C.
        purlinLF = purlinRows * eaves;
        purlinCost = purlinLF * 0.45; // $0.45 per LF for 1x4 wood
    }
    
    let fastenerCost = 0;
    let fastenerDesc = "";
    if (isShingles) {
        const boxesNeeded = Math.ceil(billableArea / 500); 
        fastenerCost = boxesNeeded * 45.00; 
        fastenerDesc = `${boxesNeeded} Boxes of Coil Nails`;
    } else if (isStandingSeam) {
        const clipsNeeded = Math.ceil(billableArea / 3); 
        fastenerCost = clipsNeeded * 0.45; 
        fastenerDesc = `${clipsNeeded} Concealed Pancake Clips`;
    } else {
        const screwsNeeded = Math.ceil(billableArea * 0.8); 
        fastenerCost = screwsNeeded * 0.15; 
        fastenerDesc = `${screwsNeeded} Color-Matched Woodgrip Screws`;
    }
    
    const sealantTubes = Math.max(2, Math.ceil((valleys + ridges) / 20));
    const sealantCost = sealantTubes * 9.50;

    const totalPanelCost = billableArea * panelCostPerSqFt;
    const totalMaterialsCost = totalPanelCost + eaveTrimCost + ridgeCapCost + rakeTrimCost + valleyTrimCost + underlaymentCost + purlinCost + fastenerCost + sealantCost;

    // --- Retail Pricing & Labor ---
    // Business Rule: Materials should always be 1/3 of the total retail price.
    // Total Price = Total Materials * 3
    const retailPrice = totalMaterialsCost * 3;
    
    // Internal tracking (hidden from customer)
    const totalLaborCost = totalMaterialsCost; // Assume 1/3 is labor
    const profitMargin = totalMaterialsCost; // Assume 1/3 is profit

    // Populate BOM
    const bomList = document.getElementById('bomList');
    bomList.innerHTML = '';
    let panelName = "29ga Ribbed Ag Panel";
    if (isStandingSeam) panelName = "26ga Standing Seam";
    if (isShingles) panelName = "CertainTeed Landmark Architectural Shingles";
    
    const panelBomText = isShingles ? 
        `${color} ${panelName}: ${Math.ceil(billableArea)} Sq Ft (incl. ${((wasteMultiplier-1)*100).toFixed(1)}% waste)` : 
        `${color} ${panelName}: ${Math.ceil(billableArea)} Sq Ft (incl. ${((wasteMultiplier-1)*100).toFixed(1)}% waste)`;
    
    const materials = [
        panelBomText,
        (!isShingles && panelQuantity > 0) ? `Best Buy Metals Custom Cut-List: ${panelQuantity} panels @ ${panelCutLength.toFixed(2)} ft` : null,
        `Eave Trim / Drip Edge: ${eaves} LF`,
        `Ridge Cap Assembly: ${ridges} LF`,
        `Rake / Gable Trim: ${rakes} LF`,
        valleys > 0 ? `W-Valley Flashing: ${valleys} LF` : null,
        `High-Temp Synthetic Underlayment: ${underlaymentRolls} rolls`,
        (!isShingles && !isTearOff) ? `1x4 Wood Purlins (Battens): ${purlinLF} LF (${purlinRows} runs @ 24" O.C.)` : null,
        fastenerDesc,
        `Polyurethane Sealant: ${sealantTubes} tubes`
    ];

    materials.forEach(item => {
        if (!item) return;
        const li = document.createElement('li');
        li.innerText = item;
        bomList.appendChild(li);
    });

    // Populate Scope
    const scopeList = document.getElementById('scopeList');
    scopeList.innerHTML = '';
    const scopeItems = [];
    
    if (isTearOff) {
        scopeItems.push(`Remove existing roof and dispose of`);
        scopeItems.push(`Inspect roof decking for rot or damage`);
        scopeItems.push(`Install Synthetic Underlayment`);
    } else {
        if (!isShingles) {
            scopeItems.push(`Install 1x4 wood purlin framing (24" on-center) directly over existing shingles`);
            scopeItems.push(`Over-Shingle Recover Applied: Customer saved $1,950 (Buncombe County dumpster $650 + Tear-off labor $1,300 eliminated)`);
        }
    }
    
    if (isShingles) {
        scopeItems.push(`Install ${color} ${panelName}`);
        scopeItems.push(`Install new custom metal drip edge around perimeter and all required flashings`);
    } else {
        scopeItems.push(`Install ${color} ${panelName} painted metal roofing (Cut-to-length)`);
        scopeItems.push(`Install new custom metal drip edge around perimeter and all required flashings`);
    }
    
    scopeItems.push(`Cleanup and haul away all debris from job`);
    scopeItems.forEach(item => {
        const li = document.createElement('li');
        li.innerText = item;
        scopeList.appendChild(li);
    });

    // Populate Display Fields
    document.getElementById('retailPrice').innerText = '$' + retailPrice.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
    document.getElementById('resCost').innerText = '$' + totalMaterialsCost.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
    document.getElementById('resLabor').innerText = '$' + totalLaborCost.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
    document.getElementById('resProfit').innerText = '$' + profitMargin.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
    
    // Inject current date into proposal form
    const today = new Date();
    document.getElementById('printDate').innerText = (today.getMonth() + 1) + '/' + today.getDate() + '/' + today.getFullYear();
    
    // Parse Google Maps address string (e.g., "123 Main St, Asheville, NC 28801, USA")
    const fullAddress = document.getElementById('addressInput').value || '';
    const parts = fullAddress.split(', ');
    
    if (parts.length >= 3) {
        document.getElementById('printAddressLine1').innerText = parts[0];
        document.getElementById('printAddressLine2').innerText = parts[1] + ', ' + parts[2];
        document.getElementById('printJobName').innerText = parts[1] + ', ' + parts[2].split(' ')[0]; // City, State
    } else {
        document.getElementById('printAddressLine1').innerText = fullAddress;
        document.getElementById('printAddressLine2').innerText = '';
        document.getElementById('printJobName').innerText = '';
    }
    
    document.getElementById('results').classList.remove('results-hidden');
}

// Preview & Print Logic
document.getElementById('previewBtn').addEventListener('click', () => {
    // If digital signature exists, transfer canvas image to printable img tag
    const printImg = document.getElementById('printSignatureImg');
    const printAcceptanceDate = document.getElementById('printAcceptanceDate');
    if (hasSignature && sigCanvas) {
        printImg.src = sigCanvas.toDataURL('image/png');
        printImg.classList.remove('hidden');
        const today = new Date();
        printAcceptanceDate.innerText = (today.getMonth() + 1) + '/' + today.getDate() + '/' + today.getFullYear();
    } else {
        printImg.classList.add('hidden');
        printAcceptanceDate.innerText = '';
    }

    // Copy the proposal content into the modal
    const proposalHtml = document.getElementById('proposalContent').innerHTML;
    document.getElementById('modalProposalContent').innerHTML = proposalHtml;
    
    // Remove internal wholesale block and interactive signature canvas from modal view
    const modalContent = document.getElementById('modalProposalContent');
    const internalBlock = modalContent.querySelector('#contractorProSection');
    if (internalBlock) internalBlock.remove();
    const noPrintItems = modalContent.querySelectorAll('.no-print');
    noPrintItems.forEach(el => el.remove());
    
    const header = modalContent.querySelector('.print-header');
    if (header) header.classList.remove('hidden');
    
    const grid = modalContent.querySelector('#printCustomerGrid');
    if (grid) grid.classList.remove('hidden');
    
    const fineprint = modalContent.querySelector('#printFinePrint');
    if (fineprint) fineprint.classList.remove('hidden');
    
    const signature = modalContent.querySelector('.signature-block');
    if (signature) signature.classList.remove('hidden');
    
    // Ensure signature image in modal has src
    if (hasSignature && sigCanvas) {
        const modalSigImg = modalContent.querySelector('#printSignatureImg');
        if (modalSigImg) {
            modalSigImg.src = sigCanvas.toDataURL('image/png');
            modalSigImg.classList.remove('hidden');
        }
    }
    
    // Show the modal
    document.getElementById('previewModal').classList.remove('hidden');
});

document.getElementById('closePreviewBtn').addEventListener('click', () => {
    document.getElementById('previewModal').classList.add('hidden');
});

document.getElementById('executePrintBtn').addEventListener('click', () => {
    window.print();
});

initMap();


