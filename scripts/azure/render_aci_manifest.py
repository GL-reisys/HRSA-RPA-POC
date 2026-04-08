#!/usr/bin/env python3

import argparse
import os
import re
import sys
from pathlib import Path


PLACEHOLDER_PATTERN = re.compile(r"__[A-Z0-9_]+__")


def required_env(var_name: str) -> str:
    value = os.getenv(var_name)
    if value:
        return value

    print(f"Missing required environment variable: {var_name}", file=sys.stderr)
    sys.exit(1)


def build_context() -> dict[str, str]:
    dns_label = required_env("AZURE_DNS_LABEL")
    location = required_env("AZURE_LOCATION")

    return {
        "__AZURE_LOCATION__": location,
        "__AZURE_CONTAINER_GROUP_NAME__": required_env("AZURE_CONTAINER_GROUP_NAME"),
        "__AZURE_DNS_LABEL__": dns_label,
        "__AZURE_ACR_LOGIN_SERVER__": required_env("AZURE_ACR_LOGIN_SERVER"),
        "__AZURE_ACR_USERNAME__": required_env("AZURE_ACR_USERNAME"),
        "__AZURE_ACR_PASSWORD__": required_env("AZURE_ACR_PASSWORD"),
        "__FRONTEND_IMAGE__": required_env("FRONTEND_IMAGE"),
        "__BACKEND_IMAGE__": required_env("BACKEND_IMAGE"),
        "__FRONTEND_CPU__": os.getenv("FRONTEND_CPU", "0.5"),
        "__FRONTEND_MEMORY_GB__": os.getenv("FRONTEND_MEMORY_GB", "1.0"),
        "__BACKEND_CPU__": os.getenv("BACKEND_CPU", "0.5"),
        "__BACKEND_MEMORY_GB__": os.getenv("BACKEND_MEMORY_GB", "1.0"),
        "__API_INTERNAL_URL__": os.getenv("API_INTERNAL_URL", "http://127.0.0.1:5000"),
        "__CORS_ALLOWED_ORIGINS__": os.getenv(
            "CORS_ALLOWED_ORIGINS",
            f"http://localhost:3000,http://127.0.0.1:3000,http://{dns_label}.{location}.azurecontainer.io:3000",
        ),
        "__AZURE_OPENAI_ENDPOINT__": os.getenv("AZURE_OPENAI_ENDPOINT", ""),
        "__AZURE_OPENAI_API_KEY__": os.getenv("AZURE_OPENAI_API_KEY", ""),
        "__AZURE_OPENAI_DEPLOYMENT__": os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4"),
    }


def render_template(template_path: Path, output_path: Path) -> None:
    content = template_path.read_text(encoding="utf-8")
    for placeholder, value in build_context().items():
        content = content.replace(placeholder, value)

    unresolved = PLACEHOLDER_PATTERN.findall(content)
    if unresolved:
        unresolved_list = ", ".join(sorted(set(unresolved)))
        print(f"Unresolved placeholders in rendered manifest: {unresolved_list}", file=sys.stderr)
        sys.exit(1)

    output_path.write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Render an Azure Container Instance YAML manifest.")
    parser.add_argument("--template", required=True, help="Path to the YAML template.")
    parser.add_argument("--output", required=True, help="Path to the rendered YAML output.")
    args = parser.parse_args()

    template_path = Path(args.template)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    render_template(template_path, output_path)


if __name__ == "__main__":
    main()
