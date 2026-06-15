from app.review_parse import parse_buckets


def test_parse_buckets_from_clean_json():
    out = parse_buckets('{"text": ["a"], "image": ["b"]}')
    assert out == {"text": ["a"], "image": ["b"]}


def test_parse_buckets_from_fenced_json():
    out = parse_buckets('```json\n{"text": ["a"], "image": []}\n```')
    assert out == {"text": ["a"], "image": []}


def test_parse_buckets_bad_input_returns_empty():
    assert parse_buckets("not json") == {"text": [], "image": []}
