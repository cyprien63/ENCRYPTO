# ENCRYPTO CLI

## Usage

```bash
python src/cli.py <command> [options]
```

---

## How It Works

1. **encrypt**: reads the file (or zips a folder), compresses with zlib (level 9), derives a 256-bit key from your password via PBKDF2-HMAC-SHA256 (100k iterations + random salt), encrypts with AES-256-GCM (random nonce), and writes a `.crypto` file.
2. **decrypt**: reads the `.crypto` header (salt + nonce + name + hint), derives the key, authenticates + decrypts with AES-GCM, decompresses with zlib, and writes the original file (or extracts the folder).
3. **inspect**: reads the header without decrypting — shows original name, password hint, and whether it was a folder.

---

## Commands

### `encrypt` — Encrypt a file or folder

```bash
python src/cli.py encrypt <path> [-o <output>] [-p <password>] [--hint <hint>]
```

| Argument | Description |
|----------|-------------|
| `path` | File or folder to encrypt |
| `-o, --output` | Output `.crypto` file (default: `name.crypto`) |
| `-p, --password` | Encryption password (omit for interactive prompt) |
| `--hint` | Optional password hint stored in the file |

**Examples:**
```bash
python src/cli.py encrypt document.pdf -p s3cret
python src/cli.py encrypt document.pdf --hint "ma date de naissance"
python src/cli.py encrypt myfolder/ -o backup.crypto -p mypass
```

---

### `decrypt` — Decrypt a `.crypto` file

```bash
python src/cli.py decrypt <path> [-o <output>] [-p <password>]
```

| Argument | Description |
|----------|-------------|
| `path` | `.crypto` file to decrypt |
| `-o, --output` | Output path (default: original filename) |
| `-p, --password` | Decryption password (omit for interactive prompt) |

**Examples:**
```bash
python src/cli.py decrypt document.pdf.crypto -p s3cret
python src/cli.py decrypt document.pdf.crypto -o restored.pdf
python src/cli.py decrypt backup.crypto -p mypass
```

---

### `inspect` — Show metadata of a `.crypto` file

```bash
python src/cli.py inspect <file>
```

| Argument | Description |
|----------|-------------|
| `file` | `.crypto` file to inspect |

**Example:**
```bash
python src/cli.py inspect secret.crypto
```

---

### `help` — Show usage information

```bash
python src/cli.py help
python src/cli.py -h
python src/cli.py --help
```

---

## Environment Variable

Instead of passing `-p` on the command line (visible in process list), set:

```bash
export ENCRYPTO_PASSWORD="yourpassword"
python src/cli.py encrypt document.pdf
```

---

## GUI Mode

The desktop graphical interface is launched with:

```bash
python app.py          # pywebview GUI (Windows/Linux)
python src/main.py     # Kivy GUI (alternative)
```

---

## AppImage (Linux Standalone)

After building (see `README.md`), the AppImage is a single executable that bundles Python, all dependencies, and WebKitGTK. Run it like any Linux binary:

```bash
# Launch the GUI
./ENCRYPTO-x86_64.AppImage

# Pass the AppImage path to the CLI tools (extract first for CLI use)
./ENCRYPTO-x86_64.AppImage --appimage-extract
cd squashfs-root
python3 src/cli.py encrypt document.pdf -p mypassword
```

The AppImage includes everything — no Python, no pip, no GTK needed on the host machine. The only requirement is a Linux kernel with FUSE support (or `--appimage-extract` if FUSE is unavailable).
