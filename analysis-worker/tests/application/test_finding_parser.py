import pytest

from src.application.services.finding_parser import FindingParser


def a_parser():
    return FindingParser()


def test_parse_splits_lines_into_findings():
    findings = a_parser().parse("Finding one\nFinding two\nFinding three")
    assert findings == ["Finding one", "Finding two", "Finding three"]


def test_parse_strips_bullet_markers():
    findings = a_parser().parse("- Finding A\n* Finding B\n• Finding C")
    assert findings == ["Finding A", "Finding B", "Finding C"]


def test_parse_strips_numbered_markers():
    findings = a_parser().parse("1. Finding A\n2) Finding B")
    assert findings == ["Finding A", "Finding B"]


def test_parse_filters_empty_lines():
    findings = a_parser().parse("Finding A\n\n\nFinding B")
    assert findings == ["Finding A", "Finding B"]


def test_parse_raises_on_none():
    with pytest.raises(ValueError, match="empty response"):
        a_parser().parse(None)


def test_parse_raises_on_empty_string():
    with pytest.raises(ValueError, match="empty response"):
        a_parser().parse("")
