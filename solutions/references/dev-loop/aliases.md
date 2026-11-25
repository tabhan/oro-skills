# Oro CLI aliases

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

JS/SCSS rebuild: `cab`; JS/SCSS debugging: `caw`.

**`assets:install` vs `oro:assets:install`** are different. `cai` is Symfony's `assets:install --symlink`, which
only links bundle `Resources/public` into `public/`. After a **JS module change** run `c oro:assets:install --symlink`
(Oro's own command, which also regenerates the module map); use `cai` only for the plain link step.

## Cache

| Alias | Command | Purpose |
|-------|---------|---------|
| `cc` | `c cache:clear` | Clear Symfony cache |
| `cw` | `c cache:warmup` | Warmup cache |
| `ccw` | `cstop && cw && cstart` | Stop services, warmup, restart |
| `ccc` | `cstop && cw && cc && cstart` | Stop, warmup, clear, restart |

See `cache-invalidation.md` for when to use each (prefer surgical deletion over full clears).

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

Git commits that run Node-based hooks need `/usr/local/bin/oro` on `PATH` so the hook sees the right Node.js.
