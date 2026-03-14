def test_package_import_smoke() -> None:
    import czech_vocab

    assert czech_vocab.__version__ == "0.1.0"
