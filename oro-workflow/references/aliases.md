# Oro CLI Aliases

Always prefer the alias over typing the underlying command.

## Console

| Alias | Command | Purpose |
|-------|---------|---------|
| `c` | `time php /oroapp/bin/console` | Base console command |
| `consume` | `c oro:message-queue:consume` | Run MQ consumer |

## Assets & Frontend

| Alias | Command | Purpose |
|-------|---------|---------|
| `cab` | `c oro:assets:build` | Build frontend assets |
| `cai` | `c assets:install --symlink` | Install assets with symlinks |
| `caw` | `/usr/local/bin/oro/npm run watch` | Watch JS/SCSS changes (live rebuild) |

**Usage:** For JS/SCSS rebuild use `cab` (oro:assets:build). For installing assets use
`cai` (assets:install --symlink). For JS/SCSS debugging use `caw` (npm watch). To fully
rebuild JS after module changes, `c oro:assets:install --symlink` (not just
`oro:assets:build`).

## Cache

| Alias | Command | Purpose |
|-------|---------|---------|
| `cc` | `c cache:clear` | Clear Symfony cache |
| `cw` | `c cache:warmup` | Warmup cache |
| `ccw` | `cstop && cw && cstart` | Stop services, warmup, restart |
| `ccc` | `cstop && cw && cc && cstart` | Stop, warmup, clear, restart |

See `cache-invalidation.md` for when to use each — prefer surgical folder deletion
over full clears.

## Services (Supervisor)

| Alias | Command | Purpose |
|-------|---------|---------|
| `sc` | `sudo supervisorctl` | Supervisorctl base |
| `rs` | `sc restart` | Restart a service |
| `cstart` | `sc start fpm nginx` | Start FPM + Nginx |
| `cstop` | `xdis && sc stop fpm mc: ws nginx && rm -rf cache dirs` | Stop all, disable xdebug, clear cache |
| `oro-start` | `sudo supervisord -c /etc/supervisor/supervisord.conf` | Start supervisord |
| `oro-stop` | `sudo pkill supervisord` | Stop supervisord |

## Migrations & Translations

| Alias | Command | Purpose |
|-------|---------|---------|
| `cup` | `cstop && c oro:migration:load --force && c oro:migration:data:load && ccw && cstart` | Full migration load + restart |
| `ctran` | `c oro:translation:load && c oro:translation:rebuild-cache && c oro:translation:dump` | Reload translations |

Editing a translation YAML does nothing without `ctran` — translations are loaded
into DB + cache, not read from disk at runtime.

## Debugging

| Alias | Command | Purpose |
|-------|---------|---------|
| `xen` | Enable xdebug + restart FPM | Turn on Xdebug |
| `xdis` | Disable xdebug + restart FPM | Turn off Xdebug |
| `ben` | Enable Blackfire extension | Turn on Blackfire profiler |
| `bdis` | Disable Blackfire extension | Turn off Blackfire profiler |

## Environment

| Alias | Command | Purpose |
|-------|---------|---------|
| `oro-init-config` | Set application_url, url, secure_url to project URL | Init Oro config URLs |
| `d` | `in_oro docker --log-level ERROR compose --env-file .env-app.local` | Docker compose wrapper |

## Git commit path

For git commits that run Node-based hooks, the PATH must include `/usr/local/bin/oro`
so the hook sees the correct Node.js version.
