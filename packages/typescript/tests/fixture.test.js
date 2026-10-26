// Every fixture point written by qc2c-build must resolve to its expected code.
const fs = require("fs");
const path = require("path");
const { getSector, getCountry } = require("../dist/index");

const dataDir = path.join(__dirname, "..", "src", "data", "json");
const load = (name) => JSON.parse(fs.readFileSync(path.join(dataDir, name), "utf8"));
const points = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "..", "fixtures", "points.json"), "utf8"));

test("fixture points match the pipeline", () => {
  const manifest = load("world_sectors.json");
  const wrong = points.filter(({ lat, lng, code }) => {
    const key = getSector(manifest, { lat, lng });
    return key === null || getCountry(load(key.replace(/\.gz$/, "")), { lat, lng }) !== code;
  });
  expect(points.length).toBeGreaterThanOrEqual(250);
  expect(wrong.slice(0, 10)).toEqual([]);
});
