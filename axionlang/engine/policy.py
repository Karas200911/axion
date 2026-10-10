"""Launch policy (spec §15): set by whoever runs the program, invisible to the model.

policy.json (every key is optional):
    {
      "allow_read": ["reports/"],      folders the program may request with allow read
      "max_steps": 1000000,            statements executed, loop passes included
      "max_output_chars": 100000,      total characters printed
      "max_list_size": 1000000,        elements in one list (ranges included), characters in one text
      "max_depth": 200,                function calls inside one another (recursion)
      "max_memory_mb": 256             megabytes of data the program keeps, counted over the run
    }

No policy = no permissions and the default limits.
"""

DEFAULT_LIMITS = {
    "max_steps": 1_000_000,
    "max_output_chars": 100_000,
    "max_list_size": 1_000_000,
    "max_depth": 200,
    "max_memory_mb": 256,
}
MAX_DEPTH_CEILING = 5000     # deeper than this the interpreter itself would run out of stack


class PolicyError(Exception):
    """A broken policy file: a problem of the person running Axion, not of the program."""


def normalize_folder(folder):
    folder = folder.strip()
    while folder.startswith("./"):
        folder = folder[2:]
    if folder and not folder.endswith("/"):
        folder += "/"
    return folder


def unsafe_path(path):
    """Absolute paths and .. could leave the allowed folder (spec §15)."""
    parts = path.replace("\\", "/").split("/")
    return path.startswith(("/", "\\")) or ".." in parts or (len(path) > 1 and path[1] == ":")


class Policy:
    def __init__(self, allow_read=(), **limits):
        self.allow_read = [normalize_folder(f) for f in allow_read]
        self.limits = dict(DEFAULT_LIMITS)
        self.limits.update(limits)

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            raise PolicyError("the policy must be a JSON object")
        unknown = set(data) - {"allow_read"} - set(DEFAULT_LIMITS)
        if unknown:
            raise PolicyError(f"unknown policy keys: {', '.join(sorted(unknown))}")
        folders = data.get("allow_read", [])
        if not isinstance(folders, list) or not all(isinstance(f, str) for f in folders):
            raise PolicyError("allow_read must be a list of folder names")
        for f in folders:
            if unsafe_path(f):
                raise PolicyError(f"allow_read folder {f!r} must be relative and must not contain ..")
        limits = {}
        for key in DEFAULT_LIMITS:
            if key in data:
                value = data[key]
                if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                    raise PolicyError(f"{key} must be a positive whole number")
                if key == "max_depth" and value > MAX_DEPTH_CEILING:
                    raise PolicyError(f"max_depth cannot be more than {MAX_DEPTH_CEILING}")
                limits[key] = value
        return cls(folders, **limits)

    def permits_read(self, folder):
        folder = normalize_folder(folder)
        return any(folder.startswith(granted) for granted in self.allow_read)
