from __future__ import annotations

import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from core.db.session import get_data_dir


def _key_path(*, data_dir: Path | None = None) -> Path:
	return (data_dir or get_data_dir()) / "secret.key"


def load_or_create_master_key(*, data_dir: Path | None = None) -> bytes:
	"""Load or create the settings encryption master key.

MVP scheme (A2): on first use, generate a Fernet key and store it at
`DATA_DIR/secret.key`.
"""

	path = _key_path(data_dir=data_dir)
	path.parent.mkdir(parents=True, exist_ok=True)

	if path.exists():
		raw = path.read_text(encoding="utf-8").strip()
		try:
			key = raw.encode("ascii")
			# Validate key shape
			_ = Fernet(key)
			return key
		except Exception as e:
			raise RuntimeError("Invalid settings encryption key") from e

	key = Fernet.generate_key()
	path.write_text(key.decode("ascii"), encoding="utf-8")
	try:
		os.chmod(path, 0o600)
	except Exception:
		# Best-effort on Windows and other platforms.
		pass
	return key


def encrypt_api_key(api_key: str, *, data_dir: Path | None = None) -> str:
	api_key = (api_key or "").strip()
	if not api_key:
		raise ValueError("apiKey must be non-empty")

	f = Fernet(load_or_create_master_key(data_dir=data_dir))
	token = f.encrypt(api_key.encode("utf-8"))
	return token.decode("ascii")


def decrypt_api_key(ciphertext: str, *, data_dir: Path | None = None) -> str:
	ciphertext = (ciphertext or "").strip()
	if not ciphertext:
		raise ValueError("ciphertext must be non-empty")

	f = Fernet(load_or_create_master_key(data_dir=data_dir))
	try:
		plain = f.decrypt(ciphertext.encode("ascii"))
	except InvalidToken as e:
		raise ValueError("Invalid ciphertext") from e
	return plain.decode("utf-8")
