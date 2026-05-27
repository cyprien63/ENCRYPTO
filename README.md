# ENCRYPTO — Secure File Encryption

Encrypt files and folders with AES-256-GCM + PBKDF2 key derivation + zlib compression.

- **Desktop GUI** (pywebview) — `python app.py`
- **Kivy GUI** (alternative) — `python src/main.py`
- **CLI** — `python src/cli.py encrypt/decrypt/inspect`

---

## Quick Start

```bash
pip install -r requirements.txt
python app.py                   # GUI
python src/cli.py encrypt doc.pdf -p mypassword   # CLI
```

---

## Build AppImage (Linux, standalone)

Build a fully self-contained AppImage bundling Python, all deps, and WebKitGTK:

### From Windows (recommended)

Run `compil.bat` → option 2 (Linux). Tries WSL first, falls back to Docker.

### From Linux (Docker)

```bash
docker run --rm -v "$PWD:/app" -w /app ubuntu:22.04 bash build/build_linux_docker.sh
```

Output: `version compiler/linux/ENCRYPTO-x86_64.AppImage`

### From Linux (native, requires host WebKitGTK)

```bash
bash build/build_linux.sh
```

---

## Build Windows .exe

```bash
compil.bat → option 1 (Windows)
```

Uses PyInstaller. Output: `version compiler/windows/ENCRYPTO/`

---

## CLI Usage

```
python src/cli.py encrypt <path> [-o <output>] [-p <password>] [--hint <hint>]
python src/cli.py decrypt <path> [-o <output>] [-p <password>]
python src/cli.py inspect <file>
```

See `docs/commands.md` for full documentation.

---

## File Format Specification (`.crypto`)

This document describes the ENCRYPTO binary format so you can build compatible implementations in any language (Java, Kotlin, Swift, C, JavaScript, etc.).

---

## Binary Structure

A `.crypto` file is a binary stream with the following layout:

### Header (fixed)

| Offset | Size | Field | Description |
|--------|------|-------|-------------|
| 0 | 8 | **Magic** | ASCII `ENCRYPTO` (`0x45 0x4E 0x43 0x52 0x59 0x50 0x54 0x4F`) |
| 8 | 1 | **Version** | `0x02` — format version (currently 2, was 1 in legacy) |
| 9 | 1 | **IsFolder** | `0x01` if the original input was a folder, `0x00` if a single file |
| 10 | 16 | **Salt** | PBKDF2 salt (random, 16 bytes) |
| 26 | 12 | **Nonce** | AES-GCM nonce (random, 12 bytes) |

### Metadata

| Offset (after nonce) | Size | Field | Description |
|---|---|---|---|
| 0 | 2 | **NameLength** | Big-endian `uint16` — byte length of original file/folder name |
| 2 | `NameLength` | **Name** | Original file/folder name encoded in UTF-8 |
| after name | 2 | **HintLength** | Big-endian `uint16` — byte length of password hint |
| after hint | `HintLength` | **Hint** | Password hint encoded in UTF-8 (may be empty, length 0) |

### Payload

| Offset (after hint) | Size | Field | Description |
|---|---|---|---|
| 0 | rest of file | **CipherText** | AES-GCM encrypted + authenticated data (see below) |

---

## Encryption Process

```
Input: plaintext bytes (file content or ZIP archive of folder)
         │
         ▼
   1. zlib compress (level 9)
         │
         ▼
   2. AES-256-GCM encrypt
      ─ Key: PBKDF2 derived
      ─ Nonce: 12 random bytes
      ─ Auth tag: appended by GCM (16 bytes)
         │
         ▼
   Output: encrypted payload written to ciphertext field
```

### Key Derivation (PBKDF2)

| Parameter | Value |
|-----------|-------|
| Algorithm | **PBKDF2-HMAC-SHA256** |
| Iterations | **100 000** |
| Salt | **16 random bytes** (unique per file, stored in header) |
| Key length | **32 bytes** (256 bits) |
| Encoding | Password is UTF-8 encoded before derivation |

### Encryption (AES-256-GCM)

| Parameter | Value |
|-----------|-------|
| Cipher | **AES-256 in GCM mode** |
| Key | **32 bytes** (derived from PBKDF2) |
| Nonce / IV | **12 random bytes** (unique per file, stored in header) |
| Associated Data | **None** (AAD length = 0) |
| Authentication tag | **16 bytes** (standard GCM tag, appended to ciphertext by the algorithm) |

### Compression

| Parameter | Value |
|-----------|-------|
| Algorithm | **zlib** (deflate) |
| Level | **9** (maximum compression) |
| Wrapper | Raw zlib stream (RFC 1950) |

> **Note for implementers:** The compression is inside the encryption — you must **compress first, then encrypt**. When decrypting, you must **decrypt first, then decompress**.

### Folder Handling

When the input is a **folder**:
1. The folder is first **ZIP-compressed** (standard ZIP format, DEFLATE method)
2. The ZIP bytes become the "plaintext" for the encryption process
3. On decryption, if `IsFolder = 1`, the recovered plaintext is a ZIP archive that must be extracted

---

## Decryption Process

```
Input: .crypto file
         │
         ▼
   1. Parse header (Magic → Version → IsFolder → Salt → Nonce → Name → Hint)
         │
         ▼
   2. Read ciphertext from remaining bytes
         │
         ▼
   3. Derive key with PBKDF2-HMAC-SHA256 (password + salt, 100k iterations)
         │
         ▼
   4. AES-256-GCM decrypt (key + nonce + ciphertext)
       ─ If authentication fails → wrong password / corrupted file
         │
         ▼
   5. zlib decompress the decrypted bytes
         │
         ▼
   Output: original plaintext (raw file bytes or ZIP of a folder)
```

---

## Implementation Guide (Cross-Platform)

### Python (reference)

```python
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
import zlib, struct

MAGIC = b'ENCRYPTO'
VERSION = 2
ITERATIONS = 100000

# Encrypt
def encrypt(plaintext, password):
    salt = os.urandom(16)
    nonce = os.urandom(12)
    kdf = PBKDF2HMAC(hashes.SHA256(), 32, salt, ITERATIONS)
    key = kdf.derive(password.encode())
    compressed = zlib.compress(plaintext, 9)
    ciphertext = AESGCM(key).encrypt(nonce, compressed, None)
    header = MAGIC + bytes([VERSION, is_folder]) + salt + nonce + ...
    return header + ciphertext

# Decrypt
def decrypt(ciphertext, password, salt, nonce):
    kdf = PBKDF2HMAC(hashes.SHA256(), 32, salt, ITERATIONS)
    key = kdf.derive(password.encode())
    plaintext = AESGCM(key).decrypt(nonce, ciphertext, None)
    return zlib.decompress(plaintext)
```

### Java / Android

```java
import javax.crypto.Cipher;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import javax.crypto.SecretKeyFactory;
import javax.crypto.spec.PBEKeySpec;
import java.util.zip.*;

// Read header, extract salt(16), nonce(12), ciphertext(rest)
byte[] magic = new byte[8]; // must be "ENCRYPTO"
int version = stream.read();      // 2
int isFolder = stream.read();     // 0 or 1
byte[] salt = stream.readNBytes(16);
byte[] nonce = stream.readNBytes(12);
int nameLen = (stream.read() << 8) | stream.read();
String name = new String(stream.readNBytes(nameLen), "UTF-8");
int hintLen = (stream.read() << 8) | stream.read();
String hint = new String(stream.readNBytes(hintLen), "UTF-8");
byte[] ciphertext = stream.readAllBytes();

// Key derivation
PBEKeySpec spec = new PBEKeySpec(password.toCharArray(), salt, 100000, 256);
SecretKeyFactory factory = SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256");
byte[] key = factory.generateSecret(spec).getEncoded();

// AES-GCM decrypt
Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
cipher.init(Cipher.DECRYPT_MODE,
    new SecretKeySpec(key, "AES"),
    new GCMParameterSpec(128, nonce));
byte[] decrypted = cipher.doFinal(ciphertext);

// zlib decompress
Inflater inflater = new Inflater();
inflater.setInput(decrypted);
byte[] plaintext = new byte[decrypted.length * 2]; // allocate properly
int len = inflater.inflate(plaintext);
// If isFolder == 1, handle as ZIP
```

### Swift (iOS / macOS)

```swift
import CryptoKit
import Compression

// Read header as above ...
let salt: Data       // 16 bytes
let nonce: Data      // 12 bytes
let ciphertext: Data // remaining

// Key derivation
let passwordData = password.data(using: .utf8)!
let symmetricKey = try! PKCS5.PBKDF2(
    password: passwordData,
    salt: salt,
    iterations: 100_000,
    keyLength: 32,
    prf: .sha256
).calculate()

// AES-GCM decrypt
let sealedBox = try! AES.GCM.SealedBox(
    nonce: AES.GCM.Nonce(data: nonce),
    ciphertext: ciphertext.dropLast(16),
    tag: ciphertext.suffix(16))
let decrypted = try! AES.GCM.open(sealedBox, using: symmetricKey)

// zlib decompress
let plaintext = (decrypted as NSData).decompressed(using: .zlib)
```

### JavaScript (Node.js / Web)

```javascript
const crypto = require('crypto');
const zlib = require('zlib');

// Key derivation
const key = crypto.pbkdf2Sync(password, salt, 100000, 32, 'sha256');

// AES-GCM decrypt
const decipher = crypto.createDecipheriv('aes-256-gcm', key, nonce);
decipher.setAuthTag(ciphertext.slice(-16));
const decrypted = Buffer.concat([
    decipher.update(ciphertext.slice(0, -16)),
    decipher.final()
]);

// zlib decompress
const plaintext = zlib.inflateSync(decrypted);
```

### Kotlin Multiplatform (KMP)

```kotlin
// Use platform-specific crypto libraries via expect/actual
// JVM: javax.crypto (same as Java)
// iOS: CryptoKit via cinterop
// JS: Web Crypto API
```

---

## Security Notes

- Each encryption generates a **fresh random salt and nonce** — even identical inputs produce different ciphertexts.
- AES-GCM provides **authenticated encryption** — any tampering is detected on decryption.
- PBKDF2 with 100 000 iterations slows down brute-force attacks.
- zlib compression before encryption reduces output size and removes patterns.

## Constants Summary

| Symbol | Value | Notes |
|--------|-------|-------|
| Magic | `ENCRYPTO` | 8 bytes, ASCII |
| Version | `2` | 1 byte, version 1 had no compression |
| Iterations | `100 000` | PBKDF2 iteration count |
| Key size | `32` bytes (256-bit) | AES-256 |
| Salt size | `16` bytes | PBKDF2 salt |
| Nonce size | `12` bytes | AES-GCM IV |
| GCM tag | `16` bytes | Appended by GCM mode |
| Compression | zlib level 9 | Raw deflate |
| Number encoding | Big-endian | All multi-byte integers |

## Version Mobile

Une version mobile de ENCRYPTO est en cours de développement mais **n'est pas sur GitHub** (problèmes de dépendances et de build).

Si vous voulez la voir, n'hésitez pas à me le dire sur mon serveur Discord :
[https://discord.gg/r3wrxZNddW](https://discord.gg/r3wrxZNddW)

---

## Version History

| Version | Changes |
|---------|---------|
| 1 (legacy) | No compression. Decrypted bytes are raw plaintext. |
| 2 (current) | zlib compression at level 9 before encryption. Decrypt → decompress. |
