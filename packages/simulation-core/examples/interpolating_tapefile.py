from movici_simulation_core.preprocessing import InterpolatingTapefile, TimeDependentAttribute

# given some init data
init_data = {
    "data": {
        "some_dataset": {
            "some_entities": {
                "id": [1, 2, 3],
                "reference": ["a", "b", "c"],
            }
        }
    }
}
# create a tapefile
tapefile = InterpolatingTapefile(
    init_data["data"]["some_dataset"]["some_entities"],
    dataset_name="some_dataset",
    entity_group_name="some_entities",
    reference="reference",
    tapefile_name="tapefile",
)

# add the csv files as TimeDependentAttribute (multiple allowed)
tapefile.add_attribute(
    TimeDependentAttribute(name="some_attribute", csv_file="bla.csv", key="Name")
)

# dump the tapefile to an output file
tapefile.dump(file="out.json")
