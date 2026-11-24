"""Source-bound infographic capacity, independent of rule-based selection policy."""

MAX_INFOGRAPHIC_NODES = 5


def supports_node_count(count: int) -> bool:
    return 2 <= count <= MAX_INFOGRAPHIC_NODES
