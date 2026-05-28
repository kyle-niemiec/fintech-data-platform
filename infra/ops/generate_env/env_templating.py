#!/usr/bin/env python3

import re
from pathlib import Path

from generator import (
	deterministic_value,
	fernet_key_deterministic,
	fernet_key_random,
	random_value,
)


class EnvTemplateRenderer:
	"""
	Render environment files from a template using deterministic or random replacement rules.
	"""

	DETERMINISTIC_SEED = "meridian-ci-seed-v1"


	def __init__(
		self,
		template_path: Path,
		output_path: Path,
		mode: str,
		ui_origin: str,
		ui_api_url: str,
		release_tag: str,
		app_env: str,
		launcher_api_url: str,
		kes_api_key: str,
		kes_identity: str,
	) -> None:
		self.template_path = template_path
		self.output_path = output_path
		self.mode = mode
		self.ui_origin = ui_origin
		self.ui_api_url = ui_api_url
		self.release_tag = release_tag
		self.app_env = app_env
		self.launcher_api_url = launcher_api_url
		self.kes_api_key = kes_api_key
		self.kes_identity = kes_identity


	def _template_find_replace(self, template: str, key: str, value: str) -> str:
		"""
		Find a key in a template `.env` and replace its value.
		"""
		pattern = re.compile(rf"(?m)^{re.escape(key)}=.*$")
		replacement = f"{key}={value}"

		if pattern.search(template):
			return pattern.sub(replacement, template, count=1)

		return f"{template.rstrip()}\n{replacement}\n"


	def _template_find_remove(self, template: str, key: str) -> str:
		"""
		Find a key in a template `.env` and remove the line if it exists.
		"""
		return re.sub(rf"(?m)^{re.escape(key)}=.*\n?", "", template)


	def _template_replace_prefixed_values(self, template: str) -> str:
		"""
		Find all keys in the template `.env` that have values starting with `replace_with_`
		and replace their values based on the specified mode (random or deterministic).
		"""
		pattern = re.compile(r"(?m)^(?P<key>[A-Za-z_][A-Za-z0-9_]*)=(?P<value>replace_with_[^\n\r]*)$")

		def _replacement(match: re.Match[str]) -> str:
			key = match.group("key")

			if self.mode == "random":
				return f"{key}={random_value(key)}"

			return f"{key}={deterministic_value(self.DETERMINISTIC_SEED, key)}"

		return pattern.sub(_replacement, template)


	def render(self) -> int:
		"""
		Read in a template `.env` file, replace values according to the specified
		mode and arguments, and write the result to the output `.env` path.
		"""
		template = self.template_path.read_text(encoding="utf-8")

		# Set MinIO related keys
		template = self._template_find_replace(template, "MINIO_KMS_KES_API_KEY", self.kes_api_key)
		template = self._template_find_replace(template, "MINIO_KMS_KES_IDENTITY", self.kes_identity)

		# Set Airflow Fernet key based on mode
		if self.mode == "random":
			template = self._template_find_replace(template, "AIRFLOW_FERNET_KEY", fernet_key_random())
		else:
			template = self._template_find_replace(
				template,
				"AIRFLOW_FERNET_KEY",
				fernet_key_deterministic(self.DETERMINISTIC_SEED, "AIRFLOW_FERNET_KEY"),
			)

		# Set UI and release tag keys if provided, otherwise remove them from the template.
		if self.ui_origin:
			template = self._template_find_replace(template, "UI_ORIGIN", self.ui_origin)

		if self.ui_api_url:
			template = self._template_find_replace(template, "UI_API_URL", self.ui_api_url)

		if self.release_tag:
			template = self._template_find_replace(template, "VITE_RELEASE_TAG", self.release_tag)

		if self.app_env:
			template = self._template_find_replace(template, "VITE_APP_ENV", self.app_env)

		if self.launcher_api_url:
			template = self._template_find_replace(template, "VITE_LAUNCHER_API_URL", self.launcher_api_url)

		# Replace any keys with values starting with `replace_with_` according to the mode.
		template = self._template_replace_prefixed_values(template)

		# Write the rendered template to the output path and return success.
		self.output_path.parent.mkdir(parents=True, exist_ok=True)
		self.output_path.write_text(template.rstrip() + "\n", encoding="utf-8")
		return 0
