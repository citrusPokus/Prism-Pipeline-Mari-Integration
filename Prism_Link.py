import mari
import os
import re
import shutil
import subprocess
import platform
import importlib
from PySide2 import QtWidgets, QtCore

class PrismProjectLinker(QtWidgets.QDialog):
    # Dialog class: allows the user to pick Global (server) and Local (workstation)
    # roots, pick an asset from the project tree. The chosen settings are saved into the
    # current geometry's metadata so other plugin actions can use the paths.
    def __init__(self):
        main_win = next((w for w in QtWidgets.QApplication.topLevelWidgets() if isinstance(w, QtWidgets.QMainWindow)), None)
        super(PrismProjectLinker, self).__init__(main_win)
        self.setWindowTitle("Prism Asset Linker & Converter")
        self.setMinimumWidth(500)
        
        geo = mari.geo.current()
        if geo:
            self.project_root = geo.metadata("PrismGlobalRoot") if geo.hasMetadata("PrismGlobalRoot") else ""
        else:
            self.project_root = ""
            print("Prism Linker: No active geometry found in Mari.")
        self.local_root = geo.metadata("PrismLocalRoot") if geo.hasMetadata("PrismLocalRoot") else ""
        self.saved_path = geo.metadata("PrismGlobalPath") if geo.hasMetadata("PrismGlobalPath") else ""
        
        self.setup_ui()
        QtCore.QTimer.singleShot(100, self.restore_saved_selection)

    def setup_ui(self):
        # Build the dialog UI: buttons for selecting roots, options for
        # category/asset and a save button. 

        layout = QtWidgets.QVBoxLayout(self)
        self.btn_root = QtWidgets.QPushButton(f"Global: {self.project_root}" if self.project_root else "Select GLOBAL Root (Server)")
        self.btn_root.clicked.connect(self.pick_root)
        layout.addWidget(self.btn_root)

        self.btn_local = QtWidgets.QPushButton(f"Local: {self.local_root}" if self.local_root else "Select LOCAL Root (Your PC)")
        self.btn_local.clicked.connect(self.pick_local)
        layout.addWidget(self.btn_local)

        layout.addWidget(QtWidgets.QLabel("Select Category & Asset:"))
        self.combo_category = QtWidgets.QComboBox()
        self.combo_category.currentIndexChanged.connect(self.populate_assets)
        layout.addWidget(self.combo_category)

        self.combo_asset = QtWidgets.QComboBox()
        layout.addWidget(self.combo_asset)

        layout.addWidget(QtWidgets.QLabel("Target Renderer for Conversion:"))
        self.combo_render = QtWidgets.QComboBox()
        self.combo_render.addItems(["Karma (RAT)", "RenderMan (TEX)", "None"])
        layout.addWidget(self.combo_render)
        # Restore saved renderer choice from geo metadata so the dialog reflects previously saved setting
        try:
            geo = mari.current.geo()
            if geo and geo.hasMetadata("PrismTargetRenderer"):
                saved = geo.metadata("PrismTargetRenderer")
                idx = self.combo_render.findText(saved)
                if idx >= 0:
                    self.combo_render.setCurrentIndex(idx)
        except Exception:
            pass

        self.btn_save = QtWidgets.QPushButton("Link & Save Settings")
        self.btn_save.clicked.connect(self.save_link)
        layout.addWidget(self.btn_save)
        
        if self.project_root: self.populate_categories()

    # select Global root directories
    def pick_root(self):
        # Opens a folder picker and stores the selected Global root (server)
        # into `self.project_root`. Also repopulates the category list when set.
        p = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Global Root")
        if p: self.project_root = p.replace("\\", "/"); self.populate_categories()

    # select Local root directories
    def pick_local(self):
        # Opens a folder picker and stores the selected Local root (workstation)
        # into `self.local_root` for later exports/publishes.
        p = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Local Root")
        if p: self.local_root = p.replace("\\", "/")

    # setup category and asset dropdowns
    def populate_categories(self):
        # Reads the `03_Production/Assets` folder under the selected Global
        # root and fills the category combobox with any subfolders found.
        self.combo_category.clear()
        path = os.path.join(self.project_root, "03_Production/Assets")
        if os.path.exists(path):
            self.combo_category.addItems([d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))])

    def populate_assets(self):
        # Given a category selection, list the assets (subfolders) and fill the
        # asset combobox.
        self.combo_asset.clear()
        path = os.path.join(self.project_root, "03_Production/Assets", self.combo_category.currentText())
        if os.path.exists(path):
            self.combo_asset.addItems([d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))])

    def restore_saved_selection(self):
        # When opening the dialog, try to restore the previously saved
        # GlobalPath metadata and pre-select the category + asset in the UI.
        if not self.saved_path: return
        parts = self.saved_path.split('/')
        if len(parts) >= 2:
            cat, ast = parts[-2], parts[-1]
            idx = self.combo_category.findText(cat)
            if idx >= 0:
                self.combo_category.setCurrentIndex(idx)
                QtCore.QTimer.singleShot(100, lambda: self.combo_asset.setCurrentIndex(self.combo_asset.findText(ast)))

    def save_link(self):
        # Save the chosen global/local roots, the full Global/Local path for the
        # selected asset, and the renderer selection into the current geometry's
        # metadata (keys: PrismGlobalRoot, PrismLocalRoot, PrismGlobalPath,
        # PrismLocalPath, PrismTargetRenderer). Show a confirmation message.
        rel = f"03_Production/Assets/{self.combo_category.currentText()}/{self.combo_asset.currentText()}"
        renderer_choice = self.combo_render.currentText()
        geo = mari.current.geo()
        geo.setMetadata("PrismGlobalRoot", self.project_root)
        geo.setMetadata("PrismLocalRoot", self.local_root)
        geo.setMetadata("PrismGlobalPath", f"{self.project_root}/{rel}".replace("//", "/"))
        geo.setMetadata("PrismLocalPath", f"{self.local_root}/{rel}".replace("//", "/"))
        geo.setMetadata("PrismTargetRenderer", renderer_choice)
        mari.utils.message("Prism Link Saved!"); self.close()

# Utility functions for version handling
def get_latest_version_label(tex_root):
    # Return the highest version folder name in a Textures folder, e.g. 'v0003'.
    # If the folder doesn't exist or no versions found return 'v0000'.
    if not os.path.exists(tex_root): return "v0000"
    versions = sorted([v for v in os.listdir(tex_root) if re.match(r'v(\d{4})', v)])
    return versions[-1] if versions else "v0000"

def get_next_version(d):
    # Given a directory that should contain versioned subfolders (v0001..),
    # return the next version string (e.g. 'v0004'). If the directory doesn't
    # exist return 'v0001'. This looks for folders matching v#### and increments
    # the numeric portion.
    if not os.path.exists(d): return "v0001"
    v = [int(m.group(1)) for f in os.listdir(d) if (m := re.match(r'v(\d{4})', f))]
    return f"v{max(v or [0]) + 1:04d}"

# Project archive functions
def mari_project_archive():
    # Archive the current Mari project to a .mra inside the local project's
    # ProjectArchive folder. Steps:
    # 1) Save and close the project (required by mari.projects.archive)
    # 2) Call mari.projects.archive to create the .mra file
    # 3) Re-open the project. User is notified of success/failure via messages.
    project = mari.projects.current()
    if not project:
        mari.utils.message("No project open."); return

    geo = mari.current.geo()
    if not geo.hasMetadata("PrismLocalPath"):
        mari.utils.message("No Local Path linked."); return

    local_path = geo.metadata("PrismLocalPath")
    archive_dir = os.path.normpath(os.path.join(local_path, "ProjectArchive"))
    if not os.path.exists(archive_dir): os.makedirs(archive_dir)

    v_label = get_latest_version_label(os.path.join(local_path, "Textures"))
    proj_info = project.info()
    proj_uuid = proj_info.uuid()
    filename = f"{proj_info.name()}_{v_label}.mra"
    full_local_path = os.path.join(archive_dir, filename).replace("\\", "/")

    # Save and Close
    project.save()
    mari.projects.close()

    # Archive (Project must be closed)
    try:
        mari.projects.archive(proj_uuid, full_local_path)
        mari.utils.message(f"Archive Created: {filename}")
    except Exception as e:
        mari.utils.message(f"Archive Failed: {e}")
    finally:
        # Reopen project
        mari.projects.open(proj_info.name())

def upload_archive_to_global():
    # Copy the most recent .mra from the local ProjectArchive to the Global
    # ProjectArchive folder. Validates that paths are linked and that archives
    # exist locally before copying.
    geo = mari.current.geo()
    if not geo.hasMetadata("PrismLocalPath") or not geo.hasMetadata("PrismGlobalPath"):
        mari.utils.message("Paths not linked correctly."); return

    local_archive_dir = os.path.join(geo.metadata("PrismLocalPath"), "ProjectArchive")
    global_archive_dir = os.path.join(geo.metadata("PrismGlobalPath"), "ProjectArchive")

    if not os.path.exists(local_archive_dir):
        mari.utils.message("No local archives found."); return

    archives = [f for f in os.listdir(local_archive_dir) if f.endswith(".mra")]
    if not archives:
        mari.utils.message("No .mra files in local archive folder."); return
    
    latest_mra = max([os.path.join(local_archive_dir, f) for f in archives], key=os.path.getmtime)
    filename = os.path.basename(latest_mra)

    if not os.path.exists(global_archive_dir): os.makedirs(global_archive_dir)
    shutil.copy2(latest_mra, os.path.join(global_archive_dir, filename))
    mari.utils.message(f"Successfully uploaded {filename} to Global.")

def publish_to_global():
    # Publish the latest local texture version to the Global Textures folder.
    # This function copies the latest v#### folder from local Textures to a new
    # incremented global version folder and writes latest_version.txt.
    geo = mari.current.geo()
    if not geo or not geo.hasMetadata("PrismGlobalPath"): return
    
    local_tex_root = os.path.join(geo.metadata("PrismLocalPath"), "Textures")
    global_tex_root = os.path.join(geo.metadata("PrismGlobalPath"), "Textures")
    
    if not os.path.exists(local_tex_root): return
    local_versions = sorted([v for v in os.listdir(local_tex_root) if re.match(r'v\d{4}', v)])
    if not local_versions: return
        
    latest_local_v = local_versions[-1]
    next_global_v = get_next_version(global_tex_root)
    
    src = os.path.join(local_tex_root, latest_local_v)
    dst = os.path.join(global_tex_root, next_global_v)
    
    if not os.path.exists(global_tex_root): os.makedirs(global_tex_root)
    shutil.copytree(src, dst)
    
    with open(os.path.join(global_tex_root, "latest_version.txt"), "w") as f: f.write(next_global_v)
    mari.utils.message(f"Published local {latest_local_v} to global {next_global_v}.")

def prism_local_export():
    geo = mari.current.geo()
    if not geo or not geo.hasMetadata("PrismLocalPath"):
        mari.utils.message("Missing Metadata: Run Linker first.")
        return

    # Setup Paths
    local_root = os.path.normpath(os.path.join(geo.metadata("PrismLocalPath"), "Textures"))
    version = get_next_version(local_root)
    version_dir = os.path.normpath(os.path.join(local_root, version))
    os.makedirs(version_dir, exist_ok=True)

    asset_name = "MergedAsset" 
    
    all_valid_items = []
    
    # 2. Gather items safely
    for mesh in mari.geo.list():
        # Get items already set in your Export Manager
        items = mari.exports.exportItemList(mesh)
        for i in items:
            if mari.exports.checkExportItemIsValid(i, mesh):
                # Resolve details using the documentation methods
                ext = os.path.splitext(i.fileTemplate())[1] or ".exr"
                colorspace = i.resolveColorspace().replace(" ", "_")
                
                # Get resolution (e.g., "4096 x 4096" -> "4k")
                res_raw = i.sourceResolution()
                res_label = f"{int(res_raw.split('x')[0]) // 1024}k" if "x" in res_raw else "2k"

                # MANDATORY: To merge all meshes into ONE sequence, 
                # we do NOT use $ENTITY. We use a static asset name.
                # Format: MergedAsset_4k_BaseColor_ACEScg.1001.exr
                new_template = f"{asset_name}_{res_label}_$CHANNEL_{colorspace}.$UDIM{ext}"
                
                i.setFileTemplate(new_template)
                all_valid_items.append(i)

    # 3. Execution - The Stability Fix
    if all_valid_items:
        try:
            # We use ShowProgressDialog=False because your logs show 
            # UI/Shortcut conflicts during the export initialization.
            mari.exports.exportTextures(all_valid_items, version_dir, ShowProgressDialog=False)
        except Exception as e:
            print(f"Export failed: {e}")
            return

        # Write versioning and trigger converter
        with open(os.path.join(local_root, "latest_version.txt"), "w") as f:
            f.write(version)

        target = geo.metadata("PrismTargetRenderer")
        if target and target != "None":
            renderer = "k" if "Karma" in target else "a"
            script = "V:/L5_2026/CNB/00_Pipeline/Scripts/txtcvn.py"
            subprocess.Popen(['cmd', '/k', 'python', script, renderer, version_dir], 
                             creationflags=subprocess.CREATE_NEW_CONSOLE)
            
        mari.utils.message(f"Smart Export (All Geo) Successful: {version}")
    else:
        mari.utils.message("No valid export items found.")

def open_folder_logic(metadata_key):
    # Open the folder path stored in the provided metadata key in the OS file
    # browser (Windows Explorer or macOS Finder). Validates that the path
    # exists first.
    geo = mari.current.geo()
    if geo and geo.hasMetadata(metadata_key):
        path = os.path.normpath(geo.metadata(metadata_key))
        if os.path.exists(path):
            if platform.system() == "Windows": subprocess.Popen(f'explorer "{path}"', shell=True)
            else: subprocess.Popen(['open', path])

# Initialization and Menu Setup
def show_linker():
    if mari.projects.current(): PrismProjectLinker().exec_()

def reload_prism_plugin():
    # Reload this plugin module and re-initialize the menu. This is meant for
    # quick development/testing while running inside Mari.
    import Prism_Link
    importlib.reload(Prism_Link)
    Prism_Link.initialize_plugin()
    mari.utils.message("Prism Plugin Reloaded!")

def initialize_plugin():
    # Build the Prism menu, removing any previous menu first, then adding
    # actions for Link, Export, Archive, Publish, Open folder, and Reload.
    # Each menu action executes a small Python command that calls the
    # corresponding function in this module.
    try: mari.menus.removeMenu("MainWindow/Prism")
    except: pass
    module_name = "Prism_Link"
    
    actions = [
        ("Prism/Link", "Link Prism Asset...", f"import {module_name}; {module_name}.show_linker()"),
        ("Prism/Export", "Run Prism Smart Export", f"import {module_name}; {module_name}.prism_local_export()"),
        ("Prism/ArchiveLocal", "Archive Mari Project (Local)", f"import {module_name}; {module_name}.mari_project_archive()"),
        ("Prism/Sep1", "-", ""),
        ("Prism/Publish", "Publish Textures to Global", f"import {module_name}; {module_name}.publish_to_global()"),
        ("Prism/ArchiveGlobal", "Upload Latest Archive to Global", f"import {module_name}; {module_name}.upload_archive_to_global()"),
        ("Prism/Sep2", "-", ""),
        ("Prism/OpenLocal", "Open Local Folder", f"import {module_name}; {module_name}.open_local_folder()"),
        ("Prism/OpenGlobal", "Open Global Folder", f"import {module_name}; {module_name}.open_global_folder()"),
        ("Prism/Sep3", "-", ""),
        ("Prism/Reload", "RELOAD SCRIPT", f"import {module_name}; {module_name}.reload_prism_plugin()")
    ]
    
    for action_id, label, cmd in actions:
        existing = mari.actions.find(action_id)
        if existing: mari.actions.remove(action_id)
        if label == "-":
            mari.menus.addSeparator("MainWindow/Prism")
        else:
            act = mari.actions.create(action_id, cmd); act.setText(label)
            mari.menus.addAction(act, "MainWindow/Prism")

def open_local_folder(): open_folder_logic("PrismLocalPath")
def open_global_folder(): open_folder_logic("PrismGlobalPath")

# Schedule plugin initialization shortly after Mari starts so menus are added
QtCore.QTimer.singleShot(2500, initialize_plugin)