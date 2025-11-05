# schemas/types.py
from typing import Any, Dict, Optional, List, Union
JSONDict = Dict[str, Any]
JSONArray = List[Any]
JSONType = Union[JSONDict, JSONArray, str, int, float, bool, None]
