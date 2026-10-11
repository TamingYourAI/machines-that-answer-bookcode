"""Settings from the environment. Every one is optional; see .env.example."""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Settings:
    public_url: str = "http://localhost:8080"
    data_dir: Path = Path("data")
    secret: str = ""
    admin_token: str = ""                 # empty: the console is open (local use only)
    demo_signin: bool = True              # the web app can sign in as a demo policyholder
    twilio_sid: str = ""
    twilio_token: str = ""
    twilio_from: str = ""
    phone_mode: str = "relay"             # relay | media
    default_pack: str = "river"           # the Knowledge Line opens on River Plumbing
    phone_pack: str = "river"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    max_photo_bytes: int = 10 * 1024 * 1024
    max_photos: int = 12
    transfer_numbers: dict = field(default_factory=dict)

    @classmethod
    def from_env(cls, env: dict | None = None) -> "Settings":
        e = dict(os.environ if env is None else env)
        data_dir = Path(e.get("OVA_DATA_DIR", "data"))
        secret = e.get("OVA_SECRET", "")
        if not secret:
            p = data_dir / "secret"
            if p.exists():
                secret = p.read_text().strip()
            else:
                data_dir.mkdir(parents=True, exist_ok=True)
                secret = secrets.token_hex(32)
                p.write_text(secret)
        return cls(
            public_url=e.get("OVA_PUBLIC_URL", "http://localhost:8080").rstrip("/"),
            data_dir=data_dir, secret=secret, admin_token=e.get("OVA_ADMIN_TOKEN", ""),
            demo_signin=e.get("OVA_DEMO_SIGNIN", "on") != "off",
            twilio_sid=e.get("TWILIO_ACCOUNT_SID", ""),
            twilio_token=e.get("TWILIO_AUTH_TOKEN", ""),
            twilio_from=e.get("TWILIO_FROM_NUMBER", ""),
            phone_mode=e.get("OVA_PHONE_MODE", "relay"),
            default_pack=e.get("OVA_DEFAULT_PACK", "river"),
            phone_pack=e.get("OVA_PHONE_PACK", e.get("OVA_DEFAULT_PACK", "river")),
            smtp_host=e.get("SMTP_HOST", ""), smtp_port=int(e.get("SMTP_PORT", "587")),
            smtp_user=e.get("SMTP_USER", ""), smtp_password=e.get("SMTP_PASSWORD", ""),
            smtp_from=e.get("SMTP_FROM", ""),
            transfer_numbers={"claims": e.get("OVA_CLAIMS_TRANSFER_NUMBER", ""),
                              "river": e.get("OVA_RIVER_OWNER_NUMBER", "")},
        )
