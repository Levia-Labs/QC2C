import json
from shapely.geometry import MultiPolygon, Polygon
import time
import shutil
from os import path
import copy
from tqdm import tqdm


def reduce_points(multi_polygon):
    reduced_polygons = []

    for polygon in multi_polygon.geoms:
        reduced_polygon = reduce_polygon_points(polygon, multi_polygon.difference(polygon))
        reduced_polygons.append(reduced_polygon)

    return MultiPolygon(reduced_polygons)


def reduce_polygon_points(polygon_list: list, other_polygons_list: list) -> list:
    # iterate through the points of the polygon and remove them one by one,
    # checking if the resulting polygon still intersects with other_polygons
    reduced_polygon_list = copy.deepcopy(polygon_list)
    original_polygon = Polygon(polygon_list)

    i = 0
    while i < len(reduced_polygon_list) and len(reduced_polygon_list) > 4:
        test_polygon_list = copy.deepcopy(reduced_polygon_list)
        test_polygon_list.pop(i)
        test_polygon = Polygon(test_polygon_list)
        # check if polygon with removed point does not intersect with any other polygon and still covers the same area
        if not any(test_polygon.intersects(Polygon(other_polygon)) for other_polygon in
                   other_polygons_list) and test_polygon.contains(original_polygon):
            reduced_polygon_list = copy.deepcopy(test_polygon_list)
            i = 0
        else:
            i += 1
    return reduced_polygon_list


def copy_and_remove(source_folder, destination_folder):
    # Remove previous files in destination_folder
    shutil.rmtree(destination_folder)

    # Copy contents from source_folder to destination_folder
    shutil.copytree(source_folder, destination_folder)


def simplify_sector(sector: str):
    # get sector data
    with open(path.join(source_directory, '../../data/output/stage_2', sector), 'r', encoding='utf-8') as file:
        sector_data = json.load(file)

    # iterate through sector and simplify it
    for country in sector_data:
        results = []
        # get rest of polygons
        rest_polygons = [value for key, value in sector_data.items() if key != country]
        rest_polygons = [item for sublist in rest_polygons for item in sublist]
        # simplify country polygon
        for polygon in sector_data[country]:
            results.append(reduce_polygon_points(polygon, rest_polygons))
        sector_data[country] = results

    # save sector data
    with open(path.join(source_directory, '../../data/output/stage_2', sector), 'w', encoding='utf-8') as _:
        json.dump(sector_data, _, separators=(',', ':'))


# data source: https://datahub.io/core/geo-countries
if __name__ == '__main__':
    source_directory = path.dirname(path.abspath(__file__))

    # Record the start time
    run_start_time = time.time()

    # copy data from previous stage
    copy_and_remove(path.join(source_directory, '../../data/output/stage_1'),
                    path.join(source_directory, '../../data/output/stage_2'))

    # get world manifest
    with open(path.join(source_directory, '../../data/output/stage_2', 'world_sectors.json'), 'r', encoding='utf-8') as file:
        world_sectors = json.load(file)

    # simplify sectors N times to get even better approximations
    for world_sector in world_sectors:
        for _ in tqdm(range(20), desc="simplify_sector: %s" % world_sector, unit="loop"):
            simplify_sector(world_sector)

    # Record the end time
    run_end_time = time.time()
    # Calculate the total runtime
    total_runtime = run_end_time - run_start_time
    # Print the total runtime
    print(f"Total runtime: {total_runtime} seconds")
