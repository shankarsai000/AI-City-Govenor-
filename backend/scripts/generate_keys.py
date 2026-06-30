"""
RSA key pair generation script.

Run once before first startup:
  python scripts/generate_keys.py

Generates:
  backend/keys/private.pem  — kept on server, never exposed
  backend/keys/public.pem   — can be distributed to verifiers

Design: 4096-bit RSA for maximum security. Production deployments should
store private.pem in a secrets manager (AWS Secrets Manager, Vault) and
inject at runtime — never commit keys to git.
"""
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

KEYS_DIR = Path(__file__).parent.parent / "keys"


def generate_rsa_keypair(key_size: int = 4096) -> None:
    KEYS_DIR.mkdir(parents=True, exist_ok=True)

    private_key_path = KEYS_DIR / "private.pem"
    public_key_path = KEYS_DIR / "public.pem"

    if private_key_path.exists() or public_key_path.exists():
        print("[!] Keys already exist. Delete them manually to regenerate.")
        print(f"   {private_key_path}")
        print(f"   {public_key_path}")
        sys.exit(1)

    print(f"Generating {key_size}-bit RSA key pair...")

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size,
    )

    # Serialize private key (PEM, no passphrase — use secrets manager in prod)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )

    # Serialize public key
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    private_key_path.write_bytes(private_pem)
    public_key_path.write_bytes(public_pem)

    # Restrict private key permissions (owner read-only)
    private_key_path.chmod(0o600)

    print(f"[OK] Private key: {private_key_path}")
    print(f"[OK] Public key:  {public_key_path}")
    print("\n[WARN] NEVER commit private.pem to git. It is in .gitignore.")


if __name__ == "__main__":
    generate_rsa_keypair()
