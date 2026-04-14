# OroCommerce Environment Setup — Complete Developer Reference

> Source: https://doc.oroinc.com/master/backend/setup/dev-environment/

## AGENT QUERY HINTS

Use this file when asked about:
- "What environment variables does Oro use?"
- "How do I configure the database connection?"
- "How do I set up RabbitMQ / Redis / Elasticsearch?"
- "What is ORO_DB_DSN / ORO_MQ_DSN / ORO_REDIS_DSN?"
- "Where do I configure the app URL?"
- "What is app.yml vs config.yml?"
- "How do I configure Oro for production vs development?"
- "What Docker services does Oro need?"
- "How do I install Oro from scratch?"
- "What does reinstall.sh do?"

---

## 1. Infrastructure Overview

OroCommerce requires the following external services:

| Service | Purpose | Default Port |
|---|---|---|
| **PostgreSQL 17** | Primary relational database | 5432 |
| **RabbitMQ 3.13** | Message queue broker (Enterprise) | 5672 / 15672 (UI) |
| **Elasticsearch 8** | Full-text search engine | 9200 / 9300 |
| **Redis 7** | Cache and session storage | 6379 |
| **MongoDB 8** | Document storage (optional features) | 27017 |
| **Mailcatcher** | Email capture during development | 1025 (SMTP) / 1080 (UI) |

Start all services locally with Docker Compose:

```bash
docker compose up -d
```

---

## 2. Environment Variable Reference

Oro uses a layered environment variable approach. Variables are defined in `.env-app` and overridden by `.env-app.local` (gitignored).

### Database

| Variable | Description | Example |
|---|---|---|
| `ORO_DB_DSN` | Full Doctrine DBAL DSN | `pgsql://user:pass@localhost:5432/oro_db` |
| `DATABASE_URL` | Alternative Symfony DSN (maps to same connection) | `postgresql://user:pass@localhost:5432/db_name` |

DSN format for PostgreSQL:
```
pgsql://<user>:<password>@<host>:<port>/<database>?serverVersion=17&charset=utf8
```

### Message Queue

| Variable | Description | Example |
|---|---|---|
| `ORO_MQ_DSN` | Message queue broker DSN | `dbal:` or `amqp://guest:guest@localhost:5672` |

DBAL (default — uses the database):
```
ORO_MQ_DSN=dbal:
```

RabbitMQ (Enterprise / production):
```
ORO_MQ_DSN=amqp://guest:guest@rabbitmq:5672/%2f
```

### Search (Elasticsearch)

| Variable | Description | Example |
|---|---|---|
| `ORO_SEARCH_ENGINE_DSN` | Elasticsearch DSN | `elastic://localhost:9200/?prefix=oro_` |
| `ORO_WEBSITE_SEARCH_ENGINE_DSN` | Website search Elasticsearch DSN | `elastic://localhost:9200/?prefix=oro_website_` |

### Cache and Sessions (Redis)

| Variable | Description | Example |
|---|---|---|
| `ORO_CACHE_DSN` | Doctrine/Symfony cache DSN | `redis://localhost:6379` |
| `ORO_SESSION_DSN` | PHP session storage DSN | `redis://localhost:6379` |
| `ORO_LAYOUT_CACHE_DSN` | Layout cache DSN | `redis://localhost:6379` |
| `ORO_MAINTENANCE_LOCK_DSN` | Maintenance lock storage | `redis://localhost:6379` |

### Application

| Variable | Description | Example |
|---|---|---|
| `ORO_APP_DOMAIN` | Primary application domain | `braskem.local` |
| `ORO_APP_PROTOCOL` | HTTP or HTTPS | `http` |
| `ORO_SECRET` | Symfony application secret (random string) | `s3cr3t_k3y_here` |
| `ORO_APP_URL` | Full application URL (used for email links, etc.) | `https://braskem.local` |

### MongoDB (if used)

| Variable | Description | Example |
|---|---|---|
| `ORO_MONGODB_DSN` | MongoDB connection DSN | `mongodb://localhost:27017/oro` |

### Email

| Variable | Description | Example |
|---|---|---|
| `MAILER_DSN` | Symfony Mailer DSN | `smtp://localhost:1025` (Mailcatcher) |

---

## 3. Environment Files

Oro uses a cascading configuration file strategy:

| File | Purpose | Committed? |
|---|---|---|
| `.env-app` | Base environment configuration — defaults and non-secret values | Yes |
| `.env-app.test` | Test environment overrides | Yes |
| `.env-build` | Build-time configuration (asset compilation) | Yes |
| `.env-app.local` | Local developer overrides — secrets, local DB credentials | No (gitignored) |
| `.env-app.local.dist` | Template for creating `.env-app.local` | Yes |

### Creating your local override file

```bash
cp .env-app.local.dist .env-app.local
# Then edit .env-app.local with your local credentials
```

### Example `.env-app.local` contents

```dotenv
# Local database
ORO_DB_DSN=pgsql://oro_user:secret@localhost:5432/braskem_oro

# Local Redis
ORO_CACHE_DSN=redis://localhost:6379
ORO_SESSION_DSN=redis://localhost:6379

# Local Elasticsearch
ORO_SEARCH_ENGINE_DSN=elastic://localhost:9200/?prefix=braskem_
ORO_WEBSITE_SEARCH_ENGINE_DSN=elastic://localhost:9200/?prefix=braskem_website_

# Message queue (use DBAL locally, RabbitMQ in production)
ORO_MQ_DSN=dbal:

# Application URL
ORO_APP_URL=http://localhost
ORO_APP_DOMAIN=localhost

# Local mail
MAILER_DSN=smtp://localhost:1025
```

---

## 4. Configuration Files

### `config/config.yml` (Symfony application config)

Standard Symfony configuration file. Use this for framework settings, security, and third-party bundle configuration.

```yaml
# config/config.yml (structure overview)
framework:
    secret: '%env(ORO_SECRET)%'
    session:
        handler_id: '%env(ORO_SESSION_DSN)%'

doctrine:
    dbal:
        url: '%env(ORO_DB_DSN)%'
    orm:
        auto_mapping: true

oro_message_queue:
    transport:
        default: '%env(ORO_MQ_DSN)%'
    client: ~
```

### `Resources/config/oro/app.yml` (per-bundle Oro configuration)

Each bundle can provide an `app.yml` under `Resources/config/oro/`. These files are merged by Oro at compile time into the global configuration tree. Use this for bundle-specific Oro settings.

```yaml
# src/Bridge/Bundle/BridgeIntegrationBundle/Resources/config/oro/app.yml

oro_message_queue:
  time_before_stale:
    jobs:
      'bridge.integration.import_sap_products': 7200

# System configuration defaults for this bundle
bridge_integration:
  sap_sftp_host: '%env(BRIDGE_SAP_SFTP_HOST)%'
  sap_sftp_user: '%env(BRIDGE_SAP_SFTP_USER)%'
```

**WHY `app.yml` instead of `config.yml`:** Bundle `app.yml` keeps bundle-specific configuration self-contained and distributable. It is the idiomatic Oro way to ship default config with a bundle.

---

## 5. Installation — Fresh Environment

### Full Reinstall Script (Braskem Project)

```bash
# Destroys everything and rebuilds from scratch
./cicd/reinstall.sh [password] [application-url]

# Examples:
./cicd/reinstall.sh                                    # admin/admin, http://localhost
./cicd/reinstall.sh mypassword                         # custom admin password
./cicd/reinstall.sh mypassword https://braskem.local   # custom password and URL
```

### What `reinstall.sh` does (in order):

1. Drops and recreates the database.
2. Clears all caches.
3. Runs `oro:install` (creates schema, loads fixtures, creates admin user).
4. Builds assets (`oro:assets:build`, `assets:install`).
5. Builds the React dashboard.

### Manual Platform Update (after entity/migration changes)

```bash
php bin/console oro:platform:update --force
```

This runs:
- Doctrine schema updates
- Oro data migrations
- Cache warming

### Key Post-Install Steps

After running `reinstall.sh` or `oro:install`:

1. **Start the message queue consumer** (required for admin login to work):
   ```bash
   php bin/console oro:message-queue:consume --env=prod
   ```

2. **Build frontend assets** (after JS/CSS changes):
   ```bash
   php bin/console oro:assets:build
   php bin/console assets:install --symlink
   ```

3. **Build the React dashboard:**
   ```bash
   php bin/console aaxis:dashboard:build
   # OR directly:
   cd src/Aaxis/Bundle/AaxisIntegrationBundle/Resources/public/js/app/dashboard
   npm run build
   ```

4. **Load initial data:**
   ```bash
   php bin/console oro:cron:bridge-customer   # VM2 customers
   php bin/console oro:cron:bridge-product    # SAP products
   php bin/console oro:cron:bridge-division   # Divisions
   ```

---

## 6. Docker Compose Services (Braskem / Standard Oro)

```yaml
# docker-compose.yml (structure overview)
services:
  pgsql:
    image: postgres:17
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: oro_db
      POSTGRES_USER: oro_user
      POSTGRES_PASSWORD: secret

  rabbitmq:
    image: rabbitmq:3.13-management
    ports:
      - "5672:5672"
      - "15672:15672"    # Management UI

  elasticsearch:
    image: elasticsearch:8.x
    ports:
      - "9200:9200"
      - "9300:9300"

  redis:
    image: redis:7
    ports:
      - "6379:6379"

  mongodb:
    image: mongo:8
    ports:
      - "27017:27017"

  mailcatcher:
    image: schickling/mailcatcher
    ports:
      - "1025:1025"   # SMTP
      - "1080:1080"   # Web UI
```

Start all:
```bash
docker compose up -d
```

---

## 7. Development vs Production Considerations

| Concern | Development | Production |
|---|---|---|
| **MQ Transport** | `ORO_MQ_DSN=dbal:` (no extra infra) | `ORO_MQ_DSN=amqp://...` (RabbitMQ) |
| **Cache** | File system or Redis | Redis (mandatory) |
| **Symfony env** | `APP_ENV=dev` | `APP_ENV=prod` |
| **Debug** | `APP_DEBUG=1` | `APP_DEBUG=0` |
| **Consumer** | Manual: `php bin/console oro:message-queue:consume` | Supervised process (systemd/Supervisor) |
| **Consumer limits** | None (easier debugging) | `--memory-limit=512 --time-limit=600` |
| **Assets** | `npm run watch` | `npm run build` (minified) |
| **Email** | Mailcatcher (catch-all, no delivery) | Real SMTP or SES |

### Switching to Production Mode

```bash
# Set in .env-app or server environment
APP_ENV=prod
APP_DEBUG=0

# Clear and warm cache
php bin/console cache:clear --env=prod
php bin/console cache:warmup --env=prod
```

---

## 8. Environment Validation

Verify all system requirements are met:

```bash
php bin/console oro:check-requirements
php bin/console oro:check-requirements -v   # Verbose output
php bin/console oro:check-requirements -vv  # Very verbose
```

---

## 9. Multi-Website Configuration

The Braskem application supports 4 localized websites (BR, MX, US, EU). After installation, each must be configured with a unique URL:

- Navigate to `/admin/config/website/{1,2,3,4}` in the admin panel.
- Set a distinct URL per website (e.g., `https://br.braskem.com`, `https://mx.braskem.com`).
- Set Brazil as the default website; remove or reassign the "Default" website.

---

## 10. Common Configuration Values via Console

Update system configuration without using the UI:

```bash
php bin/console oro:config:update oro_ui.application_url 'https://braskem.local'
php bin/console oro:config:update oro_website.url 'https://braskem.local'
```

---

## 11. Integration System Configuration

External integration settings (SAP, VM2, Edge, Digibee, Zoho) are managed through:

- **Admin UI:** `/admin/config/system/platform/bridge_integration`
- **Environment variables** for credentials (never hardcode passwords)

Relevant env variables for integrations (example pattern):

```dotenv
BRIDGE_SAP_SFTP_HOST=sftp.example.com
BRIDGE_SAP_SFTP_USER=sap_user
BRIDGE_SAP_SFTP_PASSWORD=secret
BRIDGE_VM2_API_URL=https://api.vm2.example.com
BRIDGE_VM2_API_KEY=api_key_here
BRIDGE_EDGE_API_URL=https://edge.example.com
BRIDGE_DIGIBEE_WEBHOOK_URL=https://digibee.example.com/webhook
BRIDGE_ZOHO_CLIENT_ID=zoho_client
BRIDGE_ZOHO_CLIENT_SECRET=zoho_secret
```
