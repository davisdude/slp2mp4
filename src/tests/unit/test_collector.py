from pathlib import Path
import shutil

from slp2mp4.artifact import SlippiArtifact
from slp2mp4.collector import Collection, Collector

def test_collector_single_file():
    test_path = Path("tests/integration/test.slp")
    collector = Collector([test_path])
    items = list(collector.next())
    expected = (test_path, test_path, Collection([SlippiArtifact(test_path)]))
    assert items == [expected]

def test_collector_multiple_files():
    test_path = Path("tests/integration/test.slp")
    collector = Collector([test_path, test_path])
    items = list(collector.next())
    expected = (test_path, test_path, Collection([SlippiArtifact(test_path)]))
    assert items == [expected, expected]

def test_collector_single_dir():
    test_path = Path("tests/integration/")
    collector = Collector([test_path])
    items = list(collector.next())
    expected = (test_path, test_path, Collection([SlippiArtifact(test_path / "test.slp")]))
    assert items == [expected]

def test_collector_nested_simple_dir():
    test_path = Path("tests/")
    collector = Collector([test_path])
    items = list(collector.next())
    expected = (test_path, test_path / "integration", Collection([SlippiArtifact(test_path / "integration/test.slp")]))
    assert items == [expected]

def test_collector_nested_complex_dir(tmp_path):
    # .
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
    test_slp = Path("tests/integration/test.slp")
    base_dir = tmp_path
    directories = [base_dir, base_dir / "single", base_dir / "double", base_dir / "double" / "nested"]

    for d in directories:
        d.mkdir(exist_ok=True)
        for i in range(1, 4):
            shutil.copy(test_slp, d / f"g{i}.slp")

    test_path = tmp_path
    collector = Collector([test_path])
    items = list(collector.next())

    assert len(items) == 4

    for d in directories:
        expected_collection = Collection([SlippiArtifact(d / f"g{i}.slp") for i in range(1, 4)])
        expected_base = (tmp_path, d, expected_collection)
        assert expected_base in items
