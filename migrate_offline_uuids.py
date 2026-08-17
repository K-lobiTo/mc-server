#!/usr/bin/env python3
"""
Minecraft Online -> Offline UUID Migration Tool
--------------------------------------------------
Renames player data files (playerdata, stats, advancements) from their
current online-mode (Mojang-verified) UUID to the offline-mode UUID that
will be generated once the server runs with ONLINE_MODE=false.

This does NOT touch LuckPerms data. If you use LuckPerms, check its storage
type separately (see notes printed at the end of this script).

USAGE:
    1. STOP your server first (make down / docker compose down).
    2. Back up your whole mc-data folder before running this. Seriously.
    3. Run:  python3 migrate_offline_uuids.py /path/to/mc-data
    4. Review the dry-run output.
    5. Run again with --apply to actually rename the files.

Example:
    python3 migrate_offline_uuids.py ~/Minecraft/mc-server/mc-data
    python3 migrate_offline_uuids.py ~/Minecraft/mc-server/mc-data --apply
"""

import argparse
import hashlib
import json
import shutil
import sys
import uuid
from pathlib import Path


def offline_uuid(username: str) -> str:
    """Replicates Java's UUID.nameUUIDFromBytes(("OfflinePlayer:" + name).getBytes(UTF-8))"""
    data = f"OfflinePlayer:{username}".encode("utf-8")
    md5_bytes = bytearray(hashlib.md5(data).digest())
    md5_bytes[6] = (md5_bytes[6] & 0x0F) | 0x30  # version 3
    md5_bytes[8] = (md5_bytes[8] & 0x3F) | 0x80  # variant RFC 4122
    return str(uuid.UUID(bytes=bytes(md5_bytes)))


def load_usercache(mc_data: Path) -> dict:
    """Returns {username: online_uuid} from usercache.json, if present."""
    usercache_path = mc_data / "usercache.json"
    mapping = {}
    if usercache_path.exists():
        try:
            entries = json.loads(usercache_path.read_text())
            for entry in entries:
                name = entry.get("name")
                uid = entry.get("uuid")
                if name and uid:
                    mapping[name] = uid.replace("-", "")
                    # keep dashed form too, for convenience
                    mapping[name] = uid
        except (json.JSONDecodeError, OSError) as e:
            print(f"  [!] Could not parse usercache.json: {e}")
    return mapping


def find_world_dir(mc_data: Path) -> Path:
    """Best-effort guess at the world folder name (default 'world')."""
    candidate = mc_data / "world"
    if candidate.exists():
        return candidate
    # fallback: read level-name from server.properties
    props = mc_data / "server.properties"
    if props.exists():
        for line in props.read_text().splitlines():
            if line.startswith("level-name="):
                name = line.split("=", 1)[1].strip()
                alt = mc_data / name
                if alt.exists():
                    return alt
    raise FileNotFoundError("Could not locate the world folder under mc-data.")


def gather_rename_plan(world_dir: Path, username_to_old_uuid: dict) -> list:
    """
    Returns a list of (old_path, new_path, username) tuples for every file
    that needs renaming, across playerdata, stats, and advancements.
    """
    plan = []
    subfolders = ["playerdata", "stats", "advancements"]

    for username, old_uuid in username_to_old_uuid.items():
        new_uuid = offline_uuid(username)
        old_uuid_norm = old_uuid.lower()

        for sub in subfolders:
            folder = world_dir / sub
            if not folder.exists():
                continue

            # playerdata/advancements/stats files use .dat / .json, sometimes .dat_old
            for ext in [".dat", ".dat_old", ".json"]:
                old_file = folder / f"{old_uuid_norm}{ext}"
                if old_file.exists():
                    new_file = folder / f"{new_uuid}{ext}"
                    plan.append((old_file, new_file, username))

    return plan


def main():
    parser = argparse.ArgumentParser(description="Migrate Minecraft player data to offline-mode UUIDs.")
    parser.add_argument("mc_data", help="Path to the server's mc-data directory")
    parser.add_argument("--apply", action="store_true", help="Actually perform the renames (default is dry-run)")
    parser.add_argument("--username", action="append", default=[],
                         help="Manually specify a username to migrate (repeatable). "
                              "Overrides/adds to usercache.json entries.")
    args = parser.parse_args()

    mc_data = Path(args.mc_data).expanduser().resolve()
    if not mc_data.exists():
        print(f"ERROR: {mc_data} does not exist.")
        sys.exit(1)

    print(f"Scanning: {mc_data}")

    try:
        world_dir = find_world_dir(mc_data)
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    print(f"World folder: {world_dir}")

    username_map = load_usercache(mc_data)

    # merge in manually specified usernames (need their old UUID looked up from playerdata filenames if not in cache)
    for uname in args.username:
        if uname not in username_map:
            print(f"  [!] '{uname}' not found in usercache.json — you'll need to know their old UUID manually.")
            print(f"      Skipping automatic migration for this user; handle manually if needed.")

    if not username_map:
        print("No usernames found in usercache.json. Nothing to migrate automatically.")
        print("You can still compute an offline UUID manually:")
        print("  python3 -c \"import migrate_offline_uuids as m; print(m.offline_uuid('SomeUsername'))\"")
        sys.exit(0)

    print(f"\nFound {len(username_map)} cached username(s):")
    for uname, old_uuid in username_map.items():
        new_uuid = offline_uuid(uname)
        print(f"  {uname:20s}  {old_uuid}  ->  {new_uuid}")

    plan = gather_rename_plan(world_dir, username_map)

    if not plan:
        print("\nNo matching player data files found to rename. "
              "(Maybe usernames haven't played yet, or files are already migrated.)")
        sys.exit(0)

    print(f"\n{'APPLY MODE' if args.apply else 'DRY RUN'} — {len(plan)} file(s) will be renamed:\n")
    for old_file, new_file, uname in plan:
        print(f"  [{uname}] {old_file.name}  ->  {new_file.name}   ({old_file.parent})")

    if not args.apply:
        print("\nThis was a DRY RUN. No files were changed.")
        print("Re-run with --apply once this looks correct AND you have a backup.")
        return

    print("\nApplying renames...")
    backup_dir = mc_data / "uuid_migration_backup"
    backup_dir.mkdir(exist_ok=True)

    for old_file, new_file, uname in plan:
        # extra safety: copy the original into a backup folder before renaming
        rel_backup_path = backup_dir / old_file.relative_to(world_dir)
        rel_backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(old_file, rel_backup_path)

        if new_file.exists():
            print(f"  [!] SKIP (target already exists): {new_file}")
            continue

        old_file.rename(new_file)
        print(f"  OK: {old_file.name} -> {new_file.name}")

    print(f"\nDone. Originals backed up to: {backup_dir}")
    print("\nNEXT STEPS:")
    print("  1. Set ONLINE_MODE=false in your minecraft.env")
    print("  2. Restart the server: make restart-mc")
    print("  3. Have each migrated player log in under their EXACT SAME username")
    print("     (offline UUIDs are username-based — a rename breaks this again)")
    print("\nNOTE ON LUCKPERMS:")
    print("  This script does NOT migrate LuckPerms permission data.")
    print("  If a migrated player loses their permissions/groups after the switch,")
    print("  check LuckPerms' storage type (config.conf under mc-data/config/luckperms/)")
    print("  and re-assign their group manually via /lp user <name> parent add <group>")
    print("  — much simpler than migrating LuckPerms' internal UUID references.")


if __name__ == "__main__":
    main()
