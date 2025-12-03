import configparser
from pathlib import Path
import shutil
import sqlite3
import sys
import logging
import requests
import keyring
from base64 import b64encode
import webbrowser
import threading
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

# Set up logging
logging.basicConfig(
    filename="logs.log",
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# Both console and file logging
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter("%(levelname)s - %(message)s")
console.setFormatter(formatter)
logging.getLogger().addHandler(console)
logger = logging.getLogger(__name__)

app = FastAPI()

token_received_event = threading.Event()

# Globals
PROJECTS_DIR:Path|None = None   # Path to the folder where the projects folders are located
ACCDOCS_DIR:Path|None = None    # Path to the folder where the Desktop Connector syncs the files from BC
DB_FILE:Path|None = None
CLIENT_ID = keyring.get_password("client_id@BuildingConnected-Downloader", "client_id")
CLIENT_SECRET  = keyring.get_password("client_secret@BuildingConnected-Downloader", "client_secret")
REFRESH_TOKEN = keyring.get_password("refresh_token@BuildingConnected-Downloader", "refresh_token")
if not CLIENT_ID or not CLIENT_SECRET:
    print("❌ Client ID and Client secret not found. Please set them first.")
    sys.exit(1)

ACCESS_TOKEN = ""

@app.get("/oauth/callback")
async def oauth_callback(request: Request) -> None:
    global ACCESS_TOKEN, REFRESH_TOKEN, CLIENT_ID, CLIENT_SECRET
    authorization_code = request.query_params.get("code")

    if authorization_code:
        print(f"Received OAuth code: {authorization_code}")

        token_string = f"{CLIENT_ID}:{CLIENT_SECRET}"
        token_b64 = b64encode(token_string.encode("utf-8")).decode("utf-8")

        ACCESS_TOKEN, REFRESH_TOKEN  = get_access_token(token_b64, authorization_code)

        keyring.set_password("refresh_token@BuildingConnected-Downloader", "refresh_token", REFRESH_TOKEN)

        # Notify the main thread that the token was received
        token_received_event.set()
        return HTMLResponse(f"<h3>Authorization was successful.</p>")
    else:
        return HTMLResponse("<h3>Error during authozitaion.</h3>", status_code=400)

def start_fastapi() -> None:
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")

def get_access_token(token_b64:str, authorization_code:str) -> str:
    """Get the access token from the BuildingConnected API

    Args:
        token_b64 (str): Base64 encoded client ID and client secret.
        authorization_code (str): Authorization code received from the OAuth2 authorization server.

    Returns:
        str: Access token for the BuildingConnected API
    """

    url = "https://developer.api.autodesk.com/authentication/v2/token"

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {token_b64}",
    }

    data = {
        "grant_type": "authorization_code",
        "code": authorization_code,
        "redirect_uri": "http://localhost:8000/oauth/callback"
    }

    try:
        response = requests.post(url, headers=headers, data=data)
        response.raise_for_status() # Raises HTTPError for bad responses (4xx, 5xx)
        token_response = response.json()
        print(f"access_token: {token_response}")
        return token_response["access_token"], token_response["refresh_token"]
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP error occurred: {e} - Response: {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Request error: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

def exchange_refresh_token(token_b64:str, refresh_token:str) -> str:
    """Exchange the refresh token for a new access token.

    Args:
        token_b64 (str): Base64 encoded client ID and client secret.
        refresh_token (str): Refresh token to exchange for a new access token.

    Returns:
        str: New access token for the BuildingConnected API
    """
    
    url = "https://developer.api.autodesk.com/authentication/v2/token"

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {token_b64}",
    }

    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }

    try:
        response = requests.post(url, headers=headers, data=data)
        response.raise_for_status() # Raises HTTPError for bad responses (4xx, 5xx)
        token_response = response.json()
        return token_response["access_token"], token_response["refresh_token"]
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP error occurred: {e} - Response: {response.text}")

def authenticate() -> None:
    global ACCESS_TOKEN, REFRESH_TOKEN, CLIENT_ID, CLIENT_SECRET
    try:
        logger.info("Exchanging refresh token for access token...")
        token_string = f"{CLIENT_ID}:{CLIENT_SECRET}"
        token_b64 = b64encode(token_string.encode("utf-8")).decode("utf-8")
        ACCESS_TOKEN, REFRESH_TOKEN = exchange_refresh_token(token_b64, REFRESH_TOKEN)
        keyring.set_password("refresh_token@BuildingConnected-Downloader", "refresh_token", REFRESH_TOKEN)
    except Exception as e:
        logger.error(f"Error exchanging refresh token: {e}")
        logger.info("Starting new authorization flow...")
        threading.Thread(target=start_fastapi, daemon=True).start()

        webbrowser.open(f"https://developer.api.autodesk.com/authentication/v2/authorize?response_type=code&client_id={CLIENT_ID}&redirect_uri=http://localhost:8000/oauth/callback&scope=data:read")
        logger.info("Waiting for OAuth token...")
        token_received_event.wait()
        logger.info("Access token received.")

def init() -> None:
    """Initialize the script, loadss configuration and credentials."""
    global PROJECTS_DIR, ACCDOCS_DIR, DB_FILE

    def resource_path(filename: str) -> Path:
        """Return path to file located next to the executable."""
        if getattr(sys, 'frozen', False):
            # In PyInstaller executable
            return Path(sys.executable).parent / filename
        else:
            # When running as a script
            return Path(__file__).parent / filename

    # Parse config file
    try:
        config_file = resource_path("config.conf")
        config = configparser.ConfigParser()
        config.read(config_file)
        if not config.sections() or "project" not in config.sections():
            raise Exception("Configuration file is empty or 'project' section is missing. Please create a valid config.conf file.")
    except FileNotFoundError:
        raise Exception("Configuration file not found. Please create a config.conf file.")
    except Exception as e:
        raise Exception(f"Error reading configuration file") from e

    # Load pase_path from config or default to Downloads folder
    try:
        project_dir_str = config.get("project", "projects_dir")
        PROJECTS_DIR = Path(project_dir_str) if project_dir_str else Path.home() / "Projects"
        PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    except configparser.NoOptionError:
        raise Exception("Download path not found in config. Please set it first.")
    except Exception as e:
        raise Exception(f"Could not parse or create download path") from e

    try:
        accdocs_dir_str = config.get("project", "ACCDocs_dir")
        ACCDOCS_DIR = Path(accdocs_dir_str) if accdocs_dir_str else None
        if ACCDOCS_DIR is None:
            raise Exception("Could not parse from config.")
    except configparser.NoOptionError:
        raise Exception("ACCDocs_dir not found in config. Please set it first.")
    except Exception as e:
        raise Exception("Error getting ACCDocs_dir") from e
    
    # Create a new database file in the current directory (or open it if it exists)
    try:
        DB_FILE = resource_path("database.db")
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_name TEXT NOT NULL,
                number TEXT NOT NULL,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """)
    except sqlite3.Error as e:
        raise Exception("SQLite error while creating DB") from e
    except Exception as e:
        raise Exception("Error creating database") from e

def list_projects_from_accdocs(directory: Path) -> list[Path]:
    """List all projects from a directory."""
    try:
        projects = [dir for dir in directory.iterdir() if dir.is_dir()]
        return projects
    except Exception as e:
        raise Exception(f"Error listing projects from accdocs dir: {e}")

def project_exists_in_db(project_name: str) -> bool:
    """Check if the project already exists in the database."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM projects WHERE project_name = ? LIMIT 1", (project_name,))
            return cursor.fetchone() is not None
    except sqlite3.Error as e:
        raise Exception("SQLite error while checking if project exists") from e

def save_new_project_to_db(project_name: str, number: str) -> None:
    """Save the new project name to the database."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO projects (project_name, number) VALUES (?, ?)", (project_name, number))
            conn.commit()
    except sqlite3.Error as e:
        raise Exception("SQLite error while save new project to DB") from e

def create_project_folder(new_folder_name:str) -> Path:
    """Create a new project folder by copying the Sample Project folder and rename the folder according to the database."""
    global PROJECTS_DIR

    try:
        sample_project_path = PROJECTS_DIR / "Sample Project"
        new_path = PROJECTS_DIR / new_folder_name

        if not sample_project_path.exists() or not sample_project_path.is_dir():
            raise Exception(f"Sample Project folder does not exist: {sample_project_path}")

        if new_path.exists():
            raise Exception(f"Project folder already exists: {new_path}")

        shutil.copytree(sample_project_path, new_path)
        return new_path
    except Exception as e:
        raise Exception("Could not create project folder") from e

def copy_project_files(source_path:str, dest_path:str) -> None:
    """Copy project files from the ACCDocs folder to the new project folder."""
    try:
        shutil.copytree(source_path, dest_path, dirs_exist_ok=True)
    except Exception as e:
        raise Exception("Error copying project files") from e

def get_opportunities(path:str="/construction/buildingconnected/v2/opportunities") -> str:
    """Get the opportunities from the BuildingConnected API"""
    global ACCESS_TOKEN
    url = f"https://developer.api.autodesk.com{path}"

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status() # Raises HTTPError for bad responses (4xx, 5xx)
        projects = response.json()
        return projects
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error occurred: {e} - Response: {response.text}")

def strip_project_name(name: str) -> str:
    """Normalize project name by removing characters, white spaces"""
    return name.strip().strip("-")

def normalize_project_name(name: str) -> str:
    """Normalize project name by removing characters, white spaces and converting to lowercase."""
    return name.lower().strip().strip("-")

if __name__ == "__main__":
    try:
        init()
        logger.info("Successfully initialized. Starting to search for new projects...")

        all_projects = list_projects_from_accdocs(ACCDOCS_DIR)
        
        new_projects = [project for project in all_projects if not project_exists_in_db(strip_project_name(project.name))]
        logger.info(f"{len(new_projects)} new projects found: {[project.name for project in new_projects]}")

        if not new_projects:
            logger.info("No new projects found. Exiting.")
            sys.exit(0)

        authenticate()

        logger.info("Authenticated successfully. Processing new projects...")
        
        # Make a set from the new projects to speed up lookups
        new_projects_set = set(normalize_project_name(i.name) for i in new_projects)
        normalized_to_project_mapping = {normalize_project_name(p.name): p for p in new_projects} # Mapping normalized names to original project objects
        found_projects = {}
        next_page = None

        while True:
            opportunities = get_opportunities(next_page) if next_page else get_opportunities()

            if not opportunities or not opportunities.get("results"):
                break

            for p in opportunities["results"]:
                name = strip_project_name(p.get("name"))
                normalized_name = normalize_project_name(name)
                if normalized_name in new_projects_set and p.get("number") is not None and not p.get("isArchived", False):
                    found_projects[name] = p["number"]
                    new_projects_set.remove(normalized_name)

            if not new_projects_set:
                break

            next_page = opportunities.get("pagination", {}).get("nextUrl")
            if not next_page:
                break
        
        # Create new project folders, copy files and update database
        for project_name, project_number in found_projects.items():
            full_project_name = f"{project_number} - {project_name}".rstrip(" .")
            new_project_dir = create_project_folder(full_project_name)
            if new_project_dir:
                copy_project_files(normalized_to_project_mapping[normalize_project_name(project_name)] / "Project Files", new_project_dir / "1_Bid Docs" / "BCD")
                save_new_project_to_db(project_name, project_number)
                logger.info(f"New project created: {project_name} -> {full_project_name}")

        # Check if there are any projects left in the new_projects_set that were not found in BuildingConnected
        if new_projects_set:
            logger.warning(f"Some projects were not found in BuildingConnected: {new_projects_set}")
            logger.info("Check if they has number assigned in BuildingConnected.")

        logger.info("Script finished successfully.")
    except Exception as e:
        logger.exception(f"ERROR: {e}")
        sys.exit(1)


