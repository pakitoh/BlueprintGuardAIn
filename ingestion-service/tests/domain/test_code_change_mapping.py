import pytest
from src.domain.entities.code_change import CodeChange

def test_should_create_code_change_from_push_payload():
    """TDD: Test the mapping from a raw GitHub push payload to our Domain Entity."""
    # Arrange
    raw_push_payload = {
        "ref": "refs/heads/main",
        "after": "d4e5f6g7h8",
        "repository": {
            "full_name": "paco/blueprint-guardain"
        },
        "commits": [
            {
                "id": "d4e5f6g7h8",
                "message": "feat: add domain entities",
                "author": {"name": "paco"}
            }
        ]
    }
    
    # Act
    # We'll use a factory method on the entity or a separate Mapper
    change = CodeChange.from_push_event(raw_push_payload)
    
    # Assert
    assert change.repository == "paco/blueprint-guardain"
    assert change.ref == "refs/heads/main"
    assert change.target_sha == "d4e5f6g7h8"
    assert change.event_type == "push"

def test_should_create_code_change_from_pull_request_payload():
    """TDD: Test the mapping from a raw GitHub PR payload to our Domain Entity."""
    # Arrange
    raw_pr_payload = {
        "action": "opened",
        "number": 42,
        "pull_request": {
            "head": {"sha": "a1b2c3d4"},
            "base": {"repo": {"full_name": "paco/blueprint-guardain"}},
        },
        "repository": {
            "full_name": "paco/blueprint-guardain"
        }
    }
    
    # Act
    change = CodeChange.from_pull_request_event(raw_pr_payload)
    
    # Assert
    assert change.repository == "paco/blueprint-guardain"
    assert change.ref == "pr/42"
    assert change.target_sha == "a1b2c3d4"
    assert change.event_type == "pull_request"
