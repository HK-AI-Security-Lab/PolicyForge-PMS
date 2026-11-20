"""Set the demo Nacos password and random API secrets; retain an existing .env."""

import base64
import os
import secrets
from pathlib import Path


def main(path: Path | None = None):
    path = path or Path(__file__).resolve().parents[1] / ".env"
    values = {
        "NACOS_PASSWORD": "nacos",
        "NACOS_AUTH_TOKEN": base64.b64encode(secrets.token_bytes(48)).decode(),
        "NACOS_AUTH_IDENTITY_VALUE": secrets.token_hex(24),
        "POLICYFORGE_API_KEY": secrets.token_hex(32),
        "POLICYFORGE_READ_KEY": secrets.token_hex(32),
        "NACOS_CONSOLE_PORT": "8080",
        "POLICYFORGE_PORT": "8000",
        "POLICYFORGE_SEED_EXAMPLES": "true",
    }
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        print("Existing .env retained.")
        return
    with os.fdopen(fd, "w") as handle:
        handle.write("# Local secrets. Do not commit this file.\n")
        handle.writelines(f"{key}={value}\n" for key, value in values.items())
    print("Created .env: demo login nacos/nacos; API keys generated (permissions 0600).")


if __name__ == "__main__":
    main()
