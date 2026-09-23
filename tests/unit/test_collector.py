import zipfile
from io import BytesIO
from pathlib import Path

from slp2mp4.artifact import ContextArtifact, SlippiArtifact
from slp2mp4.collector import Collector


def zip_bytes(entries: dict[str, dict | Path]) -> bytes:
    output = BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for name, data in entries.items():
            if isinstance(data, Path):
                archive.write(data, arcname=name)
            elif isinstance(data, dict):
                archive.writestr(name, zip_bytes(data))
            else:
                archive.writestr(str(name), data)
    return output.getvalue()


def test_collector_single_file(tmp_path):
    test_slp = tmp_path / "g1.slp"
    test_slp.touch()
    collector = Collector([test_slp])
    items = list(collector.next())
    expected = (test_slp, test_slp, [SlippiArtifact(test_slp)])
    assert items == [expected]


def test_collector_context(tmp_path):
    test_slps = [tmp_path / f"{p}.slp" for p in ["g1", "g2"]]
    for slp in test_slps:
        slp.touch()
    test_slp = test_slps[1]
    context = tmp_path / "context.json"
    context.touch()
    collector = Collector([test_slp])
    items = list(collector.next())

    assert len(items) == 1
    item_input, collection_root, collection = items[0]

    assert item_input == test_slp
    assert collection_root == test_slp
    assert collection == [SlippiArtifact(test_slp, 1, ContextArtifact(context))]


def test_collector_multiple_files(tmp_path):
    test_slps = [tmp_path / f"{p}.slp" for p in ["g1", "g2"]]
    for slp in test_slps:
        slp.touch()
    collector = Collector(test_slps)
    items = list(collector.next())
    expected = [(slp, slp, [SlippiArtifact(slp)]) for slp in test_slps]
    assert items == expected


def test_collector_single_dir(tmp_path):
    test_slp = tmp_path / "foo/bar/baz/g1.slp"
    test_slp.parent.mkdir(parents=True)
    test_slp.touch()
    collector = Collector([test_slp])
    items = list(collector.next())
    expected = (test_slp, test_slp, [SlippiArtifact(test_slp)])
    assert items == [expected]


def test_collector_nested_simple_dir(tmp_path):
    test_slp = tmp_path / "foo/bar/baz/g1.slp"
    test_slp.parent.mkdir(parents=True)
    test_slp.touch()
    collector = Collector([tmp_path])
    items = list(collector.next())
    expected = (tmp_path, test_slp.parent, [SlippiArtifact(test_slp)])
    assert items == [expected]


def test_collector_nested_complex_dir(tmp_path):
    # tmp_path
    # ├── g1.slp
    # ├── g2.slp
    # ├── g3.slp
    # ├── single
    # │   ├── g1.slp
    # │   ├── g2.slp
    # │   └── g3.slp
    # └── double
    #     ├── g1.slp
    #     ├── g2.slp
    #     ├── g3.slp
    #     └── nested
    #         ├── g1.slp
    #         ├── g2.slp
    #         └── g3.slp
    base_dir = tmp_path
    directories = [
        base_dir,
        base_dir / "single",
        base_dir / "double",
        base_dir / "double" / "nested",
    ]
    for d in directories:
        d.mkdir(exist_ok=True, parents=True)
        for i in range(1, 4):
            path = d / f"g{i}.slp"
            path.touch()

    test_path = tmp_path
    collector = Collector([test_path])
    items = list(collector.next())

    assert len(items) == 4

    for d in directories:
        expected_collection = [
            SlippiArtifact(d / f"g{i}.slp", i - 1) for i in range(1, 4)
        ]
        expected_base = (tmp_path, d, expected_collection)
        assert expected_base in items


def test_collector_zip_simple(tmp_path):
    # tmp_path/test.zip
    # ├── g1.slp
    # ├── g2.slp
    # └── g3.slp
    test_dir = tmp_path
    slp_files = {f"g{i}.slp": "" for i in range(1, 4)}
    archive_tree = slp_files
    test_zip = test_dir / "test.zip"
    test_zip.write_bytes(zip_bytes(archive_tree))

    collector = Collector([test_zip])
    items = list(collector.next())

    assert len(items) == 1
    item_input, collection_root, collection = items[0]

    assert item_input == test_zip
    assert collection_root == test_dir / "test"
    assert [file.path.name for file in collection] == [
        "g1.slp",
        "g2.slp",
        "g3.slp",
    ]


def test_collector_zip_in_dir(tmp_path):
    # tmp_path/foo/bar/baz/test.zip
    # ├── g1.slp
    # ├── g2.slp
    # └── g3.slp
    test_dir = tmp_path / "foo/bar/baz"
    test_dir.mkdir(parents=True)
    slp_files = {f"g{i}.slp": "" for i in range(1, 4)}
    archive_tree = slp_files
    test_zip = test_dir / "test.zip"
    test_zip.write_bytes(zip_bytes(archive_tree))

    collector = Collector([tmp_path])
    items = list(collector.next())

    assert len(items) == 1
    item_input, collection_root, collection = items[0]

    assert item_input == tmp_path
    assert collection_root == test_dir / "test"
    assert [file.path.name for file in collection] == [
        "g1.slp",
        "g2.slp",
        "g3.slp",
    ]


def test_collector_zip_complex(tmp_path):
    # tmp_path/test.zip
    # ├── g1.slp
    # ├── g2.slp
    # ├── g3.slp
    # ├── single.zip
    # │   ├── g1.slp
    # │   ├── g2.slp
    # │   └── g3.slp
    # └── double.zip
    #     ├── g1.slp
    #     ├── g2.slp
    #     ├── g3.slp
    #     └── nested.zip
    #         ├── g1.slp
    #         ├── g2.slp
    #         └── g3.slp
    test_dir = tmp_path
    slp_files = {f"g{i}.slp": "" for i in range(1, 4)}
    archive_tree = {
        **slp_files,
        "single.zip": slp_files,
        "double.zip": {
            **slp_files,
            "nested.zip": slp_files,
        },
    }
    test_zip = test_dir / "test.zip"
    test_zip.write_bytes(zip_bytes(archive_tree))

    collector = Collector([test_zip])
    items = list(collector.next())

    assert len(items) == 4

    expected_roots = {
        tmp_path / "test",
        tmp_path / "test" / "single",
        tmp_path / "test" / "double",
        tmp_path / "test" / "double" / "nested",
    }
    actual_roots = set()

    for item_input, collection_root, collection in items:
        assert item_input == test_zip
        assert [file.path.name for file in collection] == [
            "g1.slp",
            "g2.slp",
            "g3.slp",
        ]
        actual_roots.add(collection_root)

    assert expected_roots == actual_roots
