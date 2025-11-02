import models
from typing import Any, Optional
from dataclasses import dataclass

language_model = models.testing_model()

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

def generate_field_data(path: str, fields_list: list, given: dict) -> dict:
    fields_list = [f for f in fields_list if f.name not in given]
    fields_list = [f for f in fields_list if f.generated]

    lines = ["You are an adventure game engine, and you need to generate some interesting values for storytelling purposes. Avoid boring or placeholder values; get creative! Return a list of ONLY your results, split by newlines"]

    if given:
        lines.append("You are given this information to work with:")
    for k, v in given.items():
        lines.append(f"{k}: {v}")

    lines.append("\nNow generate values for the following:")
    path = path.replace(" ", "_")

    for field in fields_list:
        if not field.generated: continue
        line = f"{path}.{field.name}: {field.type.__name__}"
        if field.annotation:
            line += f" ({field.annotation})"
        lines.append(line)

    prompt = "\n".join(lines) + "\n\n"
    print(prompt)
    data = language_model.generate_sync(prompt)
    print(data)
    data = data.strip().split("\n")

    out = {}
    for raw, field in zip(data, fields_list):
        # print("--")
        # print(raw, field.name)
        # TODO: Raise errors and retry or someth
        out[field.name] = field.type(raw)

    out |= given
    return out

class Field:
    def __init__(
            self,
            name: str,
            type: Any,
            generated: bool = True,
            public: bool = True,
            annotation: Optional[str] = None
        ) -> None:
        self.name = name
        self.type = type
        self.generated = generated
        self.public = public
        self.annotation = annotation


class Structured:
    RELEVANT_FIELDS: list[Field] = []

    @classmethod 
    def generate(cls, given: Optional[dict] = None, path: str = "") -> Any:
        given = given or {}
        out = cls()

        path_parts = []
        if path: path_parts.append(path)
        path_parts.append(out.get_name())

        for k, v in generate_field_data(".".join(path_parts), out.RELEVANT_FIELDS, given).items():
            setattr(out, k, v)
        return out

    def structured(self) -> dict:
        return {k.name: getattr(self, k.name, None) for k in self.RELEVANT_FIELDS}

    def get_name(self) -> str:
        return self.__class__.__name__

    def __str__(self) -> str:
        return structured_format({self.get_name(): self.structured()})


class Player(Structured):
    RELEVANT_FIELDS = [Field("name", str), Field("age", int)]
    name: str = None
    age: int = None
    
    def __init__(self, name: str, age: int) -> None:
        self.name = name
        self.age = age


class Location(Structured):
    RELEVANT_FIELDS = [
        Field("name", str),
        Field("description", str, annotation="One sentence")
    ]

    name: str
    description: str


@dataclass
class Game:
    player: Player
    location: Location

    def prompt(self) -> str:
        lines = []
        lines.append(f"You are an adventure game engine. Take the following information and produce the next game state.\n")
        lines.append(str(self.player))
        lines.append(str(self.location))
        return "\n".join(lines)

location = Location.generate({"name": "Cat Village"})
plr = Player("Claire", 19)

game = Game(
    player=plr,
    location=location,
)

print(game.prompt())
print(language_model.generate_sync(game.prompt()))
