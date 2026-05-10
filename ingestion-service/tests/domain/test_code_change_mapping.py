import pytest
from src.domain.entities.code_change import CodeChange
from src.domain.exceptions import MappingError

def test_should_create_code_change_from_push_payload():
    """Test the mapping from a raw GitHub push payload to our Domain Entity."""
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
    
    change = CodeChange.from_push_event(raw_push_payload)
    
    assert change.repository == "paco/blueprint-guardain"
    assert change.ref == "refs/heads/main"
    assert change.target_sha == "d4e5f6g7h8"
    assert change.event_type == "push"

def test_push_mapping_should_fail_with_missing_keys():
    """Ensure the domain raises a MappingError if the push payload is malformed."""
    invalid_payload = {"ref": "only-ref-no-repo"}
    
    with pytest.raises(MappingError) as excinfo:
        CodeChange.from_push_event(invalid_payload)
    
    assert "Missing required field" in str(excinfo.value)

def test_should_create_code_change_from_pull_request_payload():
    """Test the mapping from a raw GitHub PR payload to our Domain Entity."""
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
    
    change = CodeChange.from_pull_request_event(raw_pr_payload)
    
    assert change.repository == "paco/blueprint-guardain"
    assert change.ref == "pr/42"
    assert change.target_sha == "a1b2c3d4"
    assert change.event_type == "pull_request"

def test_pr_mapping_should_fail_with_missing_keys():
    """Ensure the domain raises a MappingError if the PR payload is malformed."""
    invalid_payload = {"action": "opened", "number": 1} # Missing 'pull_request' object
    
    with pytest.raises(MappingError) as excinfo:
        CodeChange.from_pull_request_event(invalid_payload)
        
    assert "Missing required field" in str(excinfo.value)
