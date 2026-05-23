import yaml
from dataclasses import dataclass, field

@dataclass
class ReviewConfig:
    severity_threshold: str = "suggestion"
    auto_approve: bool = True
    ignored_files: list[str] = field(default_factory=list)
    language_hints: dict[str, str] = field(default_factory=dict)
    max_comments: int = 20

DEFAULT_CONFIG = ReviewConfig()

def parse_config(raw_yaml: str) -> ReviewConfig:
    try:
        data = yaml.safe_load(raw_yaml)
        if not isinstance(data, dict):
            return DEFAULT_CONFIG

        return ReviewConfig(
            severity_threshold=data.get("severity_threshold", "suggestion"),
            auto_approve=data.get("auto_approve", True),
            ignored_files=data.get("ignored_files", []),
            language_hints=data.get("language_hints", {}),
            max_comments=data.get("max_comments", 20)
        )
    except yaml.YAMLError as e:
        print(f"Invalid .reviewai.yml: {e}")
        return DEFAULT_CONFIG