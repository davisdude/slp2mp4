import zipfile
from io import BytesIO
from multiprocessing import Event
from pathlib import Path

import pytest

from slp2mp4.artifact import ContextArtifact, SlippiArtifact
from slp2mp4.collector import Collector, ConcatRequest, RenderRequest


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
    requests = set(collector.next())
    collector.cleanup()

    mp4 = Path("g1.mp4")
    slp = SlippiArtifact(test_slp)
    expected = {(test_slp, RenderRequest(slp)), (test_slp, ConcatRequest(mp4, (slp,)))}
    assert requests == expected


def test_collector_context(tmp_path):
    test_slps = [tmp_path / f"{p}.slp" for p in ["g1", "g2"]]
    for slp in test_slps:
        slp.touch()
    test_slp = test_slps[1]
    context_path = tmp_path / "context.json"
    context_path.touch()
    context = ContextArtifact(context_path)
    collector = Collector([test_slp])
    requests = set(collector.next())
    collector.cleanup()

    mp4 = Path("g2.mp4")
    slp = SlippiArtifact(test_slp, 1, context)
    expected = {(test_slp, RenderRequest(slp)), (test_slp, ConcatRequest(mp4, (slp,)))}
    assert requests == expected


def test_collector_multiple_files(tmp_path):
    test_slps = [tmp_path / f"{p}.slp" for p in ["g1", "g2"]]
    for slp in test_slps:
        slp.touch()
    collector = Collector(test_slps)
    requests = set(collector.next())
    collector.cleanup()

    slps = [SlippiArtifact(slp, i) for i, slp in enumerate(test_slps)]
    mp4s = [Path("g1.mp4"), Path("g2.mp4")]
    expected = {
        *{(test, RenderRequest(slp)) for test, slp in zip(test_slps, slps)},
        *{
            (test, ConcatRequest(mp4, (slp,)))
            for test, mp4, slp in zip(test_slps, mp4s, slps)
        },
    }
    assert requests == expected


def test_collector_single_dir(tmp_path):
    test_slp = tmp_path / "foo/bar/baz/g1.slp"
    test_slp.parent.mkdir(parents=True)
    test_slp.touch()
    test_dir = test_slp.parent
    collector = Collector([test_dir])
    requests = set(collector.next())
    collector.cleanup()

    slp = SlippiArtifact(test_slp)
    mp4 = Path("baz.mp4")
    expected = {
        (test_dir, RenderRequest(slp)),
        (test_dir, ConcatRequest(mp4, (slp,))),
    }
    assert requests == expected


def test_collector_nested_simple_dir(tmp_path):
    test_slp = tmp_path / "foo/bar/baz/g1.slp"
    test_slp.parent.mkdir(parents=True)
    test_slp.touch()
    collector = Collector([tmp_path])
    requests = set(collector.next())
    collector.cleanup()

    slp = SlippiArtifact(test_slp)
    mp4 = Path("foo/bar/baz.mp4")
    expected = {
        (tmp_path, RenderRequest(slp)),
        (tmp_path, ConcatRequest(mp4, (slp,))),
    }
    assert requests == expected


def test_collector_nested_complex_dir(tmp_path):
    # tmp_path
    # ├── g0.slp
    # ├── g1.slp
    # ├── g2.slp
    # ├── single
    # │   ├── g0.slp
    # │   ├── g1.slp
    # │   └── g2.slp
    # └── double
    #     ├── g0.slp
    #     ├── g1.slp
    #     ├── g2.slp
    #     └── nested
    #         ├── g0.slp
    #         ├── g1.slp
    #         └── g2.slp
    base_dir = tmp_path
    directories = [
        base_dir,
        base_dir / "single",
        base_dir / "double",
        base_dir / "double" / "nested",
    ]
    slps = []
    for d in directories:
        d.mkdir(exist_ok=True, parents=True)
        for i in range(3):
            path = d / f"g{i}.slp"
            path.touch()
    collector = Collector([tmp_path])
    requests = set(collector.next())
    collector.cleanup()

    slps = [
        tuple(SlippiArtifact(d / f"g{i}.slp", i) for i in range(3)) for d in directories
    ]
    mp4s = [
        Path(base_dir.name + ".mp4"),
        Path("single.mp4"),
        Path("double.mp4"),
        Path("double/nested.mp4"),
    ]
    expected = {
        *{(tmp_path, RenderRequest(slp)) for slps in slps for slp in slps},
        *{(tmp_path, ConcatRequest(mp4, slps)) for slps, mp4 in zip(slps, mp4s)},
    }
    assert requests == expected


def test_collector_zip_simple(tmp_path):
    # tmp_path/test.zip
    # ├── g0.slp
    # ├── g1.slp
    # └── g2.slp
    test_dir = tmp_path
    slp_files = {f"g{i}.slp": "" for i in range(3)}
    archive_tree = slp_files
    test_zip = test_dir / "test.zip"
    test_zip.write_bytes(zip_bytes(archive_tree))
    collector = Collector([test_zip])
    requests = set(collector.next())
    collector.cleanup()

    # Cannot do typical comparison because of zip's temp dirs
    inputs = {i for i, _req in requests}
    assert inputs == {test_zip}

    render_requests = {req for _i, req in requests if isinstance(req, RenderRequest)}
    concat_requests = {req for _i, req in requests if isinstance(req, ConcatRequest)}

    render_props = {(req.slp.path.name, req.slp.index) for req in render_requests}
    expected_render_props = tuple((f"g{i}.slp", i) for i in range(3))
    assert render_props == set(expected_render_props)

    concat_props = {
        (req.final, tuple((slp.path.name, slp.index) for slp in req.slps))
        for req in concat_requests
    }
    expected_concat_props = {(Path("test.mp4"), expected_render_props)}
    assert concat_props == expected_concat_props


def test_collector_zip_in_dir(tmp_path):
    # tmp_path/foo/bar/baz/test.zip
    # ├── g0.slp
    # ├── g1.slp
    # └── g2.slp
    test_dir = tmp_path / "foo/bar/baz"
    test_dir.mkdir(parents=True)
    slp_files = {f"g{i}.slp": "" for i in range(3)}
    archive_tree = slp_files
    test_zip = test_dir / "test.zip"
    test_zip.write_bytes(zip_bytes(archive_tree))
    collector = Collector([tmp_path])
    requests = list(collector.next())
    collector.cleanup()

    # Cannot do typical comparison because of zip's temp dirs
    inputs = {i for i, _req in requests}
    assert inputs == {tmp_path}

    render_requests = {req for _i, req in requests if isinstance(req, RenderRequest)}
    concat_requests = {req for _i, req in requests if isinstance(req, ConcatRequest)}

    render_props = {(req.slp.path.name, req.slp.index) for req in render_requests}
    expected_render_props = tuple((f"g{i}.slp", i) for i in range(3))
    assert render_props == set(expected_render_props)

    concat_props = {
        (req.final, tuple((slp.path.name, slp.index) for slp in req.slps))
        for req in concat_requests
    }
    expected_concat_props = {(Path("foo/bar/baz/test.mp4"), expected_render_props)}
    assert concat_props == expected_concat_props


def test_collector_zip_complex(tmp_path):
    # tmp_path/test.zip
    # ├── g0.slp
    # ├── g1.slp
    # ├── g2.slp
    # ├── single.zip
    # │   ├── g3.slp
    # │   ├── g4.slp
    # │   └── g5.slp
    # └── double.zip
    #     ├── g6.slp
    #     ├── g7.slp
    #     ├── g8.slp
    #     └── nested.zip
    #         ├── g9.slp
    #         ├── g10.slp
    #         └── g11.slp
    test_dir = tmp_path
    archive_tree = {
        **{f"g{i}.slp": "" for i in range(3)},
        "single.zip": {f"g{i}.slp": "" for i in range(3, 6)},
        "double.zip": {
            **{f"g{i}.slp": "" for i in range(6, 9)},
            "nested.zip": {f"g{i}.slp": "" for i in range(9, 12)},
        },
    }
    test_zip = test_dir / "test.zip"
    test_zip.write_bytes(zip_bytes(archive_tree))
    collector = Collector([test_zip])
    requests = set(collector.next())
    collector.cleanup()

    # Cannot do typical comparison because of zip's temp dirs
    inputs = {i for i, _req in requests}
    assert inputs == {test_zip}

    render_requests = {req for _i, req in requests if isinstance(req, RenderRequest)}
    concat_requests = {req for _i, req in requests if isinstance(req, ConcatRequest)}

    render_props = {(req.slp.path.name, req.slp.index) for req in render_requests}
    expected_render_props = tuple(
        tuple((f"g{i + j * 3}.slp", i) for i in range(3)) for j in range(4)
    )
    assert render_props == {p for prop in expected_render_props for p in prop}

    concat_props = {
        (req.final, tuple((slp.path.name, slp.index) for slp in req.slps))
        for req in concat_requests
    }
    expected_names = [
        "test.mp4",
        "test/single.mp4",
        "test/double.mp4",
        "test/double/nested.mp4",
    ]
    expected_concat_props = {
        (Path(name), prop) for name, prop in zip(expected_names, expected_render_props)
    }
    assert concat_props == expected_concat_props


def test_collector_monitor_directory_grows(tmp_path):
    test_dir = tmp_path / "set"
    test_dir.mkdir()
    stop_event = Event()
    collector = Collector([test_dir], monitor=True, stop_event=stop_event)
    iterator = collector.next()

    g0 = test_dir / "g0.slp"
    g0.touch()
    input_path, request = next(iterator)
    assert input_path == test_dir
    assert request == RenderRequest(SlippiArtifact(g0))

    g1 = test_dir / "g1.slp"
    g1.touch()
    input_path, request = next(iterator)
    assert input_path == test_dir
    assert request == RenderRequest(SlippiArtifact(g1, 1))

    stop_event.set()
    input_path, request = next(iterator)
    assert input_path == test_dir
    assert isinstance(request, ConcatRequest)

    assert request.final == Path("set.mp4")
    assert request.slps == (SlippiArtifact(g0, 0), SlippiArtifact(g1, 1))

    with pytest.raises(StopIteration):
        next(iterator)

    collector.cleanup()
