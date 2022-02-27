import os
import os.path
import shutil
import sys
from typing import Any, Dict, Iterable, Mapping, Set

import vdf

PATHS_TO_CHECK = {
    "~/.steam/steam/steamapps/libraryfolders.vdf"
}
MAX_LIBS = 100
DEBUG_MODE = False

def debug_log(msg: str) -> None:
    if not DEBUG_MODE:
        return
    print(msg, file=sys.stderr)

def info(msg: str) -> None:
    print(msg, file=sys.stderr)

def discover_library_file() -> str:
    for path in PATHS_TO_CHECK:
        path = os.path.expanduser(path)
        path = os.path.expandvars(path)
        if os.path.exists(path):
            debug_log(f"Found library file at {path}")
            return path
    raise Exception("Library file not found")

def iter_libraries(file: Dict[str, Any]) -> Iterable[Mapping[str, Any]]:
    data = file["libraryfolders"]
    for i in range(0, MAX_LIBS):
        lib = data.get(str(i))
        if not isinstance(lib, Mapping):
            break
        yield lib

def add_orphaned_app(dict: Dict[str, Set[str]], id: str, path: str) -> None:
    if id not in dict:
        dict[id] = set()
    dict[id].add(path)


if __name__ == "__main__":
    # Find and parse lib data
    lib_path = discover_library_file()
    with open(lib_path, "r") as lib_file:
        lib_vdf = vdf.load(lib_file)
    debug_log("Successfully parsed library file")

    app_homes_by_id: Dict[str, str] = {}
    orphaned_apps: Dict[str, Set[str]] = {}
    for lib in iter_libraries(lib_vdf):
        src_path = lib["path"]
        apps = lib["apps"]
        assert isinstance(src_path, str)
        assert isinstance(apps, Mapping)
        debug_log(f"Found library at {src_path} with {len(apps)} app(s)")
        compatdata_path = f"{src_path}/steamapps/compatdata"

        for appid in apps:
            expected_path = f"{compatdata_path}/{appid}"
            if not os.path.exists(expected_path):
                app_homes_by_id[appid] = expected_path

        # Find apps which belong elsewhere
        for appid in os.listdir(compatdata_path):
            if appid not in apps:
                add_orphaned_app(orphaned_apps, appid, f"{compatdata_path}/{appid}")
    debug_log(f"Found {len(app_homes_by_id)} app(s) missing compatdata and {len(orphaned_apps)} orphaned compatdata folder(s)")

    if not orphaned_apps:
        exit(0)

    info(f"{len(orphaned_apps)} orphan(s) detected; folders WILL be deleted. I make no guarantees about anything at all.")
    info("Run this script at your own peril.")
    info("If you have data you do not want to risk losing, please CREATE A BACKUP. ")
    confirmation = input("Please confirm acceptance of liability and willingness to go ahead with reconciliation regardless by typing capital Y: ")
    if confirmation != "Y":
        info("Cancelled")

    for appid, paths in orphaned_apps.items():
        if not app_homes_by_id.get(appid):
            if appid == "0":
                # Some kind of special folder
                continue

            info(f"No home for app {appid}")
            for path in paths:
                shutil.rmtree(path)

        else:
            if not paths:
                info(f"No paths for appid {appid}; this shouldn't happen!")
                continue

            elif len(paths) == 1:
                info(f"Reconciling {appid} with orphan")
                src_path = next(iter(paths))
                dest_path = app_homes_by_id[appid]
                try:
                    shutil.copytree(src_path, dest_path, symlinks=True)
                except KeyboardInterrupt:
                    info("Interrupted")
                    shutil.rmtree(dest_path)
                    exit(0)
                else:
                    shutil.rmtree(src_path)

            else:
                info(f"Multiple orphans found for app {appid}; conflict resolution not yet implemented")
