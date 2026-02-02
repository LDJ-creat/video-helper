from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def _parse_csv(value: str | None) -> list[str]:
	if not value:
		return []
	parts = [p.strip() for p in value.split(",")]
	return [p for p in parts if p]


def wire_cors(app: FastAPI) -> None:
	"""Attach CORS middleware for browser-based local development.

	Env:
	- CORS_ALLOWED_ORIGINS: comma-separated origins (e.g. http://localhost:3000)
	- CORS_ALLOW_ORIGIN_REGEX: optional regex to allow multiple localhost ports

	Defaults to allowing localhost/127.0.0.1 on port 3000.
	Some environments (notably certain Chrome/Android setups) may send Origin
	without an explicit port (e.g. http://127.0.0.1).
	"""
	allowed_origins = (
		_parse_csv(os.environ.get("CORS_ALLOWED_ORIGINS"))
		or _parse_csv(os.environ.get("CORS_ALLOW_ORIGINS"))
		or [
			"http://localhost:3000",
			"http://127.0.0.1:3000",
			"http://localhost",
			"http://127.0.0.1",
		]
	)

	allow_origin_regex = os.environ.get("CORS_ALLOW_ORIGIN_REGEX")

	app.add_middleware(
		CORSMiddleware,
		allow_origins=allowed_origins,
		allow_origin_regex=allow_origin_regex,
		allow_credentials=False,
		allow_methods=["*"],
		allow_headers=["*"],
	)
