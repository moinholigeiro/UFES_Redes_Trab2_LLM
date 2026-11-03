#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 || $# -gt 3 ]]; then
  echo "uso: $0 <node-id> <dns-ou-ip-do-certificado> [SANs-adicionais-separados-por-virgula]" >&2
  exit 2
fi

node_id="$1"
primary_san="$2"
extra_sans="${3:-}"
cert_days="${CERT_DAYS:-825}"
if [[ ! "$node_id" =~ ^[A-Za-z0-9_-]{1,64}$ ]]; then
  echo "node-id inválido" >&2
  exit 2
fi
if [[ ! "$primary_san" =~ ^[A-Za-z0-9._:-]+$ || "$primary_san" == *..* ]]; then
  echo "DNS/IP inválido" >&2
  exit 2
fi
if [[ -n "$extra_sans" && ! "$extra_sans" =~ ^(DNS:[A-Za-z0-9._-]+|IP:[0-9A-Fa-f:.]+)(,(DNS:[A-Za-z0-9._-]+|IP:[0-9A-Fa-f:.]+))*$ ]]; then
  echo "SAN adicional inválido (use DNS:nome ou IP:endereço)" >&2
  exit 2
fi
if [[ ! "$cert_days" =~ ^[0-9]+$ ]] || (( cert_days < 1 || cert_days > 825 )); then
  echo "CERT_DAYS deve ser inteiro entre 1 e 825" >&2
  exit 2
fi

out_dir="${NODE_SECRETS_DIR:-secrets}"
mkdir -p "$out_dir"
umask 077
lock_dir="$out_dir/.${node_id}.provision.lock"
if ! mkdir "$lock_dir" 2>/dev/null; then
  echo "provisionamento já está em andamento ou lock existe: $lock_dir" >&2
  exit 2
fi
trap 'rmdir "$lock_dir" 2>/dev/null || true' EXIT
key="$out_dir/$node_id.key"
cert="$out_dir/$node_id.crt"
if [[ -e "$key" || -e "$cert" ]]; then
  echo "certificado/chave já existem; nada foi sobrescrito: $out_dir/$node_id" >&2
  exit 2
fi

if [[ "$primary_san" =~ ^[0-9a-fA-F:.]+$ ]]; then
  san="IP:$primary_san"
else
  san="DNS:$primary_san"
fi
if [[ -n "$extra_sans" ]]; then san="$san,$extra_sans"; fi
tmp_dir="$(mktemp -d "$out_dir/.${node_id}.XXXXXX")"
trap 'rm -f "$tmp_dir/$node_id.key" "$tmp_dir/$node_id.crt"; rmdir "$tmp_dir" 2>/dev/null || true; rmdir "$lock_dir" 2>/dev/null || true' EXIT
openssl req -x509 -newkey rsa:3072 -sha256 -nodes -days "$cert_days" \
  -keyout "$tmp_dir/$node_id.key" -out "$tmp_dir/$node_id.crt" \
  -subj "/CN=$primary_san" \
  -addext "basicConstraints=critical,CA:FALSE" \
  -addext "keyUsage=critical,digitalSignature,keyEncipherment" \
  -addext "extendedKeyUsage=serverAuth" \
  -addext "subjectAltName=$san"
chmod 600 "$tmp_dir/$node_id.key"
chmod 644 "$tmp_dir/$node_id.crt"
mv "$tmp_dir/$node_id.key" "$key"
mv "$tmp_dir/$node_id.crt" "$cert"
echo "Certificado self-signed criado em $cert (SAN: $san). Copie somente o .crt para o trust bundle do Backend; mantenha a chave neste host."
