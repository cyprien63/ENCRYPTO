# -*- coding: utf-8 -*-
import os
import sys
import shutil
import tempfile
import zipfile
import struct
import threading
import time
import base64
import webview
import ctypes
import zlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

# Windows Shell API (only imported on Windows)
if sys.platform == 'win32':
    from ctypes import wintypes
    SHGFI_ICON = 0x000000100
    SHGFI_LARGEICON = 0x000000000
    SHGFI_USEFILEATTRIBUTES = 0x000000010
    class SHFILEINFO(ctypes.Structure):
        _fields_ = [
            ("hIcon", wintypes.HANDLE),
            ("iIcon", ctypes.c_int),
            ("dwAttributes", wintypes.DWORD),
            ("szDisplayName", wintypes.CHAR * 260),
            ("szTypeName", wintypes.CHAR * 80)
        ]
else:
    SHGFI_ICON = SHGFI_LARGEICON = SHGFI_USEFILEATTRIBUTES = 0

# Configuration
MAGIC = b'ENCRYPTO'
VERSION = 2 # Incremented for compression support
ITERATIONS = 100000

class EncryptoApi:
    def __init__(self):
        self._window = None
        self.active_path = None
        self.active_name = ""
        self.active_size = 0
        self.active_is_folder = False
        self.active_icon = "" # Base64 icon

        # Temp file tracking
        self.temp_dir = tempfile.mkdtemp(prefix="encrypto_")
        self.temp_encrypted_path = os.path.join(self.temp_dir, "temp.crypto")
        self.temp_decrypted_path = os.path.join(self.temp_dir, "temp.decrypted")
        self.decrypted_name = ""
        self.decrypted_is_folder = False

    def set_window(self, window):
        self._window = window

    def minimize_window(self):
        """Minimize the desktop window."""
        if self._window:
            self._window.minimize()

    def close_window(self):
        """Close the desktop window and exit."""
        if self._window:
            self._window.destroy()

    def get_human_size(self, size_in_bytes):
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_in_bytes < 1024.0:
                return f"{size_in_bytes:.2f} {unit}"
            size_in_bytes /= 1024.0
        return f"{size_in_bytes:.2f} PB"

    def select_file(self):
        """Open native file dialog and load file details."""
        try:
            result = self._window.create_file_dialog(webview.FileDialog.OPEN)
            if result and len(result) > 0:
                path = result[0]
                return self.load_path_info(path)
            return None
        except Exception as e:
            print(f"Error in select_file: {e}")
            return {"error": str(e)}

    def select_folder(self):
        """Open native folder dialog and load folder details."""
        try:
            result = self._window.create_file_dialog(webview.FileDialog.FOLDER)
            if result and len(result) > 0:
                path = result[0]
                return self.load_path_info(path)
            return None
        except Exception as e:
            print(f"Error in select_folder: {e}")
            return {"error": str(e)}

    def load_file_from_js(self, name, data_b64):
        try:
            file_path = os.path.join(self.temp_dir, name)
            raw = base64.b64decode(data_b64)
            with open(file_path, 'wb') as f:
                f.write(raw)
            return self.load_path_info(file_path)
        except Exception as e:
            return {"error": str(e)}

    def get_system_icon(self, path):
        """Extract high-quality system icon for Windows files/folders."""
        if sys.platform != 'win32':
            return ""

        try:
            shell32 = ctypes.windll.shell32
            user32 = ctypes.windll.user32

            shfi = SHFILEINFO()
            flags = SHGFI_ICON | SHGFI_LARGEICON

            # If path doesn't exist yet, use attributes flag
            if not os.path.exists(path):
                flags |= SHGFI_USEFILEATTRIBUTES

            ret = shell32.SHGetFileInfoW(
                ctypes.c_wchar_p(path),
                0,
                ctypes.byref(shfi),
                ctypes.sizeof(shfi),
                flags
            )

            if not ret or not shfi.hIcon:
                return ""

            user32.DestroyIcon(shfi.hIcon)
            return ""
        except:
            return ""

    def load_path_info(self, path):
        """Load file or folder info and return JSON metadata to JS."""
        if not os.path.exists(path):
            return {"error": "File or folder does not exist"}

        self.active_path = path
        self.active_name = os.path.basename(path)
        if not self.active_name: # Handle root drives like C:\
            self.active_name = path.replace(":", "").replace("\\", "").replace("/", "")

        self.active_is_folder = os.path.isdir(path)

        if self.active_is_folder:
            # Calculate folder size
            total_size = 0
            for dirpath, _, filenames in os.walk(path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    if os.path.exists(fp):
                        total_size += os.path.getsize(fp)
            self.active_size = total_size
        else:
            self.active_size = os.path.getsize(path)

        return {
            "name": self.active_name,
            "size": self.get_human_size(self.active_size),
            "isFolder": self.active_is_folder,
            "path": self.active_path,
            "isCryptoFile": self.active_name.lower().endswith(".crypto")
        }

    def inspect_crypto_file(self, path):
        """Inspect a .crypto file to retrieve password hint and name."""
        try:
            if not os.path.exists(path):
                return {"error": "File does not exist"}

            with open(path, 'rb') as f:
                magic = f.read(8)
                if magic != MAGIC:
                    return {"error": "Invalid file format. Not an ENCRYPTO file."}

                file_version = ord(f.read(1))
                is_folder = ord(f.read(1)) == 1
                salt = f.read(16)
                nonce = f.read(12)

                name_len = struct.unpack('>H', f.read(2))[0]
                name = f.read(name_len).decode('utf-8')

                hint_len = struct.unpack('>H', f.read(2))[0]
                hint = f.read(hint_len).decode('utf-8')

            return {
                "name": name,
                "hint": hint,
                "isFolder": is_folder,
                "path": path,
                "version": file_version
            }
        except Exception as e:
            return {"error": f"Failed to read crypto file: {str(e)}"}

    def encrypt_target(self, password, hint=""):
        """Encrypt the loaded file or folder in a separate background thread."""
        if not self.active_path:
            return {"error": "No file or folder selected"}

        # Run in thread so the UI animations remain active and smooth
        threading.Thread(target=self._run_encryption, args=(password, hint), daemon=True).start()
        return {"status": "started"}

    def _run_encryption(self, password, hint):
        try:
            self._window.evaluate_js("onProgress(5)")

            salt = os.urandom(16)
            nonce = os.urandom(12)

            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=ITERATIONS
            )
            key = kdf.derive(password.encode('utf-8'))

            self._window.evaluate_js("onProgress(15)")

            # Prepare data (Folder or Single File)
            if self.active_is_folder:
                temp_zip = os.path.join(self.temp_dir, "archive.zip")
                self._zip_directory(self.active_path, temp_zip)
                with open(temp_zip, 'rb') as f:
                    raw_data = f.read()
                try:
                    os.remove(temp_zip)
                except:
                    pass
            else:
                with open(self.active_path, 'rb') as f:
                    raw_data = f.read()

            self._window.evaluate_js("onProgress(40)")

            # 1. HIGH PERFORMANCE COMPRESSION (Level 9)
            # This uses max PC performance to shrink data before encryption
            compressed_data = zlib.compress(raw_data, level=9)
            del raw_data # Immediate memory release

            self._window.evaluate_js("onProgress(70)")

            # 2. ENCRYPTION
            aesgcm = AESGCM(key)
            ciphertext = aesgcm.encrypt(nonce, compressed_data, None)
            del compressed_data

            self._window.evaluate_js("onProgress(90)")

            # Write custom file structure
            with open(self.temp_encrypted_path, 'wb') as f:
                f.write(MAGIC)
                f.write(bytes([VERSION]))
                f.write(bytes([1 if self.active_is_folder else 0]))
                f.write(salt)
                f.write(nonce)

                name_bytes = self.active_name.encode('utf-8')
                f.write(struct.pack('>H', len(name_bytes)))
                f.write(name_bytes)

                hint_bytes = hint.encode('utf-8')
                f.write(struct.pack('>H', len(hint_bytes)))
                f.write(hint_bytes)

                f.write(ciphertext)

            self._window.evaluate_js("onProgress(100)")
            time.sleep(0.3)

            # Return success to UI
            self._window.evaluate_js(f"onEncryptionComplete('{self.active_name}', {1 if self.active_is_folder else 0})")

        except Exception as e:
            print(f"Encryption error: {e}")
            self._window.evaluate_js(f"onOperationError('{str(e)}')")

    def decrypt_target(self, password):
        """Decrypt the loaded .crypto file in a background thread."""
        if not self.active_path:
            return {"error": "No crypto file loaded"}

        threading.Thread(target=self._run_decryption, args=(password,), daemon=True).start()
        return {"status": "started"}

    def _run_decryption(self, password):
        try:
            self._window.evaluate_js("onProgress(10)")
            time.sleep(0.2)

            with open(self.active_path, 'rb') as f:
                magic = f.read(8)
                if magic != MAGIC:
                    self._window.evaluate_js("onOperationError('Not a valid ENCRYPTO file')")
                    return

                file_version = ord(f.read(1))
                is_folder = ord(f.read(1)) == 1
                salt = f.read(16)
                nonce = f.read(12)

                name_len = struct.unpack('>H', f.read(2))[0]
                original_name = f.read(name_len).decode('utf-8')

                hint_len = struct.unpack('>H', f.read(2))[0]
                hint = f.read(hint_len).decode('utf-8')

                ciphertext = f.read()

            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=ITERATIONS
            )
            key = kdf.derive(password.encode('utf-8'))

            self._window.evaluate_js("onProgress(40)")

            # DECRYPT
            aesgcm = AESGCM(key)
            try:
                decrypted_compressed = aesgcm.decrypt(nonce, ciphertext, None)
            except Exception:
                self._window.evaluate_js("onDecryptionFailed()")
                return

            self._window.evaluate_js("onProgress(70)")

            # DECOMPRESS (Handle both compressed V2 and legacy V1 uncompressed)
            if file_version >= 2:
                plaintext = zlib.decompress(decrypted_compressed)
            else:
                plaintext = decrypted_compressed

            self.decrypted_name = original_name
            self.decrypted_is_folder = is_folder

            if is_folder:
                # Decrypted bytes are a zip file. Write to temp zip, extract later
                self.temp_zip_decrypted = os.path.join(self.temp_dir, "temp_decrypted.zip")
                with open(self.temp_zip_decrypted, 'wb') as f:
                    f.write(plaintext)
            else:
                with open(self.temp_decrypted_path, 'wb') as f:
                    f.write(plaintext)

            self._window.evaluate_js("onProgress(100)")
            time.sleep(0.3)

            self._window.evaluate_js(f"onDecryptionComplete('{self.decrypted_name}', {1 if self.decrypted_is_folder else 0})")

        except Exception as e:
            print(f"Decryption error: {e}")
            self._window.evaluate_js(f"onOperationError('{str(e)}')")

    def save_output(self, mode):
        """Trigger Save File/Folder dialog and write output to user's desired path."""
        try:
            if mode == 'encrypt':
                base_name = os.path.splitext(self.active_name)[0]
                default_name = base_name + ".crypto"

                result = self._window.create_file_dialog(
                    webview.FileDialog.SAVE,
                    os.path.dirname(self.active_path),
                    default_name
                )

                if result:
                    save_path = result[0] if isinstance(result, (list, tuple)) else result
                    if not save_path.lower().endswith(".crypto"):
                        save_path += ".crypto"

                    shutil.copy(self.temp_encrypted_path, save_path)
                    return {"success": True, "saved_path": save_path}

            elif mode == 'decrypt':
                default_name = self.decrypted_name
                if self.decrypted_is_folder:
                    result = self._window.create_file_dialog(
                        webview.FileDialog.FOLDER,
                        os.path.dirname(self.active_path)
                    )
                    if result:
                        save_path = result[0] if isinstance(result, (list, tuple)) else result
                        target_dir = os.path.join(save_path, default_name)
                        if os.path.exists(target_dir):
                            suffix = 1
                            while os.path.exists(f"{target_dir} ({suffix})"):
                                suffix += 1
                            target_dir = f"{target_dir} ({suffix})"

                        os.makedirs(target_dir, exist_ok=True)
                        self._unzip_directory(self.temp_zip_decrypted, target_dir)
                        try:
                            os.remove(self.temp_zip_decrypted)
                        except:
                            pass
                        return {"success": True, "saved_path": target_dir}
                else:
                    result = self._window.create_file_dialog(
                        webview.FileDialog.SAVE,
                        os.path.dirname(self.active_path),
                        default_name
                    )
                    if result:
                        save_path = result[0] if isinstance(result, (list, tuple)) else result
                        orig_ext = os.path.splitext(self.decrypted_name)[1]
                        if orig_ext and not save_path.endswith(orig_ext):
                            save_path += orig_ext
                        shutil.copy(self.temp_decrypted_path, save_path)
                        return {"success": True, "saved_path": save_path}

            return None
        except Exception as e:
            print(f"Save output error: {e}")
            return {"error": str(e)}

    def cleanup(self):
        """Remove temporary directory."""
        try:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception as e:
            print(f"Cleanup error: {e}")

    def _zip_directory(self, dir_path, zip_path):
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(dir_path):
                for file in files:
                    abs_path = os.path.join(root, file)
                    rel_path = os.path.relpath(abs_path, dir_path)
                    zipf.write(abs_path, rel_path)

    def _unzip_directory(self, zip_path, dest_dir):
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            zipf.extractall(dest_dir)


def print_logo():
    """Print the ENCRYPTO logo to terminal from image.png or fallback text."""
    try:
        from PIL import Image
        if getattr(sys, 'frozen', False):
            logo_path = os.path.join(sys._MEIPASS, 'image.png')
        else:
            logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'image.png')
        if os.path.exists(logo_path):
            img = Image.open(logo_path).convert('L')
            w, h = img.size
            ratio = h / w * 0.5
            nw = 100
            nh = int(nw * ratio)
            img = img.resize((nw, nh))
            chars = '@%#*+=-:. '
            pixels = list(img.getdata())
            for y in range(nh):
                line = ''
                for x in range(nw):
                    p = pixels[y * nw + x]
                    line += chars[min(p * (len(chars) - 1) // 256, len(chars) - 1)]
                print(line)
            return
    except Exception:
        pass
    print(' ' * 15 + '  _______ _   _  _____  _____  _   _ _____  ______   _____  ')
    print(r' ' * 15 + ' |__   __| \ | |/ ____|/ ____|| \ | |  __ \|  ____| / ____| ')
    print(r' ' * 15 + '    | |  |  \| | |    | |     |  \| | |__) | |__   | (___  ')
    print(r' ' * 15 + '    | |  | . ` | |    | |     | . ` |  ___/|  __|   \___ \ ')
    print(r' ' * 15 + '    | |  | |\  | |____| |____ | |\  | |    | |____  ____) |')
    print(r' ' * 15 + '    |_|  |_| \_|\_____|\_____||_| \_|_|    |______||_____/')
    print()
    print()
    print(' ' * 25 + 'Secure File Encryption')
    print()

if __name__ == '__main__':
    print_logo()

    api = EncryptoApi()

    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    gui_dir = os.path.join(base_path, 'web')
    html_path = os.path.join(gui_dir, 'index.html')
    if not os.path.exists(html_path):
        html_path = 'web/index.html'

    window = webview.create_window(
        title='ENCRYPTO',
        url=html_path,
        js_api=api,
        width=320,
        height=550,
        resizable=False,
        frameless=True,
        background_color='#1e1e1e'
    )

    api.set_window(window)

    try:
        webview.start(debug=False)
    finally:
        api.cleanup()
