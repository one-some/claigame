from typing import Any, Optional
from dataclasses import dataclass

def _structured_format(
    data: Any = None,
    indent: int = 0,
    include_none: bool = False
) -> str:
    if data is None: return ""
    if type(data) in [str, float, int]:
        return str(data)


    assert type(data) in [dict, list]

    indent_str = "  " * indent
    lines = []

    if type(data) == dict:
        for k, v in data.items():
            if v is None and not include_none: continue

            formatted_v = _structured_format(v, indent + 1)
            lines.append(indent_str + f"{k}: {formatted_v}")
    elif type(data) == list:
        for v in data:
            if v is None and not include_none: continue

            formatted_v = _structured_format(v, indent + 1)
            lines.append(indent_str + f"- {formatted_v}")

    if not lines:
        lines.append(indent_str + "*empty*")
    return "\n" + "\n".join(lines)


def structured_format(data: Any) -> str:
    return _structured_format(data).strip()

def generate_sync(prompt: str) -> str:
    print(prompt)
    return input("> ")

def generate_field_data(path: str, fields: dict) -> dict:
    lines = ["Please return a list of ONLY your results, seperated by commas."]
    path = path.replace(" ", "_")

    for field, field_type in fields.items():
        lines.append(f"Please generate a value for `{path}.{field}` ({field_type.__name__})")

    data = generate_sync("\n".join(lines))
    print(data)
    data = data.strip().split(",")

    out = {}
    for d, (k, field_type) in zip(data, fields.items()):
        # TODO: Raise errors and retry or someth
        out[k] = field_type(d)
    return out


class Structured:
    RELEVANT_FIELDS = {}

    @classmethod 
    def generate(cls, path: str = "") -> Any:
        out = cls()

        path_parts = []
        if path: path_parts.append(path)
        path_parts.append(out.get_name())

        for k, v in generate_field_data(".".join(path_parts), out.RELEVANT_FIELDS).items():
            setattr(out, k, v)
        return out

    def structured(self) -> dict:
        return {k: getattr(self, k) for k in self.RELEVANT_FIELDS.keys()}

    def get_name(self) -> str:
        return self.__class__.__name__

    def __str__(self) -> str:
        return structured_format({self.get_name(): self.structured()})


class Player(Structured):
    RELEVANT_FIELDS = {"name": str, "age": int}
    name: str = None
    age: int = None


player = Player.generate()
print("--")
print(player)

# print(structured_format({"Player": {"name": "Claire", "age": 19, "inventory": ["Sword", "Lava Crunch Cake", "Minecraft Ring"]}}))
