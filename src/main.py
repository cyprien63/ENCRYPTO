import os
import sys
import shutil
import tempfile
import zipfile
import struct
import threading
import zlib

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

import kivy
kivy.require('2.2.0')
from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import StringProperty, NumericProperty, BooleanProperty
from kivy.uix.screenmanager import Screen
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.uix.button import Button

MAGIC = b'ENCRYPTO'
VERSION = 2
ITERATIONS = 100000


class EncryptoCore:
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp(prefix="encrypto_")
        self.temp_encrypted_path = os.path.join(self.temp_dir, "temp.crypto")
        self.temp_decrypted_path = os.path.join(self.temp_dir, "temp.decrypted")
        self.decrypted_name = ""
        self.decrypted_is_folder = False

    def get_human_size(self, size_in_bytes):
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_in_bytes < 1024.0:
                return f"{size_in_bytes:.2f} {unit}"
            size_in_bytes /= 1024.0
        return f"{size_in_bytes:.2f} PB"

    def inspect_crypto_file(self, path):
        try:
            with open(path, 'rb') as f:
                magic = f.read(8)
                if magic != MAGIC:
                    return None
                file_version = ord(f.read(1))
                is_folder = ord(f.read(1)) == 1
                salt = f.read(16)
                nonce = f.read(12)
                name_len = struct.unpack('>H', f.read(2))[0]
                name = f.read(name_len).decode('utf-8')
                hint_len = struct.unpack('>H', f.read(2))[0]
                hint = f.read(hint_len).decode('utf-8')
            return {"name": name, "hint": hint, "isFolder": is_folder, "version": file_version}
        except Exception:
            return None

    def encrypt(self, path, password, hint, progress_callback):
        try:
            is_folder = os.path.isdir(path)
            name = os.path.basename(path)
            progress_callback(5)
            salt = os.urandom(16)
            nonce = os.urandom(12)
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=ITERATIONS
            )
            key = kdf.derive(password.encode('utf-8'))
            progress_callback(15)
            if is_folder:
                temp_zip = os.path.join(self.temp_dir, "archive.zip")
                self._zip_directory(path, temp_zip)
                with open(temp_zip, 'rb') as f:
                    raw_data = f.read()
                try:
                    os.remove(temp_zip)
                except:
                    pass
            else:
                with open(path, 'rb') as f:
                    raw_data = f.read()
            progress_callback(40)
            compressed_data = zlib.compress(raw_data, level=9)
            del raw_data
            progress_callback(70)
            aesgcm = AESGCM(key)
            ciphertext = aesgcm.encrypt(nonce, compressed_data, None)
            del compressed_data
            progress_callback(90)
            with open(self.temp_encrypted_path, 'wb') as f:
                f.write(MAGIC)
                f.write(bytes([VERSION]))
                f.write(bytes([1 if is_folder else 0]))
                f.write(salt)
                f.write(nonce)
                name_bytes = name.encode('utf-8')
                f.write(struct.pack('>H', len(name_bytes)))
                f.write(name_bytes)
                hint_bytes = hint.encode('utf-8')
                f.write(struct.pack('>H', len(hint_bytes)))
                f.write(hint_bytes)
                f.write(ciphertext)
            progress_callback(100)
            return {"success": True, "name": name, "isFolder": is_folder}
        except Exception as e:
            return {"error": str(e)}

    def decrypt(self, path, password, progress_callback):
        try:
            progress_callback(10)
            with open(path, 'rb') as f:
                magic = f.read(8)
                if magic != MAGIC:
                    return {"error": "Not a valid ENCRYPTO file"}
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
            progress_callback(40)
            aesgcm = AESGCM(key)
            try:
                decrypted_compressed = aesgcm.decrypt(nonce, ciphertext, None)
            except Exception:
                return {"error": "wrong_password"}
            progress_callback(70)
            if file_version >= 2:
                plaintext = zlib.decompress(decrypted_compressed)
            else:
                plaintext = decrypted_compressed
            self.decrypted_name = original_name
            self.decrypted_is_folder = is_folder
            if is_folder:
                self.temp_zip_decrypted = os.path.join(self.temp_dir, "temp_decrypted.zip")
                with open(self.temp_zip_decrypted, 'wb') as f:
                    f.write(plaintext)
            else:
                with open(self.temp_decrypted_path, 'wb') as f:
                    f.write(plaintext)
            progress_callback(100)
            return {"success": True, "name": original_name, "isFolder": is_folder}
        except Exception as e:
            return {"error": str(e)}

    def save_encrypted(self, dest_path):
        shutil.copy(self.temp_encrypted_path, dest_path)

    def save_decrypted(self, dest_path, is_folder):
        if is_folder:
            os.makedirs(dest_path, exist_ok=True)
            self._unzip_directory(self.temp_zip_decrypted, dest_path)
            try:
                os.remove(self.temp_zip_decrypted)
            except:
                pass
        else:
            shutil.copy(self.temp_decrypted_path, dest_path)

    def cleanup(self):
        try:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception:
            pass

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


class MainScreen(Screen):
    pass


class BrowserScreen(Screen):
    current_path = StringProperty("")

    def on_enter(self):
        app = App.get_running_app()
        self.load_directory(app.browser_root)

    def load_directory(self, path):
        app = App.get_running_app()
        layout = self.ids.entries_layout
        layout.clear_widgets()
        try:
            entries = sorted(os.listdir(path))
            has_parent = os.path.dirname(path) != path
            if has_parent:
                parent = os.path.dirname(path)
                if parent and os.path.isdir(parent):
                    btn = FileEntryButton(
                        label="..",
                        entry_type="parent",
                        entry_path=parent,
                        size_hint_y=None,
                        height=56
                    )
                    btn.bind(on_release=self._on_entry)
                    layout.add_widget(btn)

            for name in entries:
                full = os.path.join(path, name)
                try:
                    is_dir = os.path.isdir(full)
                    entry_type = "dir" if is_dir else "file"
                    icon = "\U0001F4C1  " if is_dir else "\U0001F4C4  "
                    size = "" if is_dir else app.core.get_human_size(os.path.getsize(full))
                    label_text = icon + name
                    if size:
                        label_text += "    " + size
                    btn = FileEntryButton(
                        label=label_text,
                        entry_type=entry_type,
                        entry_path=full,
                        size_hint_y=None,
                        height=56
                    )
                    btn.bind(on_release=self._on_entry)
                    layout.add_widget(btn)
                except:
                    pass
            self.current_path = path
        except Exception as e:
            popup = Popup(title="Error", content=Label(text=str(e)), size_hint=(0.8, 0.4))
            popup.open()

    def _on_entry(self, btn):
        app = App.get_running_app()
        if btn.entry_type == "parent":
            self.load_directory(btn.entry_path)
        elif btn.entry_type == "dir":
            self.load_directory(btn.entry_path)
        else:
            app.select_path(btn.entry_path)


class FileEntryButton(Button):
    def __init__(self, label="", entry_type="", entry_path="", **kwargs):
        super().__init__(**kwargs)
        self.entry_type = entry_type
        self.entry_path = entry_path
        self.text = label
        self.background_normal = ""
        self.background_color = (0.16, 0.16, 0.16, 1)
        self.halign = "left"
        self.valign = "middle"
        self.text_size = (self.width, self.height)
        self.bind(size=lambda s, v: setattr(self, 'text_size', (v[0], v[1])))


class DetailScreen(Screen):
    file_name = StringProperty("")
    file_size = StringProperty("")
    is_crypto = BooleanProperty(False)
    is_folder = BooleanProperty(False)
    crypto_hint = StringProperty("")
    mode = StringProperty("encrypt")

    def on_enter(self):
        app = App.get_running_app()
        name = app.selected_name
        size = app.selected_size
        self.file_name = name
        self.file_size = size
        is_crypto = name.lower().endswith(".crypto")
        self.is_crypto = is_crypto
        self.is_folder = app.selected_is_folder
        self.mode = "decrypt" if is_crypto else "encrypt"

        info = None
        if is_crypto:
            info = app.core.inspect_crypto_file(app.selected_path)
        self.crypto_hint = info["hint"] if info else ""

        self.ids.password_input.text = ""
        self.ids.hint_input.text = ""
        self.ids.password_input.hint_text = f"Password (Hint: {self.crypto_hint})" if self.crypto_hint else "Password"
        self.ids.hint_box.opacity = 0 if is_crypto else 1
        self.ids.hint_box.disabled = is_crypto
        self.ids.action_btn.text = "DECRYPT" if is_crypto else "ENCRYPT"

    def do_action(self):
        app = App.get_running_app()
        pw = self.ids.password_input.text
        if not pw:
            return
        hint = self.ids.hint_input.text
        app.start_operation(self.mode, pw, hint)


class ProgressScreen(Screen):
    file_name = StringProperty("")
    progress = NumericProperty(0)


class DoneScreen(Screen):
    result_name = StringProperty("")
    is_folder = BooleanProperty(False)
    mode = StringProperty("encrypt")


class EncryptoApp(App):
    core = EncryptoCore()

    selected_path = ""
    selected_name = ""
    selected_size = ""
    selected_is_folder = False
    browser_root = os.path.expanduser("~")
    output_dir = ""

    def build(self):
        self.title = "ENCRYPTO"
        self.output_dir = os.path.join(os.path.expanduser("~"), "ENCRYPTO")
        os.makedirs(self.output_dir, exist_ok=True)
        kv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.kv")
        return Builder.load_file(kv_path)

    def select_path(self, path):
        self.selected_path = path
        self.selected_name = os.path.basename(path)
        self.selected_is_folder = os.path.isdir(path)
        if self.selected_is_folder:
            total_size = 0
            for dirpath, _, filenames in os.walk(path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    if os.path.exists(fp):
                        total_size += os.path.getsize(fp)
            self.selected_size = self.core.get_human_size(total_size)
        else:
            self.selected_size = self.core.get_human_size(os.path.getsize(path))
        self.root.current = "detail"

    def show_browser(self):
        self.root.current = "browser"

    def go_main(self):
        self.root.current = "main"

    def start_operation(self, mode, password, hint=""):
        self.root.get_screen("progress").file_name = self.selected_name
        self.root.get_screen("progress").progress = 0
        self.root.current = "progress"
        threading.Thread(target=self._run_op, args=(mode, password, hint), daemon=True).start()

    def _run_op(self, mode, password, hint):
        if mode == "encrypt":
            result = self.core.encrypt(self.selected_path, password, hint, self._progress_update)
        else:
            result = self.core.decrypt(self.selected_path, password, self._progress_update)
        Clock.schedule_once(lambda dt: self._op_finished(result, mode))

    def _progress_update(self, value):
        Clock.schedule_once(lambda dt: setattr(self.root.get_screen("progress"), "progress", value))

    def _op_finished(self, result, mode):
        if "error" in result:
            if result["error"] == "wrong_password":
                popup = Popup(title="Error", content=Label(text="Wrong password"), size_hint=(0.8, 0.4))
                popup.open()
                self.root.current = "detail"
            else:
                popup = Popup(title="Error", content=Label(text=result["error"]), size_hint=(0.8, 0.4))
                popup.open()
                self.root.current = "main"
            return
        done = self.root.get_screen("done")
        done.result_name = result["name"]
        done.is_folder = result.get("isFolder", False)
        done.mode = mode
        self.root.current = "done"

    def save_result(self):
        done = self.root.get_screen("done")
        name = done.result_name
        is_folder = done.is_folder
        mode = done.mode
        if mode == "encrypt":
            base = os.path.splitext(name)[0]
            dest = os.path.join(self.output_dir, base + ".crypto")
            self.core.save_encrypted(dest)
        else:
            dest = os.path.join(self.output_dir, name)
            if is_folder:
                self.core.save_decrypted(dest, True)
            else:
                self.core.save_decrypted(dest, False)
        self.root.current = "main"

    def on_stop(self):
        self.core.cleanup()


if __name__ == '__main__':
    EncryptoApp().run()
