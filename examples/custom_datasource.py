# The following example shows you how to preprocess any raw spatial data (geojson, shapefile)
# before using that data to create a Movici dataset

import geopandas

from movici_simulation_core.preprocessing import GeopandasSource, create_dataset

# Here we create a GeoJSON on the fly. Alternatively, you can read an existing GeoJSON or
# shapefile by using ``geopandas.read_file(<filename>)``
gdf = geopandas.GeoDataFrame.from_features(
    {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [0, 0]},
                "properties": {"a": 1, "b": 2},
            },
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [1, 1]},
                "properties": {"a": 3, "b": 4},
            },
        ],
    },
    crs="WGS84",
)
# We can now do any preprocessing / dataframe operations that we want
gdf["c"] = gdf["a"] + gdf["b"]

# We can now use the source and the new property to create our dataset
config = {
    "__meta__": {"crs": "WGS84"},
    "name": "customized_data",
    "data": {
        "point_entities": {
            "__meta__": {
                "source": "my_custom_source",
                "geometry": "points",
            },
            "some_attribute": {"property": "c"},
        }
    },
}
dataset = create_dataset(config, sources={"my_custom_source": GeopandasSource(gdf)})
