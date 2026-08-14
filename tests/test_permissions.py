import pytest

from raglib.permissions import build_security_filter


@pytest.mark.parametrize(
    ("security_groups", "expected"),
    [
        (None, None),
        ([], "security_groups/any(g: g eq '__DENY_ALL__')"),
        (
            ["group-a", "group-b"],
            "security_groups/any(g: search.in(g, 'group-a,group-b'))",
        ),
    ],
)
def test_build_security_filter(
    security_groups: list[str] | None,
    expected: str | None,
) -> None:
    assert build_security_filter(security_groups) == expected
