from __future__ import annotations

import json
import random
import models
import hashlib
from typing import Any, Optional
from dataclasses import dataclass

language_model = models.testing_model()
PROMPT_PREFIX = "You are a creative worldbuilding engine for a text adventure game."

def hash_dict(d: dict) -> bytes:
    # If we are not JSON serializable we're just gonna die.
    return hashlib.sha1(json.dumps(d).encode("utf-8")).digest()

def _structured_format(
    data: Any = None,
    indent: int = 0,
    include_none: bool = False
) -> str:
    if data is None: return ""
    if type(data) in [str, float, int]:
        return str(data)

    if isinstance(data, Structured):
        data = data.structured()


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

def generate_field_data(path: str, fields_list: list, given: dict, count: int = 5) -> list[dict]:
    fields_list = [f for f in fields_list if f.name not in given]
    fields_list = [f for f in fields_list if f.generated]

    lines = [
    ]

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
            annotation: Optional[str] = None
        ) -> None:
        self.name = name
        self.type = type
        self.generated = generated
        self.annotation = annotation


class Structured:
    RELEVANT_FIELDS: list[Field] = []

    def add_field(self, field, value) -> None:
        self.RELEVANT_FIELDS.append(field)
        setattr(self, field.name, value)

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
    world: World

    def __init__(self):
        self.actions = []

    def generate_actions(self) -> None:
        for i in range(random.randint(2, 6)):
            self.actions.append(Action.generate(given={"location": self}))

    def generate_flavor(self) -> str:
        out = language_model.generate_sync(f"{PROMPT_PREFIX} You need to generate 1-3 sentences of flavor text and/or idle happenings in the second person from the given information. No major changes to the game state should be made by this.\n{self}\n{self.world}")
        return out


class Action(Structured):
    RELEVANT_FIELDS = [
        Field("shortcode", str, annotation="A verb and direct object, separated by a colon. Ex: 'goto:town_tavern'. The only valid verbs are as follows: goto, get, talk, do. Use 'do' when the player's action doesn't fit into any of the others."),
        Field("description", str, annotation="Traditional adventure game choice text. The player will only see this."),
    ]


    shortcode: str
    description: str

    def get_name(self):
        return "PlayerAction"

class World(Structured):
    RELEVANT_FIELDS = [
        Field("conditions", str, annotation="State of the world in words. Comma seperated. No more than 3. Can be very normal: 'peaceful'; can be more imaginative: 'zombie invasion'."),
        Field("facts", str, annotation="What facts capture the world? Do not repeat conditions. Complete sentences. Comma seperated. No more than 3. Perhaps the world is identical to ours, or very different."),
        Field("player", None, generated=False),
    ]

    player: Player
    conditions: str

    locations = {}

    def get_location(self, name: str) -> Location:
        if name in self.locations:
            return self.locations[name]

        loc = Location.generate(given={"name": name, "world": self})
        self.locations[name] = loc

        return loc

player = Player("Claire", 19)
player.add_field(Field("species", str), "humanoid robot")
world = World.generate({"theme": "Fantasy,Outcast MC"})
world.player = player

location = world.get_location("Cat Village")

print(location.description)
print()
print(location.generate_flavor())

if not location.actions:
    location.generate_actions()

for act in location.actions:
    print(f"({act.shortcode}) {act.description}")
