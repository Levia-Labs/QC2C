"use strict";
var __awaiter = (this && this.__awaiter) || function (thisArg, _arguments, P, generator) {
    function adopt(value) { return value instanceof P ? value : new P(function (resolve) { resolve(value); }); }
    return new (P || (P = Promise))(function (resolve, reject) {
        function fulfilled(value) { try { step(generator.next(value)); } catch (e) { reject(e); } }
        function rejected(value) { try { step(generator["throw"](value)); } catch (e) { reject(e); } }
        function step(result) { result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected); }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
    });
};
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.coordinatesToCountry = exports.getCountry = exports.getSector = void 0;
// Import point-in-polygon utility to check if a point lies inside a polygon
const point_in_polygon_1 = __importDefault(require("point-in-polygon"));
/**
 * Find which sector a coordinate falls into based on bounding boxes.
 *
 * Iterate through each sector in the manifest, checking if the coordinates
 * lie within the sector's bounding box.
 *
 * @param sectors_manifest - Object mapping sector keys to bounding box arrays [lat_min, lng_min, lat_max, lng_max].
 * @param coordinates - Coordinates as LatLng object.
 * @returns Sector key string if found; otherwise null.
 */
const getSector = (sectors_manifest, coordinates) => {
    // Iterate through each sector entry in the manifest
    for (const [key, bounds] of Object.entries(sectors_manifest)) {
        // Destructure the bounding box into min/max latitudes and longitudes
        // Accept a bare bounds array or an object carrying a "bounds" entry
        const [lat_min, lng_min, lat_max, lng_max] = Array.isArray(bounds)
            ? bounds
            : bounds.bounds;
        // Check if the coordinate lies within the bounding box
        if (lat_min <= coordinates.lat &&
            coordinates.lat <= lat_max &&
            lng_min <= coordinates.lng &&
            coordinates.lng <= lng_max) {
            // Return the sector key if coordinate is inside the bounding box
            return key;
        }
    }
    // Return null if no sector contains the coordinate
    return null;
};
exports.getSector = getSector;
/**
 * Determine the country within a sector by testing polygons.
 *
 * Represent the coordinate as an array and iterate through each country's polygon
 * to check if the coordinate lies inside.
 *
 * @param sector_manifest - Object mapping country keys to polygon coordinate arrays.
 * @param coordinates - Coordinates as LatLng object.
 * @returns Country key string if found; otherwise null.
 */
const getCountry = (sector_manifest, coordinates) => {
    // Represent coordinate as an array to match point-in-polygon input format
    const point = [coordinates.lat, coordinates.lng];
    // Iterate through each country's polygon in the sector manifest
    for (const [key, value] of Object.entries(sector_manifest)) {
        // Accept a single polygon or a list of polygons (multipolygon)
        const polygons = Array.isArray(value) && Array.isArray(value[0]) && typeof value[0][0] === "number"
            ? [value]
            : value;
        // Return the country key if the point lies inside any polygon
        if (polygons.some((polygon) => (0, point_in_polygon_1.default)(point, polygon))) {
            return key;
        }
    }
    // Return null if point does not match any polygon
    return null;
};
exports.getCountry = getCountry;
/**
 * Asynchronously convert coordinates to a country name.
 *
 * Fetch the world sector manifest to determine the sector, then fetch the
 * sector polygon data to identify the specific country polygon containing the coordinate.
 *
 * This is just a premade workflow to show how to operate the functions: getSector, getCountry.
 *
 * @param coordinates - Coordinates as LatLng object.
 * @returns Promise resolving to country key string if found; otherwise null.
 */
const coordinatesToCountry = (coordinates_1, ...args_1) => __awaiter(void 0, [coordinates_1, ...args_1], void 0, function* (coordinates, urls = {
    manifest: "/",
    sectors: "/",
}) {
    try {
        // Fetch the world sector manifest file
        let response = yield fetch(urls.manifest);
        // Throw error if request fails
        if (!response.ok) {
            throw new Error(`Failed to get manifest from ${urls.manifest}`);
        }
        // Parse the sector manifest JSON
        let data = yield response.json();
        // Determine the relevant sector key for the coordinates
        const sector = (0, exports.getSector)(data, coordinates);
        // No sector contains the coordinates, so there is nothing more to fetch
        if (sector === null) {
            return null;
        }
        // Fetch the sector-specific polygon data
        response = yield fetch(`${urls.sectors}/${sector}`);
        // Throw error if request fails
        if (!response.ok) {
            throw new Error(`Failed to get ${sector} from ${urls.sectors}`);
        }
        // Parse the sector polygon data
        data = yield response.json();
        // Determine and return the country within the sector
        return (0, exports.getCountry)(data, coordinates);
    }
    catch (error) {
        // Log any fetch or processing errors
        console.error("Error fetching data:", error);
        // Return null in case of failure
        return null;
    }
});
exports.coordinatesToCountry = coordinatesToCountry;
