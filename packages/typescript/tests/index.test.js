const fs = require("fs");
const path = require("path");
const { getSector, getCountry, coordinatesToCountry } = require("../dist/index");

const dataDir = path.join(__dirname, "..", "src", "data", "json");
const load = (name) => JSON.parse(fs.readFileSync(path.join(dataDir, name), "utf8"));

const lookup = ({ lat, lng }) => {
  const manifest = load("world_sectors.json");
  // Sector bounds may overlap: try every sector containing the point.
  for (const [key, value] of Object.entries(manifest)) {
    if (getSector({ [key]: value }, { lat, lng }) === null) continue;
    const country = getCountry(load(key.replace(/\.gz$/, "")), { lat, lng });
    if (country) return country;
  }
  return null;
};

describe("getSector", () => {
  const bare = { a: [0, 0, 5, 5], b: [6, 6, 10, 10] };
  const wrapped = { a: { bounds: [0, 0, 5, 5], center: {} }, b: { bounds: [6, 6, 10, 10], center: {} } };

  test.each([["bare", bare], ["wrapped", wrapped]])("%s bounds", (_, manifest) => {
    expect(getSector(manifest, { lat: 3, lng: 3 })).toBe("a");
    expect(getSector(manifest, { lat: 7, lng: 7 })).toBe("b");
    expect(getSector(manifest, { lat: 11, lng: 11 })).toBeNull();
  });
});

describe("getCountry", () => {
  const square = [[0, 0], [0, 2], [2, 2], [2, 0]];
  const far = [[6, 6], [6, 10], [10, 10], [10, 6]];

  test.each([
    ["polygon", { A: square, B: far }],
    ["multipolygon", { A: [square], B: [[[20, 20], [20, 21], [21, 21]], far] }],
  ])("%s", (_, manifest) => {
    expect(getCountry(manifest, { lat: 1, lng: 1 })).toBe("A");
    expect(getCountry(manifest, { lat: 7, lng: 7 })).toBe("B");
    expect(getCountry(manifest, { lat: 15, lng: 15 })).toBeNull();
  });
});

describe("bundled data", () => {
  test.each([
    [52.23, 21.01, "POL"],
    [40.71, -74.0, "USA"],
    [-33.87, 151.21, "AUS"],
    [35.68, 139.69, "JPN"],
    // Open ocean returns the nearest country (Marquesas).
    [0, -140, "PYF"],
  ])("(%s, %s) -> %s", (lat, lng, expected) => {
    expect(lookup({ lat, lng })).toBe(expected);
  });
});

describe("coordinatesToCountry", () => {
  test("resolves via fetch over bundled json", async () => {
    global.fetch = async (url) => {
      const name = String(url).split("/").pop();
      const file = name === "" ? "world_sectors.json" : name.replace(/\.gz$/, "");
      return { ok: true, json: async () => load(file) };
    };
    const urls = { manifest: "/", sectors: "" };
    expect(await coordinatesToCountry({ lat: 52.23, lng: 21.01 }, urls)).toBe("POL");
  });
});
