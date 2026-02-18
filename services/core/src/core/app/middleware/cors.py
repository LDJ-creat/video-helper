from __future__ import annotations

import os
import re

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
	explicit_allowed_origins = _parse_csv(os.environ.get("CORS_ALLOWED_ORIGINS")) or _parse_csv(
		os.environ.get("CORS_ALLOW_ORIGINS")
	)
	explicit_allow_origin_regex = os.environ.get("CORS_ALLOW_ORIGIN_REGEX")

	default_allowed_origins = [
		"http://localhost:3000",
		"http://127.0.0.1:3000",
		"http://localhost",
		"http://127.0.0.1",
	]

	# If the user explicitly configures CORS via env, respect it as-is.
	# Otherwise, default to a permissive localhost-only regex to support
	# direct browser-to-backend calls (e.g. streaming) without a proxy.
	if explicit_allowed_origins or explicit_allow_origin_regex:
		allowed_origins = explicit_allowed_origins or default_allowed_origins
		allow_origin_regex = explicit_allow_origin_regex
	else:
		allowed_origins = default_allowed_origins
		allow_origin_regex = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"

		# Extra safety: if we're in the default local-dev CORS mode, echo the exact
		# Origin back on responses for localhost/127 to avoid any header mismatch.
		# This helps when browsers are strict and some upstream layer mutates headers.
		_local_origin_re = re.compile(r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$")

		@app.middleware("http")
		async def _echo_local_origin(request, call_next):  # type: ignore
			response = await call_next(request)
			origin = request.headers.get("origin")
			if origin and _local_origin_re.match(origin):
				response.headers["Access-Control-Allow-Origin"] = origin
				# Ensure caches/proxies don't reuse a response across origins
				vary = response.headers.get("Vary")
				if not vary:
					response.headers["Vary"] = "Origin"
				elif "origin" not in vary.lower():
					response.headers["Vary"] = f"{vary}, Origin"
			return response

	app.add_middleware(
		CORSMiddleware,
		allow_origins=allowed_origins,
		allow_origin_regex=allow_origin_regex,
		allow_credentials=False,
		allow_methods=["*"],
		allow_headers=["*"],
	)
