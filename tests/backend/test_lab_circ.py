import os
import sys
import pytest
from app.lab_catalog import profile
from app.lab_suites import suite
from app.lab_templates import template
from app.lab_circ import validate_circ
from app.lab_logisim import grade_circ, parse_result, vectors, run_bounded
from app.lab_engine import LabError
from lab_circ_fixtures import reference_circ


@pytest.mark.parametrize("code", ["LAB-D", "LAB-C6", "LAB-S4", "LAB-FSM"])
def test_template_and_independent_circuits_validate(code):
    task = profile(code)
    assert validate_circ(template(task), task)
    assert validate_circ(reference_circ(code), task)


@pytest.mark.parametrize(
    "change",
    [
        lambda b: b.replace(b"5.0.0", b"3.8.0"),
        lambda b: b.replace(
            b"<project ",
            b'<!DOCTYPE project [<!ENTITY x SYSTEM "file:///secret">]><project ',
            1,
        ),
        lambda b: b.replace(b"#Wiring", b"file#secret.circ"),
        lambda b: b.replace(b'name="Pin"', b'name="RAM"', 1),
        lambda b: b.replace(b'val="CLK"', b'val="OTHER"'),
        lambda b: b.replace(b'name="width" val="1"', b'name="width" val="64"', 1),
        lambda b: b.replace(b'name="label" val="CLK"', b'name="path" val="secret"', 1),
        lambda b: b.replace(
            b"</circuit>", b'<comp name="main" loc="(100,100)"/></circuit>'
        ),
    ],
)
def test_invalid_version_libraries_attributes_ports_recursion(change):
    task = profile("LAB-D")
    with pytest.raises(LabError):
        validate_circ(change(template(task)), task)


def test_binary_vector_values_complete_sets_and_non_scored_init():
    task = profile("LAB-S4")
    text, rows = vectors(task, suite("LAB-S4"))
    assert "P[4]" in text and "Q[4]" in text and "<set> <seq>" in text
    assert text.splitlines()[1].endswith("<DC> 1 1")
    assert all(" 0" != line.split()[-1] for line in text.splitlines()[1:])
    assert len(rows) < 256


def test_exit_zero_with_failure_is_not_pass_and_binary_is_preserved():
    rows = [
        dict(inputs={"D": "1"}, expected={"Q": "0000"}, scored=True),
        dict(inputs={"D": "0"}, expected={"Q": "0101"}, scored=True),
    ]
    out = "1 \r\n  Q = 1010 (expected 0000)\n2 \r\nPassed: 1, Failed: 1\n"
    result = parse_result(0, out.replace("\r", "\n"), "Error on test vector 1:", rows)
    assert (
        result["score"] == 50
        and not result["passed"]
        and result["first_failure"]["actual"] == {"Q": "1010"}
    )
    for code, stdout, stderr in [
        (1, out, "Error on test vector 1:"),
        (0, "Passed: 2, Failed: 0", ""),
        (0, out, ""),
        (0, out.replace("Failed: 1", "Failed: 2"), "Error on test vector 1:"),
    ]:
        with pytest.raises(LabError):
            parse_result(code, stdout.replace("\r", "\n"), stderr, rows)


def test_subprocess_timeout_and_bounded_both_streams(tmp_path):
    with pytest.raises(LabError, match="超过15秒"):
        run_bounded(
            [sys.executable, "-c", "import time; time.sleep(10)"], tmp_path, timeout=0.1
        )
    with pytest.raises(LabError, match="超过限制"):
        run_bounded(
            [
                sys.executable,
                "-c",
                'import sys; sys.stdout.write("a"*300000);sys.stderr.write("b"*300000)',
            ],
            tmp_path,
            limit=4096,
        )


@pytest.mark.skipif(
    not os.environ.get("LAB_REAL_ENGINE"),
    reason="设置LAB_REAL_ENGINE=1及LAB_JAVA/LAB_JAR执行真实引擎验收",
)
@pytest.mark.parametrize("code", ["LAB-D", "LAB-C6", "LAB-S4", "LAB-FSM"])
def test_real_official_engine_four_correct_wrong_equivalent(code):
    task = profile(code)
    tests = suite(code)
    config = dict(LAB_JAVA=os.environ["LAB_JAVA"], LAB_JAR=os.environ["LAB_JAR"])
    for equivalent in (False, True):
        content = validate_circ(reference_circ(code, equivalent=equivalent), task)
        result = grade_circ(task, tests, content, config)
        assert result["score"] == 100 and result["passed"], result
    wrong = grade_circ(
        task, tests, validate_circ(reference_circ(code, wrong=True), task), config
    )
    assert (
        not wrong["passed"]
        and wrong["score"] < 100
        and wrong["first_failure"]["actual"] != wrong["first_failure"]["expected"]
    )
