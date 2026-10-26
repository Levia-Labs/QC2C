import json
import json_minify
import gzip
import time
import shutil
from os import path, listdir, remove


def copy_and_remove(source_folder, destination_folder):
    # Remove previous files in destination_folder
    shutil.rmtree(destination_folder)

    # Copy contents from source_folder to destination_folder
    shutil.copytree(source_folder, destination_folder)


def simplify_sector(sector: str):
    sector_path = path.join(source_directory, '../../data/output/stage_3')
    # get sector data
    with open(path.join(sector_path, sector), 'r', encoding='utf-8') as file:
        sector_data = json.load(file)

    # Dump the data to a JSON file with ASCII encoding
    with open(path.join(sector_path, sector), 'w', encoding='utf-8') as _:
        json.dump(sector_data, _, ensure_ascii=True, separators=(',', ':'))

    # reduce file size:
    # Dump the data to a JSON file with minimal whitespace using json_minify
    minified_json = json_minify.json_minify(json.dumps(sector_data))

    # Compress the minified JSON using gzip
    with gzip.open(path.join(sector_path, "%s.gz" % sector), "wb") as gzipped_file:
        gzipped_file.write(minified_json.encode('utf-8'))


def adjust_world_sectors_manifest():
    source_directory = path.dirname(path.abspath(__file__))

    # Load the original JSON file
    with open(path.join(source_directory, '../../data/output/stage_3/world_sectors.json'), "r", encoding='utf-8') as json_file:
        data = json.load(json_file)

    # Modify keys by adding ".gz"
    modified_data = {key + ".gz": value for key, value in data.items()}

    # Dump the modified data to a JSON file with minimal whitespace using json_minify
    minified_json = json_minify.json_minify(json.dumps(modified_data))

    # Save the modified and minified data to a new file
    with open(path.join(source_directory, '../../data/output/stage_3/world_sectors.json'), "w", encoding='utf-8') as output_file:
        output_file.write(minified_json)


# data source: https://datahub.io/core/geo-countries
if __name__ == '__main__':
    source_directory = path.dirname(path.abspath(__file__))

    # Record the start time
    run_start_time = time.time()

    # copy data from previous stage
    copy_and_remove(path.join(source_directory, '../../data/output/stage_2'),
                    path.join(source_directory, '../../data/output/stage_3'))

    # get world manifest
    with open(path.join(source_directory, '../../data/output/stage_3', 'world_sectors.json'), 'r', encoding='utf-8') as file:
        world_sectors = json.load(file)

    # simplify sectors N times to get even better approximations
    for world_sector in world_sectors:
        simplify_sector(world_sector)

    # adjust file names in world_sectors.json
    adjust_world_sectors_manifest()

    # List all files in the folder
    files = listdir(path.join(source_directory, '../../data/output/stage_3'))

    # Iterate over the files and remove the JSON files
    for _ in files:
        if _.endswith(".json") and not _.endswith("sectors.json"):
            file_path = path.join(source_directory, '../../data/output/stage_3', _)
            remove(file_path)

    # Record the end time
    run_end_time = time.time()
    # Calculate the total runtime
    total_runtime = run_end_time - run_start_time
    # Print the total runtime
    print(f"Total runtime: {total_runtime} seconds")
