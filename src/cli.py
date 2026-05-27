#!/usr/bin/env python3
import os
import sys
import shutil
import tempfile
import zipfile
import struct
import zlib
import argparse
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

MAGIC = b'ENCRYPTO'
VERSION = 2
ITERATIONS = 100000


def get_human_size(size_in_bytes):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_in_bytes < 1024.0:
            return f"{size_in_bytes:.2f} {unit}"
        size_in_bytes /= 1024.0
    return f"{size_in_bytes:.2f} PB"


def inspect(path):
    if not os.path.exists(path):
        return {"error": "File does not exist"}
    try:
        with open(path, 'rb') as f:
            magic = f.read(8)
            if magic != MAGIC:
                return {"error": "Not a valid ENCRYPTO file"}
            file_version = ord(f.read(1))
            is_folder = ord(f.read(1)) == 1
            salt = f.read(16)
            nonce = f.read(12)
            name_len = struct.unpack('>H', f.read(2))[0]
            name = f.read(name_len).decode('utf-8')
            hint_len = struct.unpack('>H', f.read(2))[0]
            hint = f.read(hint_len).decode('utf-8')
        return {
            "original_name": name,
            "hint": hint,
            "is_folder": is_folder,
            "version": file_version
        }
    except Exception as e:
        return {"error": str(e)}


def encrypt(path, password, hint=""):
    if not os.path.exists(path):
        return {"error": "Path does not exist"}
    try:
        is_folder = os.path.isdir(path)
        name = os.path.basename(path)
        salt = os.urandom(16)
        nonce = os.urandom(12)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=ITERATIONS
        )
        key = kdf.derive(password.encode('utf-8'))
        if is_folder:
            tmp_dir = tempfile.mkdtemp(prefix="encrypto_")
            tmp_zip = os.path.join(tmp_dir, "archive.zip")
            with zipfile.ZipFile(tmp_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(path):
                    for file in files:
                        abs_path = os.path.join(root, file)
                        rel_path = os.path.relpath(abs_path, path)
                        zipf.write(abs_path, rel_path)
            with open(tmp_zip, 'rb') as f:
                raw_data = f.read()
            shutil.rmtree(tmp_dir, ignore_errors=True)
        else:
            with open(path, 'rb') as f:
                raw_data = f.read()
        compressed = zlib.compress(raw_data, level=9)
        del raw_data
        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(nonce, compressed, None)
        del compressed
        output = bytearray()
        output.extend(MAGIC)
        output.append(VERSION)
        output.append(1 if is_folder else 0)
        output.extend(salt)
        output.extend(nonce)
        name_bytes = name.encode('utf-8')
        output.extend(struct.pack('>H', len(name_bytes)))
        output.extend(name_bytes)
        hint_bytes = hint.encode('utf-8')
        output.extend(struct.pack('>H', len(hint_bytes)))
        output.extend(hint_bytes)
        output.extend(ciphertext)
        return {"success": True, "data": bytes(output), "name": name, "is_folder": is_folder}
    except Exception as e:
        return {"error": str(e)}


def decrypt(path, password):
    if not os.path.exists(path):
        return {"error": "File does not exist"}
    try:
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
        aesgcm = AESGCM(key)
        try:
            decrypted_compressed = aesgcm.decrypt(nonce, ciphertext, None)
        except Exception:
            return {"error": "Wrong password"}
        if file_version >= 2:
            plaintext = zlib.decompress(decrypted_compressed)
        else:
            plaintext = decrypted_compressed
        return {
            "success": True,
            "data": plaintext,
            "name": original_name,
            "is_folder": is_folder
        }
    except Exception as e:
        return {"error": str(e)}


def cmd_inspect(args):
    result = inspect(args.path)
    if "error" in result:
        print(f"[ERROR] {result['error']}")
        sys.exit(1)
    print(f"Original name: {result['original_name']}")
    print(f"Type: {'Folder' if result['is_folder'] else 'File'}")
    print(f"Hint: {result['hint']}")
    print(f"Format version: {result['version']}")


def cmd_encrypt(args):
    password = args.password or os.environ.get('ENCRYPTO_PASSWORD')
    if not password:
        import getpass
        password = getpass.getpass("Password: ")
    if args.hint:
        hint = args.hint
    else:
        hint = ""
    result = encrypt(args.path, password, hint)
    if "error" in result:
        print(f"[ERROR] {result['error']}")
        sys.exit(1)
    output_path = args.output
    if not output_path:
        base = os.path.splitext(result['name'])[0]
        output_path = base + ".crypto"
    with open(output_path, 'wb') as f:
        f.write(result['data'])
    size = os.path.getsize(output_path)
    print(f"[OK] Encrypted: {output_path} ({get_human_size(size)})")


def cmd_decrypt(args):
    password = args.password or os.environ.get('ENCRYPTO_PASSWORD')
    if not password:
        import getpass
        password = getpass.getpass("Password: ")
    result = decrypt(args.path, password)
    if "error" in result:
        if result['error'] == "Wrong password":
            print("[ERROR] Wrong password")
        else:
            print(f"[ERROR] {result['error']}")
        sys.exit(1)
    output_path = args.output
    if not output_path:
        output_path = result['name']
    else:
        orig_ext = os.path.splitext(result['name'])[1]
        if orig_ext and not output_path.endswith(orig_ext):
            output_path += orig_ext
    if result['is_folder']:
        os.makedirs(output_path, exist_ok=True)
        tmp_dir = tempfile.mkdtemp(prefix="encrypto_extract_")
        tmp_zip = os.path.join(tmp_dir, "out.zip")
        with open(tmp_zip, 'wb') as f:
            f.write(result['data'])
        with zipfile.ZipFile(tmp_zip, 'r') as zf:
            zf.extractall(output_path)
        shutil.rmtree(tmp_dir, ignore_errors=True)
        print(f"[OK] Decrypted folder: {output_path}/")
    else:
        with open(output_path, 'wb') as f:
            f.write(result['data'])
        size = os.path.getsize(output_path)
        print(f"[OK] Decrypted: {output_path} ({get_human_size(size)})")


def cmd_help():
    print("""ENCRYPTO - Secure File Encryption Tool

Usage:
  python cli.py <command> [options]

Commands:
  encrypt   Encrypt a file or folder
  decrypt   Decrypt a .crypto file
  inspect   Show metadata of a .crypto file
  help      Show this help message

Options:
  encrypt <path> [-o <output>] [-p <password>] [--hint <hint>]
  decrypt <path> [-o <output>] [-p <password>]
  inspect <file>

Examples:
  python cli.py encrypt document.pdf -p mypassword --hint "my birthday"
  python cli.py encrypt myfolder/ -o backup.crypto
  python cli.py decrypt secret.crypto -o restored.pdf
  python cli.py decrypt secret.crypto -p mypassword
  python cli.py inspect secret.crypto

Environment:
  ENCRYPTO_PASSWORD  Set password to avoid interactive prompt
""")

def main():
    parser = argparse.ArgumentParser(
        prog="ENCRYPTO",
        description="Secure File Encryption Tool",
        add_help=False
    )
    parser.add_argument("command", nargs="?", default=None,
                        help="Command: encrypt, decrypt, inspect, help")
    parser.add_argument("path", nargs="?", default=None)
    parser.add_argument("-o", "--output", default=None)
    parser.add_argument("-p", "--password", default=None)
    parser.add_argument("--hint", default=None)
    parser.add_argument("-h", "--help", action="store_true", dest="show_help")

    args, unknown = parser.parse_known_args()

    if args.show_help or args.command is None or args.command == "help":
        cmd_help()
        return

    if args.command not in ("encrypt", "decrypt", "inspect"):
        print(f"[ERROR] Unknown command: {args.command}")
        print("Use: python cli.py help")
        sys.exit(1)

    if args.command == "encrypt":
        if not args.path:
            print("[ERROR] Missing path to encrypt")
            sys.exit(1)
        cmd_encrypt(args)
    elif args.command == "decrypt":
        if not args.path:
            print("[ERROR] Missing .crypto file to decrypt")
            sys.exit(1)
        cmd_decrypt(args)
    elif args.command == "inspect":
        if not args.path:
            print("[ERROR] Missing .crypto file to inspect")
            sys.exit(1)
        cmd_inspect(args)


if __name__ == '__main__':
    main()
