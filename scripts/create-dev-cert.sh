#!/usr/bin/env sh
set -eu

cert_dir="${1:-certs}"
cert_file="$cert_dir/cert.pem"
key_file="$cert_dir/key.pem"
tmp_config="$(mktemp)"

cleanup() {
  rm -f "$tmp_config"
}

trap cleanup EXIT

mkdir -p "$cert_dir"

cat > "$tmp_config" <<'EOF'
[req]
default_bits = 2048
prompt = no
default_md = sha256
distinguished_name = dn
x509_extensions = req_ext

[dn]
C = FI
ST = Uusimaa
L = Helsinki
O = Valinta-Apuri Dev
OU = Local Development
CN = localhost

[req_ext]
subjectAltName = @alt_names
basicConstraints = critical,CA:FALSE
keyUsage = critical,digitalSignature,keyEncipherment
extendedKeyUsage = serverAuth

[alt_names]
DNS.1 = localhost
DNS.2 = host.docker.internal
IP.1 = 127.0.0.1
IP.2 = 0.0.0.0
EOF

openssl req -x509 -nodes -newkey rsa:2048 \
  -keyout "$key_file" \
  -out "$cert_file" \
  -days 7 \
  -config "$tmp_config"

chmod 600 "$key_file"
echo "Created $cert_file and $key_file"