"""Load the versioned site definitions shipped by Sherlock, without startup networking."""
import json
from functools import lru_cache
from importlib.resources import files


@lru_cache(maxsize=1)
def site_catalog():
    data = json.loads(files("sherlock_project").joinpath("resources/data.json").read_text(encoding="utf-8"))
    return {name: info for name, info in data.items() if not name.startswith("$") and not info.get("isNSFW", False)}
