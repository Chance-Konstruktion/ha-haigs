#!/bin/sh
# Echte Gitea- und Forgejo-Instanzen fuer den Job tests-forgen.
#
# Beide laufen OHNE TLS auf eigenen Ports -- genau der Fall aus
# GitHub #1 (Forgejo im LAN, http://forgejo.lan:3030). Codeberg ist
# ein Forgejo und damit mit abgedeckt. Die Binaries sind auf Version
# und SHA256 festgenagelt; Gitea und Forgejo verweigern root, darum
# laufen sie als Benutzer "forge".
#
# Die Ports sucht das Skript frei: Runner koennen sich das Netz teilen,
# ein fester Port 3000 war im ersten Lauf schon belegt. Die gewaehlten
# Adressen landen in .forgen-env (HAIGS_FORGEN) fuer Saat und Tests.
set -eu

GITEA_VERSION=28.1.0
GITEA_SHA256=ea93cfa4a300564ac457d3903469fea49ec5a4da37d0cebaa435f8e329ea64d0
FORGEJO_VERSION=16.0.5
FORGEJO_SHA256=2c548bf1bfa09a441a3a674b1dd4959d77576816ad50534c23496908a3ea5a19

ABLAGE="${CI_PROJECT_DIR:-$PWD}/.forgen-cache"
mkdir -p "$ABLAGE"
id forge >/dev/null 2>&1 || useradd -m forge

holen() { # name url sha
  ziel="$ABLAGE/$1"
  if ! echo "$3  $ziel" | sha256sum -c --status 2>/dev/null; then
    curl -fsSL -o "$ziel" "$2"
    echo "$3  $ziel" | sha256sum -c
  fi
  install -m 0755 "$ziel" "/usr/local/bin/$1"
}

starten() { # name port
  name=$1; port=$2; wurzel=/srv/$name
  mkdir -p "$wurzel/custom/conf"
  cat > "$wurzel/custom/conf/app.ini" <<INI
APP_NAME = $name
RUN_USER = forge
WORK_PATH = $wurzel
[database]
DB_TYPE = sqlite3
PATH = $wurzel/data/db.sqlite
[server]
HTTP_ADDR = 127.0.0.1
HTTP_PORT = $port
DOMAIN = 127.0.0.1
ROOT_URL = http://127.0.0.1:$port/
OFFLINE_MODE = true
DISABLE_SSH = true
[security]
INSTALL_LOCK = true
[service]
DISABLE_REGISTRATION = true
[repository]
ROOT = $wurzel/repos
[migrations]
ALLOW_LOCALNETWORKS = true
[log]
LEVEL = Warn
INI
  chown -R forge "$wurzel"
  konf="--config $wurzel/custom/conf/app.ini"
  su forge -s /bin/sh -c "cd $wurzel && $name migrate $konf >/dev/null"
  su forge -s /bin/sh -c "cd $wurzel && $name admin user create $konf --username haigs --password haigs-ci-geheim --email haigs@example.invalid --admin --must-change-password=false >/dev/null"
  su forge -s /bin/sh -c "cd $wurzel && nohup $name web $konf > $wurzel/web.log 2>&1 &"
  for _ in $(seq 1 60); do
    curl -fs "http://127.0.0.1:$port/api/v1/version" >/dev/null && return 0
    sleep 1
  done
  echo "FEHLER: $name antwortet nicht auf Port $port"; cat "$wurzel/web.log"; exit 1
}

freier_port() {
  python3 -c 'import socket; s = socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1])'
}

holen gitea "https://dl.gitea.com/gitea/$GITEA_VERSION/gitea-$GITEA_VERSION-linux-amd64" "$GITEA_SHA256"
holen forgejo "https://codeberg.org/forgejo/forgejo/releases/download/v$FORGEJO_VERSION/forgejo-$FORGEJO_VERSION-linux-amd64" "$FORGEJO_SHA256"
GITEA_PORT=$(freier_port)
starten gitea "$GITEA_PORT"
FORGEJO_PORT=$(freier_port)
starten forgejo "$FORGEJO_PORT"
echo "HAIGS_FORGEN=gitea=http://127.0.0.1:$GITEA_PORT,forgejo=http://127.0.0.1:$FORGEJO_PORT" > .forgen-env
cat .forgen-env
