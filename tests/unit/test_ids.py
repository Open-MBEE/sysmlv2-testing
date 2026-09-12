from sysmlv2_testing import ids


def test_slug_id_is_stable_and_readable():
    a = ids.slug_id("implementation", "opensysml")
    b = ids.slug_id("implementation", "opensysml")
    assert a == b
    assert str(a) == "https://w3id.org/sysmlv2-testing/id/implementation-opensysml"


def test_slug_id_normalizes_unsafe_characters():
    iri = ids.slug_id("testcase", "Some Weird ID!!")
    assert str(iri).endswith("testcase-some-weird-id")


def test_mint_is_deterministic_and_content_derived():
    a = ids.mint("version", "opensysml|abc123")
    b = ids.mint("version", "opensysml|abc123")
    c = ids.mint("version", "opensysml|def456")
    assert a == b
    assert a != c
