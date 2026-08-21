from coderabbit_control.canonical import canonical_json, sha256_digest


def test_canonical_json_is_key_order_independent():
    left = {"b": 2, "a": {"y": 2, "x": 1}}
    right = {"a": {"x": 1, "y": 2}, "b": 2}
    assert canonical_json(left) == canonical_json(right)
    assert sha256_digest(left) == sha256_digest(right)


def test_canonical_json_uses_compact_utf8_stable_encoding():
    assert canonical_json({"z": "é", "a": 1}) == '{"a":1,"z":"é"}'
