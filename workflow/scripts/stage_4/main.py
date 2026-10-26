import json
import json_minify
import gzip
import time
import shutil
from os import path, remove

from shapely import MultiPolygon, Polygon


def copy_and_remove(source_folder, destination_folder):
    # Remove previous files in destination_folder
    shutil.rmtree(destination_folder)

    # Copy contents from source_folder to destination_folder
    shutil.copytree(source_folder, destination_folder)


def simplify_sector(sector: str) -> dict:
    sector_path = path.join(source_directory, '../../data/output/stage_4')
    # get sector data
    # Compress the minified JSON using gzip
    with gzip.open(path.join(sector_path, sector), 'rt', encoding='utf-8') as gzipped_file:
        sector_data = json.load(gzipped_file)

    # Iterate through the dictionary and update the values with the center coordinates
    for key, data in sector_data.items():
        multipolygon = MultiPolygon([Polygon(coordinates) for coordinates in data])
        center = multipolygon.centroid
        sector_data[key] = (center.x, center.y)

    return sector_data


# data source: https://datahub.io/core/geo-countries
if __name__ == '__main__':
    source_directory = path.dirname(path.abspath(__file__))

    # Record the start time
    run_start_time = time.time()

    # copy data from previous stage
    copy_and_remove(path.join(source_directory, '../../data/output/stage_3'),
                    path.join(source_directory, '../../data/output/stage_4'))

    # get world manifest
    with open(path.join(source_directory, '../../data/output/stage_4', 'world_sectors.json'), 'r', encoding='utf-8') as file:
        world_sectors = json.load(file)

    # simplify sectors
    for world_sector in world_sectors:
        world_sectors[world_sector] = {
            'bounds': world_sectors[world_sector],
            'center': simplify_sector(world_sector)
        }

    # Compress the JSON data and write it to a Gzip file
    with gzip.open(path.join(source_directory, '../../data/output/stage_4/world_sectors.json.gz'), "w") as gzip_file:
        # Dump the modified data to a JSON file with minimal whitespace using json_minify
        minified_json = json_minify.json_minify(json.dumps(world_sectors))
        gzip_file.write(minified_json.encode('utf-8'))

    # delete json manifest
    remove(path.join(source_directory, '../../data/output/stage_4/world_sectors.json'))

    # Record the end time
    run_end_time = time.time()
    # Calculate the total runtime
    total_runtime = run_end_time - run_start_time
    # Print the total runtime
    print(f"Total runtime: {total_runtime} seconds")
