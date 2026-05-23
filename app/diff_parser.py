from dataclasses import dataclass, field

@dataclass
class DiffLine:
    content: str
    line_type: str
    position: int
    new_file_line: int

@dataclass
class DiffHunk:
    file_path: str
    new_start_line: int
    lines: list[DiffLine] = field(default_factory=list)


def parse_diff(raw_diff:str) -> list[DiffHunk]:
    hunks = []
    current_file = None
    current_hunk = None
    position = 0
    current_new_line = 0

    for line in raw_diff.splitlines():
        if line.startswith("diff --git"):
            position = 0
            current_hunk = None
            current_file = None
        elif line.startswith("+++ ") or line.startswith("--- "):
            if line.startswith("+++ b/"):
                current_file = line[6:].strip()
        elif line.startswith("@@"):
            position += 1
            try:
                new_part = line.split("+")[1].split("@@")[0].strip()
                new_start = int(new_part.split(",")[0])
            except (IndexError, ValueError):
                new_start = 0
            
            current_new_line = new_start - 1
            current_hunk = DiffHunk(current_file or "unknown", new_start)
            hunks.append(current_hunk)
        elif current_hunk is not None and line and line[0] in ("+", "-", " "):
            position += 1
            if line[0] == "+":
                line_type = "added"
                current_new_line += 1
            elif line[0] == "-":
                line_type = "removed"
            else:
                line_type = "context"
                current_new_line += 1
            
            current_hunk.lines.append(DiffLine(line[1:], line_type, position, current_new_line))
        
    return hunks

