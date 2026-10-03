"""Path-traversal validation for output_folder overrides (SEC-2)."""
import os
import tempfile

from utils.path_validator import validate_output_folder


def test_empty_candidate_is_allowed_noop():
    ok, result = validate_output_folder("", ["/some/root"])
    assert ok
    assert result == ""


def test_no_allowed_roots_configured_rejects_everything():
    ok, _ = validate_output_folder("/anywhere", [])
    assert not ok


def test_candidate_inside_allowed_root_is_accepted():
    root = tempfile.mkdtemp(prefix="sv_ptest_root_")
    sub = os.path.join(root, "subfolder")
    os.makedirs(sub, exist_ok=True)
    ok, result = validate_output_folder(sub, [root])
    assert ok
    assert os.path.normcase(os.path.normpath(result)) == os.path.normcase(os.path.normpath(sub))


def test_traversal_outside_allowed_root_is_rejected():
    root = tempfile.mkdtemp(prefix="sv_ptest_root_")
    traversal = os.path.join(root, "..", "..", "..", "windows", "system32")
    ok, _ = validate_output_folder(traversal, [root])
    assert not ok


def test_unrelated_absolute_path_is_rejected():
    root = tempfile.mkdtemp(prefix="sv_ptest_root_")
    other = tempfile.mkdtemp(prefix="sv_ptest_other_")
    ok, _ = validate_output_folder(other, [root])
    assert not ok
