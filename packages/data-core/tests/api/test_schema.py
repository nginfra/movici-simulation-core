import pytest


class TestDatasetTypes:
    def test_list_dataset_types(self, get_json):
        get_json("/dataset_types", method="post", json={"name": "type1", "format": "entity_based"})
        get_json("/dataset_types", method="post", json={"name": "type2", "format": "entity_based"})
        get_json("/dataset_types", method="post", json={"name": "type3", "format": "entity_based"})
        result = get_json("/dataset_types")
        assert {r["name"] for r in result["dataset_types"]}.issuperset({"type1", "type2", "type3"})

    @pytest.mark.parametrize(
        "payload",
        [
            {"name": "type1", "format": "entity_based"},
            {"name": "type1", "format": "unstructured"},
            {"name": "type1", "format": "binary"},
            {"name": "type1", "format": "binary", "mimetype": "application/x-netcdf"},
        ],
    )
    def test_create_and_get_dataset_type(self, payload, get_json):
        created = get_json("/dataset_types", method="post", json=payload)
        assert created["message"] == "dataset_type created"
        created_id = created["id"]
        result = get_json(f"/dataset_types/{created_id}")
        assert result.pop("id") == created_id
        assert result.pop("mimetype", None) == payload.pop("mimetype", None)
        assert result == payload

    def test_update_dataset_type(self, get_json):
        created = get_json(
            "/dataset_types", method="post", json={"name": "a_type", "format": "entity_based"}
        )

        updated = get_json(
            f"/dataset_types/{created['id']}",
            method="put",
            json={"name": "new_name", "format": "entity_based"},
        )
        assert updated["message"] == "dataset_type updated"
        assert updated["id"] == created["id"]

        assert get_json(f"/dataset_types/{created['id']}")["name"] == "new_name"

    def test_delete_dataset_type(self, get_json):
        created = get_json(
            "/dataset_types", method="post", json={"name": "a_type", "format": "entity_based"}
        )
        deleted = get_json(f"/dataset_types/{created['id']}", method="delete")
        assert deleted["message"] == "dataset_type deleted"
        result = get_json(f"/dataset_types/{created['id']}", expected_status=404)
        assert result["type"] == "not_found"


class TestEntityTypes:
    def test_list_entity_types(self, get_json):
        get_json("/entity_types", method="post", json={"name": "type1"})
        get_json("/entity_types", method="post", json={"name": "type2"})
        get_json("/entity_types", method="post", json={"name": "type3"})
        result = get_json("/entity_types")
        assert {r["name"] for r in result["entity_types"]}.issuperset({"type1", "type2", "type3"})

    def test_create_and_get_entity_type(self, get_json):
        payload = {"name": "sometype"}
        created = get_json("/entity_types", method="post", json=payload)
        assert created["message"] == "entity_type created"
        created_id = created["id"]
        result = get_json(f"/entity_types/{created_id}")
        assert result.pop("id") == created_id
        assert result == payload

    def test_update_entity_type(self, get_json):
        created = get_json("/entity_types", method="post", json={"name": "a_type"})

        updated = get_json(
            f"/entity_types/{created['id']}",
            method="put",
            json={"name": "new_name"},
        )
        assert updated["message"] == "entity_type updated"
        assert updated["id"] == created["id"]

        assert get_json(f"/entity_types/{created['id']}")["name"] == "new_name"

    def test_delete_entity_type(self, get_json):
        created = get_json("/entity_types", method="post", json={"name": "a_type"})
        deleted = get_json(f"/entity_types/{created['id']}", method="delete")
        assert deleted["message"] == "entity_type deleted"
        result = get_json(f"/entity_types/{created['id']}", expected_status=404)
        assert result["type"] == "not_found"


class TestAttributeTypes:
    def test_list_attribute_types(self, get_json):
        get_json(
            "/attribute_types", method="post", json={"name": "type1", "data_type": {"type": "int"}}
        )
        get_json(
            "/attribute_types", method="post", json={"name": "type2", "data_type": {"type": "int"}}
        )
        get_json(
            "/attribute_types", method="post", json={"name": "type3", "data_type": {"type": "int"}}
        )
        result = get_json("/attribute_types")
        assert {r["name"] for r in result["attribute_types"]}.issuperset(
            {"type1", "type2", "type3"}
        )

    @pytest.mark.parametrize(
        "payload",
        [
            {"name": "sometype", "data_type": {"type": "int", "unit_shape": (1,), "csr": False}},
            {"name": "sometype", "data_type": {"type": "int", "unit_shape": (1, 2), "csr": True}},
            {"name": "sometype", "data_type": {"type": "float"}},
            {"name": "sometype", "data_type": {"type": "int"}},
            {"name": "sometype", "data_type": {"type": "int"}, "enum_name": None},
            {"name": "sometype", "data_type": {"type": "bool"}},
            {"name": "sometype", "data_type": {"type": "str"}},
            {
                "name": "sometype",
                "data_type": {"type": "int"},
                "description": "a description",
                "unit": "m",
                "enum_name": "some_enum",
            },
        ],
    )
    def test_create_and_get_attribute_type(self, payload, get_json):
        created = get_json("/attribute_types", method="post", json=payload)
        assert created["message"] == "attribute_type created"
        created_id = created["id"]
        result = get_json(f"/attribute_types/{created_id}")
        assert result.pop("id") == created_id
        payload["data_type"].setdefault("unit_shape", [])
        payload["data_type"]["unit_shape"] = list(payload["data_type"].get("unit_shape", []))
        payload["data_type"].setdefault("csr", False)
        payload.setdefault("description", "")
        payload.setdefault("unit", "")
        payload.setdefault("enum_name", None)
        assert result == payload

    def test_update_attribute_type(self, get_json):
        created = get_json(
            "/attribute_types",
            method="post",
            json={"name": "a_type", "data_type": {"type": "int"}},
        )

        updated = get_json(
            f"/attribute_types/{created['id']}",
            method="put",
            json={"name": "a_type", "data_type": {"type": "float"}},
        )
        assert updated["message"] == "attribute_type updated"
        assert updated["id"] == created["id"]

        assert get_json(f"/attribute_types/{created['id']}")["data_type"]["type"] == "float"

    def test_delete_attribute_type(self, get_json):
        created = get_json(
            "/attribute_types",
            method="post",
            json={"name": "a_type", "data_type": {"type": "float"}},
        )
        deleted = get_json(f"/attribute_types/{created['id']}", method="delete")
        assert deleted["message"] == "attribute_type deleted"
        result = get_json(f"/attribute_types/{created['id']}", expected_status=404)
        assert result["type"] == "not_found"


class TestModelTypes:
    def test_list_model_types(self, get_json):
        get_json("/model_types", method="post", json={"name": "type1", "jsonschema": {}})
        get_json("/model_types", method="post", json={"name": "type2", "jsonschema": {}})
        get_json("/model_types", method="post", json={"name": "type3", "jsonschema": {}})
        result = get_json("/model_types")
        assert {r["name"] for r in result["model_types"]}.issuperset({"type1", "type2", "type3"})

    def test_create_and_get_model_type(self, get_json):
        payload = {"name": "sometype", "jsonschema": {"some": "schema"}}
        created = get_json("/model_types", method="post", json=payload)
        assert created["message"] == "model_type created"
        created_id = created["id"]
        result = get_json(f"/model_types/{created_id}")
        assert result.pop("id") == created_id
        assert result == payload

    def test_update_model_type(self, get_json):
        created = get_json(
            "/model_types", method="post", json={"name": "a_type", "jsonschema": {}}
        )

        updated = get_json(
            f"/model_types/{created['id']}",
            method="put",
            json={"name": "new_name", "jsonschema": {"some": "schema"}},
        )
        assert updated["message"] == "model_type updated"
        assert updated["id"] == created["id"]

        assert get_json(f"/model_types/{created['id']}")["name"] == "new_name"

    def test_delete_model_type(self, get_json):
        created = get_json(
            "/model_types", method="post", json={"name": "a_type", "jsonschema": {}}
        )
        deleted = get_json(f"/model_types/{created['id']}", method="delete")
        assert deleted["message"] == "model_type deleted"
        result = get_json(f"/model_types/{created['id']}", expected_status=404)
        assert result["type"] == "not_found"
