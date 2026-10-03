"""生成仅供本机演练的七天自签证书；需要独立工具依赖 cryptography。

不属于后端运行依赖，不会修改系统信任库。输出目录应位于仓库外。
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import ipaddress
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    root = args.out_dir.resolve()
    repository = Path(__file__).resolve().parent.parent
    if root == repository or repository in root.parents:
        parser.error("certificate output must be outside the repository")
    root.mkdir(parents=True, exist_ok=True)
    certificate = root / "localhost.pem"
    private_key = root / "localhost.key"
    if certificate.exists() or private_key.exists():
        parser.error("refusing to overwrite an existing certificate or key")
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.now(timezone.utc)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name).issuer_name(name).public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=7))
        .add_extension(x509.SubjectAlternativeName([
            x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
        ]), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    # 独占创建；密钥不回显，Windows 权限由所在目录管理。
    with private_key.open("xb") as target:
        target.write(key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ))
    with certificate.open("xb") as target:
        target.write(cert.public_bytes(serialization.Encoding.PEM))
    print(f"Created local certificate and key in {root}; SAN=localhost,127.0.0.1; valid=7 days")


if __name__ == "__main__":
    main()
