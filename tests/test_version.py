import server


def test_version_value() -> None:
    """Check that __version__ matches the expected value."""
    assert server.__version__ == "0.0.1"
