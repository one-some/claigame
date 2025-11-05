from __future__ import annotations

import json
import random
import models
import hashlib
from typing import Any, Optional
from dataclasses import dataclass

language_model = models.testing_model()
PROMPT_PREFIX = "You are a creative worldbuilding engine for a text adventure game."

# Global..
world: World

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

def generate_field_data(path: str, fields_list: list, given: dict, count: int = 1) -> list[dict]:
    fields_list = [f for f in fields_list if f.name not in given]
    fields_list = [f for f in fields_list if f.generated]

    # Create the prompt
    _lore_phrase = "Generate imaginative, specific lore that avoids generic fantasy tropes."
    if count > 1:
        _lore_phrase = f"Generate {count} imaginative, specific lore options that avoid generic fantasy tropes."

    lines = [
        f"{PROMPT_PREFIX} {_lore_phrase} Output ONLY the raw JSON object. Do not wrap it in markdown code blocks, backticks, or any other formatting.\n"
    ]

    for k, v in given.items():
        lines.append(f"{k}: {v}")

    lines.append("\nOutput valid JSON with this structure:")

    json_example = {}
    for field in fields_list:
        if not field.generated: continue
        json_example[f"{path}.{field.name}"] = f"<some {field.type.__name__} here>"

    json_example = [json_example]

    if count > 1:
        json_example *= count

    lines.append(json.dumps(json_example, indent=2))

    lines.append("Field definitions:")
    for field in fields_list:
        if not field.generated: continue
        lines.append(f"- {path}.{field.name}: {field.annotation if field.annotation else 'Self-explanatory.'}")
    prompt = "\n".join(lines) + "\n\n"

    text_out = language_model.generate_sync(prompt)
    data = json.loads(text_out)

    out = []
    for entry in data:
        out_entry = {}
        for (k, v), field in zip(entry.items(), fields_list):
            # print("--")
            # print(raw, field.name)
            # TODO: Raise errors and retry or someth
            out_entry[field.name] = field.type(v)

        out_entry |= given
        out.append(out_entry)
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
    def generate(cls, given: Optional[dict] = None) -> Any:
        return cls.generate_many(given=given, count=1)[0]

    @classmethod 
    def generate_many(cls, given: Optional[dict] = None, count: int = 1) -> list[Any]:
        given = given or {}

        out = []
        data = generate_field_data(cls.get_name(), cls.RELEVANT_FIELDS, given, count)

        for entry in data:
            entry_object = cls()

            for k, v in entry.items():
                setattr(entry_object, k, v)
            out.append(entry_object)

        return out

    def structured(self) -> dict:
        return {k.name: getattr(self, k.name, None) for k in self.RELEVANT_FIELDS}

    @classmethod
    def get_name(cls) -> str:
        return cls.__name__

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
        new_actions = Action.generate_many(count=random.randint(2, 6), given={"location": self})

        for a in new_actions:
            a.location = self
        
        self.actions += new_actions

    def generate_flavor(self) -> str:
        out = language_model.generate_sync(f"{PROMPT_PREFIX} You need to generate 1-3 sentences of flavor text and/or idle happenings in the second person from the given information. No major changes to the game state should be made by this.\n{self}\n{self.world}")
        return out


class Action(Structured):
    RELEVANT_FIELDS = [
        Field("shortcode", str, annotation="A verb and direct object, separated by a colon. Ex: 'goto:town_tavern'. The only valid verbs are as follows: goto, get, talk, do. Use 'do' when the player's action doesn't fit into any of the others."),
        Field("description", str, annotation="The player will choose this to make the action. Ex: 'Walk into the town's tavern'."),
    ]

    shortcode: str
    description: str
    location: Location

    @classmethod
    def get_name(cls) -> str:
        return "PlayerAction"

    def commit(self) -> None:
        world.state_log.append(f"player:{self.shortcode}")
        verb, noun = self.shortcode.split(":")

        match verb:
            case "goto":
                location = world.get_location(noun)
                world.goto(location)
            case "talk":
                pass
            case "get":
                pass
            case "do":
                pass
            case _:
                assert False, f"Don't understand '{verb}'"

        happening = Happening.generate(given={"world": world, "location": self.location, "action": self})
        print(happening)

class Happening(Structured):
    RELEVANT_FIELDS = [
        Field("narration", str, annotation="What narration should the player see in the scene after committing to this action? Describe in descriptive prose what's happening around the player."),
        Field("state_updates", str, annotation="What has changed in this scene? Format in snake case, actor first, comma seperated: 'snake:bite_player,player:kill_snake,villager:thank_player'"),
    ]

    narration: str
    state_updates: str

class World(Structured):
    RELEVANT_FIELDS = [
        Field("conditions", str, annotation="State of the world in words. Comma seperated. No more than 3. Can be very normal: 'peaceful'; can be more imaginative: 'zombie invasion'."),
        Field("facts", str, annotation="What facts capture the world? Do not repeat conditions. Complete sentences. Comma seperated. No more than 3. Perhaps the world is identical to ours, or very different."),
        Field("player", None, generated=False),
    ]

    player: Player
    conditions: str
    active_location: Location
    state_log = []

    locations = {}


    def get_location(self, name: str) -> Location:
        if name in self.locations:
            return self.locations[name]

        loc = Location.generate(given={"name": name, "world": self})
        self.locations[name] = loc

        return loc
    

    def goto(self, location: Location) -> None:
        self.active_location = location
        print("We AT", location)

class ChoiceSet:
    @dataclass
    class Choice:
        text: str
        key: str
        on_select: Any

    def __init__(self) -> None:
        self.choices = []

    def add_choice(self, text: str, on_select: Any) -> None:
        for char in text.lower():
            if char not in "abcdefghijklmnopqrstuvwxyz": continue
            if any([c.key == char for c in self.choices]): continue

            self.choices.append(ChoiceSet.Choice(text, char, on_select))
            return
        raise RuntimeError("Couldn't add choice")

    def prompt(self) -> None:
        for choice in self.choices:
            print(f"({choice.key}) {choice.text}")

        while True:
            try:
                key = input("action> ")
                choice = next(filter(lambda x: x.key == key, self.choices))
                choice.on_select()
                break
            except KeyError:
                print("Please try again. Choose the key shown near your desired action")

player = Player("Claire", 19)
player.add_field(Field("species", str), "humanoid robot")
world = World.generate({"theme": "Fantasy,Outcast MC"})
world.player = player

location = world.get_location("Cat Village")
world.active_location = location

while True:
    print(location.description)
    print()
    print(location.generate_flavor())

    if not location.actions:
        location.generate_actions()

    choices = ChoiceSet()

    for act in location.actions:
        choices.add_choice(f"({act.shortcode}) {act.description}", act.commit)

    choices.prompt()
