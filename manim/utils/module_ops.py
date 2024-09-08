from __future__ import annotations

import importlib.util
import inspect
import re
import sys
import types
import warnings
from typing import TYPE_CHECKING

from manim import config, console, constants, logger
from manim.file_writer import FileWriter

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from pathlib import Path

    from typing_extensions import Any

    from manim.scene.scene import Scene

__all__ = ["scene_classes_from_file"]


__all__ = ["scene_classes_from_file"]


def get_module(file_name: Path) -> types.ModuleType:
    if str(file_name) == "-":
        module = types.ModuleType("input_scenes")
        logger.info(
            "Enter the animation's code & end with an EOF (CTRL+D on Linux/Unix, CTRL+Z on Windows):",
        )
        code = sys.stdin.read()
        if not code.startswith("from manim import"):
            logger.warning(
                "Didn't find an import statement for Manim. Importing automatically...",
            )
            code = "from manim import *\n" + code
        logger.info("Rendering animation from typed code...")
        try:
            exec(code, module.__dict__)
            return module
        except Exception as e:
            logger.error(f"Failed to render scene: {str(e)}")
            sys.exit(2)
    else:
        if file_name.exists():
            ext = file_name.suffix
            if ext != ".py":
                raise ValueError(f"{file_name} is not a valid Manim python script.")
            module_name = ".".join(file_name.with_suffix("").parts)

            warnings.filterwarnings(
                "default",
                category=DeprecationWarning,
                module=module_name,
            )

            spec = importlib.util.spec_from_file_location(module_name, file_name)
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            sys.path.insert(0, str(file_name.parent.absolute()))
            spec.loader.exec_module(module)
            return module
        else:
            raise FileNotFoundError(f"{file_name} not found")


def get_scene_classes_from_module(module: types.ModuleType) -> list[type[Scene]]:
    from manim.scene.scene import Scene

    def is_child_scene(obj: Any, module: types.ModuleType) -> bool:
        return (
            inspect.isclass(obj)
            and issubclass(obj, Scene)
            and obj != Scene
            and obj.__module__.startswith(module.__name__)
        )

    return [
        member[1]
        for member in inspect.getmembers(module, lambda x: is_child_scene(x, module))
    ]


def get_scenes_to_render(scene_classes: Sequence[type[Scene]]) -> Sequence[type[Scene]]:
    if not scene_classes:
        logger.error(constants.NO_SCENE_MESSAGE)
        return []
    if config.write_all:
        return scene_classes
    result = []
    for scene_name in config.scene_names:
        if not scene_name:
            continue
        for scene_class in scene_classes:
            if scene_class.__name__ == scene_name:
                result.append(scene_class)
                break
        else:
            logger.error(constants.SCENE_NOT_FOUND_MESSAGE.format(scene_name))
    if result:
        return result
    if len(scene_classes) == 1:
        config.scene_names = [scene_classes[0].__name__]
        return [scene_classes[0]]
    return prompt_user_for_choice(scene_classes)


def prompt_user_for_choice(scene_classes: Iterable[type[Scene]]) -> list[type[Scene]]:
    num_to_class = {}
    FileWriter.use_output_as_scene_name()
    for count, scene_class in enumerate(scene_classes, 1):
        name = scene_class.__name__
        console.print(f"{count}: {name}", style="logging.level.info")
        num_to_class[count] = scene_class
    try:
        user_input = console.input(
            f"[log.message] {constants.CHOOSE_NUMBER_MESSAGE} [/log.message]",
        )
        scene_classes = [
            num_to_class[int(num_str)]
            for num_str in re.split(r"\s*,\s*", user_input.strip())
        ]
        config["scene_names"] = [scene_class.__name__ for scene_class in scene_classes]
        return scene_classes
    except KeyError:
        logger.error(constants.INVALID_NUMBER_MESSAGE)
        sys.exit(2)
    except EOFError:
        sys.exit(1)
    except ValueError:
        logger.error("No scenes were selected. Exiting.")
        sys.exit(1)


def scene_classes_from_file(
    file_path: Path, require_single_scene: bool = False, full_list: bool = False
) -> Sequence[type[Scene]]:
    module = get_module(file_path)
    all_scene_classes = get_scene_classes_from_module(module)
    if full_list:
        return all_scene_classes
    scene_classes_to_render = get_scenes_to_render(all_scene_classes)
    if require_single_scene:
        assert len(scene_classes_to_render) == 1
        return [scene_classes_to_render[0]]
    return scene_classes_to_render
