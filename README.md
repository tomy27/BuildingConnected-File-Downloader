## Autodesk Docs File Downloader

The script automatically prepares, renames project folders and copies the corresponding project files from the Autodesk Docs synced folder. The script checks the available projects and creates and copies only the new ones to the projects folder.

## Installation/Setup

1. Setup Autodesk Docs

   - Get access to Autodesk Docs (https://acc.autodesk.com/projects)

   - You should link every project in BuildingConnected (BC) to Autodesk Docs. In order to do this, you should open the Opportunities in BC [link](https://app.buildingconnected.com/opportunities/pipeline) and click on an opportunity. Then in the Links section click on link to Autodesk Docs in the top right corder and follow the instructions. (https://construction.autodesk.com/resources/building-connected/buildingconnected-with-autodesk-docs/)
     This will sync all the files to Autodesk Docs.

   - Install Autodesk Docs Desktop Connector to your computer (https://help.autodesk.com/view/CONNECT/ENU/?guid=Install_Desktop_Connector) (https://help.autodesk.com/view/CONNECT/ENU/)

   - Open Desktop Connector and choose 'Select Projects' menu

   - Select the projects you want to sync to your computer. This will create a folder where all the selected project files will be synced to. Example: C:\Users\<windows_user>\DC\ACCDocs\<Autodesk_user>

2. Create the directory where the projects will be saved. Example: C:\Users\<windows_user>\Projects. Download the Sample Project from the OneDrive to this directory (do not rename it). This will be used as a template by the script.

3. Open Credential Manager in Windows and save the followings as Windows Credentials (Generic Credentials):

   - client_id@BuildingConnected-Downloader, client_id, <YOUR APP ID FROM BUILDINGCONNECTED>
   - client_secret@BuildingConnected-Downloader, client_secret, <YOUR APP SECRET FROM BUILDINGCONNECTED>

4. Copy the unzipped script files to a selected folder.

5. Open the 'config.conf' file and update the two projects directory (project_dir) and the source directory (ACCDocs_dir) where the project files are synced to.

## How to run

Run the script by double-clicking the FileDownloader.exe. You can either pin it to taskbar or to start menu, or you can make a shortcut and copy it to desktop, so you can run it more easily.

## Running with python (optional)

If you would like to run the script with python, then instead of running the executable you should follow these steps:

1. Install Python 3.10 or higher
   To check if Python is installed open Command Prompt and type in 'python --version' or 'python3 --version'. You should be able to see the Python version.
   If not installed, then follow this installation manual: (https://phoenixnap.com/kb/how-to-install-python-3-windows)

2. Open powershell or terminal and navigate to the folder containing the source code.

3. Create a virtual environment by running 'python -m venv venv' in the folder of source code. (Needs To be done only once!)

4. Activate the virtual env (.\venv\Scripts\activate) if not activated yet.

5. Install dependencies (pip install -r requirements.txt) (Needs To be done only once!)

6. Run the file with python (python main.py)

## Comments

- The database stores the timestamps in UTC.

