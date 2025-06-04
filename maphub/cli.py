#!/usr/bin/env python3
"""
MapHub CLI - Command-line interface for MapHub API.

This module provides a command-line interface for interacting with the MapHub API.
It allows users to authenticate with an API key and upload maps to their projects.
"""

import argparse
import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from .client import MapHubClient
from .exceptions import APIException

# Define the config directory and file path
CONFIG_DIR = Path.home() / ".maphub"
CONFIG_FILE = CONFIG_DIR / "config.json"


def __get_api_client__() -> MapHubClient:
    """
    Initializes and returns an instance of MapHubClient using the provided API key
    stored in the configuration file. If the configuration file does not exist or
    the JSON is invalid, the program will print an error message and terminate.

    :return: An instance of MapHubClient initialized with the API key if found in
             the configuration file.
    :rtype: MapHubClient
    """
    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
            api_key = config.get("api_key")
            return MapHubClient(api_key=api_key)
    except (json.JSONDecodeError, FileNotFoundError):
        print("Error: No API key found. Please run 'maphub auth API_KEY' first.", file=sys.stderr)
        sys.exit(1)


def save_api_key(api_key: str) -> None:
    """
    Save the API key to the local configuration file.

    Args:
        api_key: The API key to save
    """
    # Create the config directory if it doesn't exist
    CONFIG_DIR.mkdir(exist_ok=True)

    # Save the API key to the config file
    with open(CONFIG_FILE, "w") as f:
        json.dump({"api_key": api_key}, f)

    print(f"API key saved successfully to {CONFIG_FILE}")



def auth_command(args) -> None:
    """
    Handle the 'auth' command to save the API key.

    Args:
        args: Command-line arguments
    """
    save_api_key(args.api_key)


def upload_command(args) -> None:
    """
    Handle the 'upload' command to upload a GIS file.

    Args:
        args: Command-line arguments
    """
    # Check if the file exists
    file_path = Path(args.file_path)
    if not file_path.exists():
        print(f"Error: File not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    # Create the client
    client = __get_api_client__()

    try:
        # Use the provided folder_id if available, otherwise use the root folder
        folder_id = args.folder_id
        if folder_id is None:
            # If error occurs when getting folders, fall back to root folder
            personal_workspace = client.workspace.get_personal_workspace()
            root_folder = client.folder.get_root_folder(personal_workspace["id"])
            folder_id = root_folder["folder"]["id"]
            print(f"Using root folder (ID: {folder_id})")
        else:
            print(f"Using specified folder (ID: {folder_id})")

        # Use the provided map_name if available, otherwise extract from the file path (without extension)
        map_name = args.map_name if args.map_name else file_path.stem

        # Upload the map
        print(f"Uploading {file_path} to folder {folder_id}...")
        response = client.maps.upload_map(
            map_name=map_name,
            folder_id=folder_id,
            public=False,
            path=str(file_path)
        )

        print(f"Map uploaded successfully!")

    except APIException as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


# Helper functions for CLI commands


def find_repository_root() -> Optional[Path]:
    """
    Find the root directory of the MapHub repository (containing .maphub).

    Returns:
        Path to the repository root, or None if not in a repository
    """
    current_dir = Path.cwd()
    root_dir = current_dir

    while not (root_dir / ".maphub").exists() or root_dir == Path.home():
        if root_dir.parent == root_dir:  # Reached filesystem root
            return None
        root_dir = root_dir.parent

    print(root_dir)
    return root_dir

# Main command functions

def clone_command(args) -> None:
    """
    Clone a folder from MapHub to local directory.

    Args:
        args: Command-line arguments containing:
            - id: ID of the folder to clone
            - output: Path to the output directory
    """
    # Create the client
    client = __get_api_client__()

    # Get the ID from args
    folder_id = uuid.UUID(args.id)
    output_dir = Path(args.output).resolve()

    # Use the client's clone method
    try:
        client.clone(folder_id, output_dir)
    except Exception as e:
        print(f"Error: Failed to clone folder with ID {folder_id}: {e}")
        import traceback
        traceback.print_exc()
        return


def pull_command(args) -> None:
    """
    Pull latest changes from MapHub.

    This command should be run from within a directory that was previously cloned.
    It will update any maps in the folder that have changed on the server.
    """
    # Find the root directory (containing .maphub)
    root_dir = find_repository_root()
    if root_dir is None:
        print("Error: Not in a MapHub repository. Please run this command from within a cloned directory.", file=sys.stderr)
        sys.exit(1)

    # Create the client
    client = __get_api_client__()

    # Use the client's pull method
    try:
        client.pull(root_dir)
    except Exception as e:
        print(f"Error during pull: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


def push_command(args) -> None:
    """
    Push local changes to MapHub.

    This command should be run from within a directory that was previously cloned.
    It will upload any maps in the folder that have changed locally.
    """
    # Find the root directory (containing .maphub)
    root_dir = find_repository_root()
    if root_dir is None:
        print("Error: Not in a MapHub repository. Please run this command from within a cloned directory.", file=sys.stderr)
        sys.exit(1)

    # Create the client
    client = __get_api_client__()

    # Use the client's push method
    try:
        client.push(root_dir, args.description)
    except Exception as e:
        print(f"Error during push: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main() -> None:
    """
    Main entry point for the CLI.
    """
    parser = argparse.ArgumentParser(description="MapHub CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Auth command
    auth_parser = subparsers.add_parser("auth", help="Save API key")
    auth_parser.add_argument("api_key", help="MapHub API key (Can be created here: https://www.maphub.co/dashboard/api_keys)")
    auth_parser.set_defaults(func=auth_command)

    # Upload command
    upload_parser = subparsers.add_parser("upload", help="Upload a GIS file")
    upload_parser.add_argument("file_path", help="Path to the GIS file")
    upload_parser.add_argument("--folder-id", help="Target folder ID (uses root folder if not specified)", default=None)
    upload_parser.add_argument("--map-name", help="Custom map name (uses file name if not specified)", default=None)
    upload_parser.set_defaults(func=upload_command)

    # Clone command
    clone_parser = subparsers.add_parser("clone", help="Clone a Folder")
    clone_parser.add_argument("id", help="ID of the Folder to clone")
    clone_parser.add_argument("--output", help="The path to the desired output folder.", default=".")
    clone_parser.set_defaults(func=clone_command)

    # Pull command
    pull_parser = subparsers.add_parser("pull", help="Pull latest version from a Folder on MapHub")
    pull_parser.set_defaults(func=pull_command)

    # Push command
    push_parser = subparsers.add_parser("push", help="Push local version of a Folder to MapHub")
    push_parser.add_argument("--description", help="Description for the new version", default=None)
    push_parser.set_defaults(func=push_command)


    # Parse arguments
    args = parser.parse_args()

    # Execute the appropriate command
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
