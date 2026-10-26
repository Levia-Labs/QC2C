import json
from shapely.geometry import shape, Polygon, MultiPolygon, box
from shapely.ops import unary_union
from tqdm import tqdm
import time
import shutil
from os import path


def get_sector_grid(coordinates) -> list:
    sectors = []
    for name in coordinates:
        min_x, min_y, max_x, max_y = coordinates[name]
        sector = box(min_x, min_y, max_x, max_y)
        sectors.append({'id': name, 'geometry': sector})
    return sectors


def get_map(input_file) -> list:
    result = []

    with open(input_file, 'r', encoding='utf-8') as datafile:
        data = json.load(datafile)
        data = data["features"]
        # Create a new list with objects containing only property1 and property2
        data = [{"name": item["properties"]["ISO_A3"], "geometry": item["geometry"]} for item in data]

        for item in data:
            geometry = shape(item['geometry'])

            if isinstance(geometry, MultiPolygon):
                # append multiple polygons
                for polygon in list(geometry.geoms):
                    polygon = polygon.simplify(tolerance=0.1, preserve_topology=True)
                    result.append({item["name"]: list(polygon.exterior.coords)})
            else:
                # append single polygon
                geometry = geometry.simplify(tolerance=0.1, preserve_topology=True)
                result.append({item["name"]: list(geometry.exterior.coords)})

            # Reduce points in the Polygon
    return result


def map_polygons_to_sectors(polygons, sectors) -> dict:
    assigned_polygons = {sector['id']: [] for sector in sectors}

    for polygon in polygons:

        name = next(iter(polygon), None)
        coordinates = next(iter(polygon.values()), None)
        # Create a copy with switched tuple elements
        switched_list = [(y, x) for x, y in coordinates]

        poly_shape = Polygon(switched_list)

        for sector in sectors:
            sector_shape = shape(sector['geometry'])

            if poly_shape.intersects(sector_shape):
                # TODO keep only the part that does not go outside of sector!
                # TODO Get the difference (remove parts of the main polygon that don't intersect)

                assigned_polygons[sector['id']].append({name: [[y, x] for x, y in coordinates]})

    return assigned_polygons


def merge_polygons(country_polygons, rest_polygons, label) -> list:
    # Step 1: Create a list to store the merged polygons
    merged_polygons = [Polygon(coordinates) for coordinates in country_polygons]

    start_time = time.time()
    total_polygons = len(merged_polygons)

    # Use tqdm to create a loading bar
    for _ in tqdm(range(total_polygons), desc="merge_polygons: %s" % label, unit="polygon"):
        # Flag to check if any merging occurred in this iteration
        merged = False

        # 2. Iterate through each pair of polygons in merged_polygons
        for i in range(len(merged_polygons)):
            for j in range(i + 1, len(merged_polygons)):
                # 3. create merged polygon for each pair:
                merged_polygon = unary_union([merged_polygons[i], merged_polygons[j]])
                # 3.1 reduce polygon
                merged_polygon = merged_polygon.convex_hull
                # 3.2 Reduce points in the Polygon
                merged_polygon = merged_polygon.simplify(tolerance=0.1, preserve_topology=True)
                # TODO 3.3 replace with square in some cases? if number of points > 4?

                # 4. Check if the current pair intersects with any polygon in rest_polygons
                intersects_rest = any(
                    merged_polygon.intersects(Polygon(rest_polygon)) for rest_polygon in rest_polygons)

                # 5. If they don't intersect, merge them and update the merged_polygons list
                if not intersects_rest:
                    merged_polygons[i] = merged_polygon
                    merged_polygons.pop(j)

                    # Set the merged flag to True
                    merged = True
                    break

            # 6. If merging occurred, break from the outer loop to start a new iteration
            if merged:
                break

        # 7. If no merging occurred in this iteration, break from the while loop
        if not merged:
            break

    # Calculate and print the elapsed time
    elapsed_time = time.time() - start_time
    print(f"\n{label}: total time: {elapsed_time:.2f} sec")

    # Step 8: Return the final list of merged polygons
    return merged_polygons


def simplify_polygons(polygons: list) -> dict:
    results = {}
    already_processed = set()
    for i in range(len(polygons)):
        polygon = polygons[i]
        name = next(iter(polygon), None)

        if name not in already_processed:
            # collect all polygons for the same country
            country_polygons = [obj[name] for obj in polygons if name in obj]
            # skip already processed countries
            rest_polygons = [next(iter(obj.values())) for obj in polygons if
                             name not in obj and name not in already_processed]
            # add already processed countries from results
            rest_polygons.extend([next(iter(obj.values())) for obj in polygons if
                                  name in already_processed])

            # merge country polygons if they do not intersect any other polygon from the rest of polygons
            country_merged = merge_polygons(country_polygons, rest_polygons, name)
            results[name] = [list(country.exterior.coords) for country in country_merged]

            # add this country to already_processed check
            already_processed.add(name)
    return results


def save_sectors(assigned_polygons):
    for output_file, data in assigned_polygons.items():
        with open(path.join(source_directory, '../../data/output/stage_1', output_file), 'w', encoding='utf-8') as _:
            json.dump(data, _, separators=(',', ':'))


def remove_country_from_map(map_list: list, country: str) -> list:
    map_list[:] = [item for item in map_list if country not in item]
    return map_list


# data source: https://datahub.io/core/geo-countries
if __name__ == '__main__':
    source_directory = path.dirname(path.abspath(__file__))

    # Record the start time
    run_start_time = time.time()

    # copy world manifest to output
    shutil.copy(path.join(source_directory, '../../data/input', 'world_sectors.json'),
                path.join(source_directory, '../../data/output/stage_1', 'world_sectors.json'))

    # Coordinates for sectors (min_x, min_y, max_x, max_y)
    with open(path.join(source_directory, '../../data/input', 'world_sectors.json'), 'r', encoding='utf-8') as file:
        world_sector_coordinates = json.load(file)
    world_sectors = get_sector_grid(world_sector_coordinates)

    # load geojson of all countries
    world_map = get_map(path.join(source_directory, '../../data/input', 'countries.json'))
    usa_map = get_map(path.join(source_directory, '../../data/input', 'us_states.json'))

    # Remove the item to be replaced from the first list
    world_map = remove_country_from_map(world_map, "USA")
    # Update the first list with items from the second list
    world_map.extend(usa_map)

    # clean up: remove broken zones
    # # SECTOR: 1
    # world_map = remove_country_from_map(world_map, "UMI")  # ??
    # # SECTOR: 2
    world_map = remove_country_from_map(world_map, "AK")  # ??
    # world_map.pop("RUS", None) # broken Kamchatka Peninsula
    # world_map.pop("FRA", None) # broken French Guiana
    # world_map.pop("NLD", None) # broken Dutch Caribbean
    # world_map.pop("NOR", None) # ??
    # # SECTOR: 3
    # world_map.pop("KIR", None) # ??
    # # SECTOR: 4
    # world_map.pop("NZL", None) # ??
    # world_map.pop("FJI", None) # ??
    # # SECTOR: 5
    # world_map.pop("ATF", None) # ??

    # split world map into sectors
    world_sectors = map_polygons_to_sectors(world_map, world_sectors)

    # simplify sectors
    for world_sector in world_sectors:
        world_sectors[world_sector] = simplify_polygons(world_sectors[world_sector])

    # save sectors to separate files
    save_sectors(world_sectors)

    # Record the end time
    run_end_time = time.time()
    # Calculate the total runtime
    total_runtime = run_end_time - run_start_time
    # Print the total runtime
    print(f"Total runtime: {total_runtime} seconds")
