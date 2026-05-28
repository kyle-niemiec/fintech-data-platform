#!/usr/bin/env python3

import sys
from pathlib import Path

from env_templating import EnvTemplateRenderer


def main() -> int:
	"""
	Main entry point for the environment file generation script. Expects command
	line arguments for template path, output path, mode, UI origin, UI API URL,
	release tag, KES API key, and KES identity.
	"""
	if len(sys.argv) != 11:
		raise SystemExit("expected args: template output mode ui_origin ui_api_url release_tag app_env launcher_api_url kes_api_key kes_identity")

	# Parse command line arguments.
	template_path = Path(sys.argv[1])
	output_path = Path(sys.argv[2])
	mode = sys.argv[3]
	ui_origin = sys.argv[4]
	ui_api_url = sys.argv[5]
	release_tag = sys.argv[6]
	app_env = sys.argv[7]
	launcher_api_url = sys.argv[8]
	kes_api_key = sys.argv[9]
	kes_identity = sys.argv[10]

	renderer = EnvTemplateRenderer(
		template_path=template_path,
		output_path=output_path,
		mode=mode,
		ui_origin=ui_origin,
		ui_api_url=ui_api_url,
		release_tag=release_tag,
		app_env=app_env,
		launcher_api_url=launcher_api_url,
		kes_api_key=kes_api_key,
		kes_identity=kes_identity,
	)

	return renderer.render()


if __name__ == "__main__":
	raise SystemExit(main())
