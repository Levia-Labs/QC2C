import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import Polygon
import json
import random
from os import path
import gzip

if __name__ == '__main__':
    source_directory = path.dirname(path.abspath(__file__))

    # select preview
    stage = 4
    sector = 1

    # Load the world map data
    world = gpd.read_file(gpd.datasets.get_path('naturalearth_lowres'))

    # after stage 3 files are compressed with gzip!
    if stage >= 3:
        with gzip.open(path.join(source_directory, f'../data/output/stage_{stage}', f'world_sector_{sector}.json.gz'),
                       'rt') as gz_file:
            countries = json.load(gz_file)
    else:
        with open(path.join(source_directory, f'../data/output/stage_{stage}', f'world_sector_{sector}.json'),
                  'r', encoding='utf-8') as file:
            countries = json.load(file)

    # Create a GeoDataFrame with the polygons
    polygons = []
    for country in countries:
        for country_polygon in countries[country]:
            # Switch x and y coordinates
            switched_coordinates = [(coord[1], coord[0]) for coord in country_polygon]
            polygon = Polygon(switched_coordinates)

            # show only enormous anomalies, or not
            if polygon.area > 4000 or True:
                color = "#{:06x}".format(random.randint(0, 0xFFFFFF))  # Generate a random hex color
                polygons.append({"geometry": polygon, "color": color, "label": country})

    polygons_gdf = gpd.GeoDataFrame(polygons)

    # Plot the world map
    world.plot()

    # Plot the polygons with random colors and labels
    for idx, row in polygons_gdf.iterrows():
        # Get the centroid of the polygon
        centroid_x, centroid_y = row['geometry'].centroid.xy
        plt.text(centroid_x[0], centroid_y[0], row['label'], ha='center', va='center')
        plt.fill(*row['geometry'].exterior.xy, color=row['color'], alpha=0.5)

    # Show the plot
    plt.show()
