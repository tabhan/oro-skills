# OroCommerce Notification Alerts

> Source: https://doc.oroinc.com/master/backend/integrations/notification-alerts/

## AGENT QUERY HINTS

Use this file when asked about:
- "How do I log integration errors in OroCommerce?"
- "What is NotificationAlert?"
- "How do I create notification alerts for sync failures?"
- "How do I show alerts to admins in the back-office?"
- "What is NotificationAlertManager?"
- "How do I clean up old notification alerts?"
- "Where do I view integration alerts in the UI?"
- "How do I notify admins about authentication failures?"
- "What CLI commands manage notification alerts?"
- "How do I implement NotificationAlertInterface?"

---

## Overview

The **Notification Alerts** system allows developers to log errors detected during data synchronization, integration jobs, or CLI commands, and notify users or administrators about issues that require resolution.

All alerts are:
- Stored persistently in the database
- Accessible via the back-office UI: **System > Alerts**
- Queryable and manageable via CLI commands
- Auto-cleaned on a weekly schedule (older than 30 days)

**WHY**: Instead of relying on log files that admins rarely check, notification alerts surface errors directly in the UI where the responsible admin or user will see them. This creates a structured, queryable record of all integration issues.

---

## NotificationAlert Entity Fields

The following fields are available on the `NotificationAlert` entity (visible in the System > Alerts datagrid):

| Field | Type | Description |
|---|---|---|
| `id` | GUID | Unique alert identifier; appears in logs for investigation |
| `createdAt` | DateTime | When the alert was logged |
| `updatedAt` | DateTime | When the alert was last updated |
| `user` | Relation | The user who performed the operation triggering the alert |
| `message` | Text | The error or exception message describing the cause |
| `source` | String | Source of the alert — usually a bundle name, integration name, CLI command, or MQ job |
| `resource` | String | The resource involved — usually an entity name or FQCN |
| `alertType` | String | Type category: `auth`, `sync`, `export`, `import`, or custom |
| `operation` | String | Operation that caused the alert: `import`, `export`, `sync`, etc. |
| `step` | String | Logical step where the error was detected: `get_list`, `map`, `save`, etc. |
| `itemId` | Integer | ID of the specific entity/resource item involved |
| `externalId` | String | ID of the resource item in the external application |
| `resolved` | Boolean | Whether the alert has been marked as resolved |

---

## Creating Notification Alerts

### Step 1: Implement `NotificationAlertInterface`

Your alert class must implement `Oro\Bundle\NotificationBundle\NotificationAlert\NotificationAlertInterface`.

For simple use cases, the standard `NotificationAlert` entity (from `OroNotificationBundle`) can be created directly via the manager without needing a custom class.

### Step 2: Register a `NotificationAlertManager` Service

The `NotificationAlertManager` is the entry point for creating, resolving, and deleting alerts. Register one per integration source:

```yaml
# Resources/config/services.yml
services:
    acme_demo.notification_alert_manager:
        class: Oro\Bundle\NotificationBundle\NotificationAlert\NotificationAlertManager
        arguments:
            # First argument: source type — use the bundle or integration name
            # Naming convention: use PascalCase bundle name or integration name
            # e.g., 'AcmeCrmIntegration', 'MicrosoftSync', 'GoogleIntegration'
            - 'AcmeCrmIntegration'
            # Second argument: resource type — entity name or FQCN
            # e.g., 'Contact', 'Order', 'Acme\Bundle\DemoBundle\Entity\Contact'
            - 'Contact'
            - '@doctrine'
            - '@oro_security.token_accessor'
```

**WHY separate managers per source**: One source can handle multiple resources, but keeping managers scoped to a specific source makes it easy to filter and clean alerts by integration name.

### Step 3: Create Alerts in Your Sync Code

```php
namespace Acme\Bundle\DemoBundle\Integration;

use Oro\Bundle\NotificationBundle\NotificationAlert\NotificationAlertManager;

class AcmeContactSyncService
{
    private NotificationAlertManager $alertManager;

    public function __construct(NotificationAlertManager $alertManager)
    {
        $this->alertManager = $alertManager;
    }

    public function syncContacts(): void
    {
        try {
            $contacts = $this->fetchContactsFromApi();
            $this->processContacts($contacts);
        } catch (\Throwable $e) {
            // Log detailed context on server side
            // Never silently swallow errors
            $this->createSyncAlert($e);
            throw $e;
        }
    }

    private function fetchContactsFromApi(): array
    {
        try {
            return $this->transport->getContacts();
        } catch (\Exception $e) {
            // Authentication failure — use 'auth' alert type
            $this->alertManager->addAlert(
                $this->alertManager->createNotificationAlertBuilder()
                    ->setType('auth')
                    ->setOperation('sync')
                    ->setStep('get_list')
                    ->setMessage(sprintf('Authentication failed: %s', $e->getMessage()))
                    ->buildNotificationAlert()
            );
            throw $e;
        }
    }

    private function createSyncAlert(\Throwable $e): void
    {
        // Sync failure — use 'sync' alert type
        $this->alertManager->addAlert(
            $this->alertManager->createNotificationAlertBuilder()
                ->setType('sync')
                ->setOperation('import')
                ->setStep('save')
                ->setMessage($e->getMessage())
                // Optionally set the specific item that failed
                // ->setItemId($contact->getId())
                // ->setExternalId($externalContactId)
                ->buildNotificationAlert()
        );
    }

    public function resolveAllAlerts(): void
    {
        // Mark all alerts for this source/resource as resolved
        // Called after a successful sync to clear previous failures
        $this->alertManager->resolveAll();
    }
}
```

### Step 4: Wire the Alert Manager into Your Service

```yaml
    acme_demo.integration.contact_sync:
        class: Acme\Bundle\DemoBundle\Integration\AcmeContactSyncService
        arguments:
            - '@acme_demo.notification_alert_manager'
```

---

## Alert Types Reference

| Alert Type | When to Use |
|---|---|
| `auth` | Authentication/authorization failure (invalid API key, expired token, permission denied) |
| `sync` | General synchronization failure (data mapping error, API error, save failure) |
| `import` | Import-specific failure |
| `export` | Export-specific failure |
| custom | Any domain-specific alert type your integration needs |

---

## Operation and Step Reference

**Operations** (what the integration was doing when the error occurred):

| Operation | Description |
|---|---|
| `import` | Importing data from external system |
| `export` | Exporting data to external system |
| `sync` | General bidirectional synchronization |
| `get_list` | Fetching a list of records |

**Steps** (logical stage within the operation):

| Step | Description |
|---|---|
| `get_list` | Fetching/listing records from external API |
| `map` | Transforming/mapping data between formats |
| `save` | Persisting data to the database |
| `validate` | Validating data before processing |

---

## Resolving Alerts

Alerts can be resolved in three ways:

### 1. Programmatically (in code)

```php
// Resolve all alerts for this manager's source + resource
$this->alertManager->resolveAll();

// Resolve a specific alert by ID
$this->alertManager->resolve($alertId);
```

### 2. Via the Admin UI

- Navigate to **System > Alerts**
- Select one or more alerts
- Use the **Delete** or **Mass Delete** action
- Or use the **Mark as Resolved** action (if available)

### 3. Via CLI Command

```bash
# Delete a specific alert by ID
php bin/console oro:notification:alerts:cleanup --id=<alert-uuid>

# Delete all resolved alerts (does not delete active alerts)
php bin/console oro:notification:alerts:cleanup
```

---

## CLI Commands Reference

### List Alerts

```bash
# List all alerts
php bin/console --env=prod oro:notification:alerts:list

# Filter by resource type
php bin/console --env=prod oro:notification:alerts:list --resource-type=Contact

# Filter by source type
php bin/console --env=prod oro:notification:alerts:list --source-type=AcmeCrmIntegration

# Filter by alert type
php bin/console --env=prod oro:notification:alerts:list --alert-type=auth

# Paginate results
php bin/console --env=prod oro:notification:alerts:list --page=2 --per-page=50

# Show summary statistics (grouped)
php bin/console --env=prod oro:notification:alerts:list --summary

# Include resolved alerts
php bin/console --env=prod oro:notification:alerts:list --resolved

# Filter to current user's alerts
php bin/console --env=prod oro:notification:alerts:list --current-user

# Filter to current organization's alerts
php bin/console --env=prod oro:notification:alerts:list --current-organization
```

### Clean Up Alerts

```bash
# Remove a specific alert by UUID
php bin/console oro:notification:alerts:cleanup --id=<uuid>

# Remove all resolved and old (30+ day) alerts (same as the cron job)
php bin/console oro:notification:alerts:cleanup
```

### Scheduled Cleanup (Cron)

The system automatically runs cleanup weekly:

```bash
# Manual trigger of the cron-scheduled cleanup
php bin/console oro:cron:notification:alerts:cleanup
```

**Cleanup schedule**: Every Sunday at 00:00
**Cleanup criteria**: Removes alerts older than 30 days AND all resolved alerts

---

## Naming Conventions

Following these conventions makes alerts filterable and consistent across integrations:

| Field | Convention | Examples |
|---|---|---|
| `source` | PascalCase bundle or integration name | `AcmeCrmIntegration`, `MicrosoftSync`, `GoogleIntegration`, `SapSftp` |
| `resource` | Entity name or FQCN | `Contact`, `Order`, `CalendarEvent`, `Acme\Bundle\DemoBundle\Entity\Task` |

**One source, many resources**: A single integration source (e.g., `AcmeCrmIntegration`) can create alerts for multiple resource types (contacts, deals, companies). Register separate `NotificationAlertManager` services per resource type.

---

## Complete Integration Pattern: Sync Service with Alert Lifecycle

This pattern shows the recommended full lifecycle: create alert on failure, resolve on success.

```php
namespace Acme\Bundle\DemoBundle\Integration;

use Oro\Bundle\NotificationBundle\NotificationAlert\NotificationAlertManager;
use Psr\Log\LoggerInterface;

class AcmeContactSyncService
{
    public function __construct(
        private readonly AcmeTransport $transport,
        private readonly NotificationAlertManager $alertManager,
        private readonly LoggerInterface $logger,
    ) {}

    public function sync(): bool
    {
        $this->logger->info('Starting Acme CRM contact sync');

        try {
            // Step 1: Authenticate / fetch data
            $contacts = $this->transport->getContacts();
        } catch (\Exception $e) {
            // Log detailed context server-side
            $this->logger->error('Acme CRM auth failed', ['exception' => $e]);

            // Surface user-friendly alert in back-office
            $this->alertManager->addAlert(
                $this->alertManager->createNotificationAlertBuilder()
                    ->setType('auth')
                    ->setOperation('sync')
                    ->setStep('get_list')
                    ->setMessage('Could not connect to Acme CRM: ' . $e->getMessage())
                    ->buildNotificationAlert()
            );

            return false;
        }

        // Step 2: Process each contact
        $errors = [];
        foreach ($contacts as $contactData) {
            try {
                $this->processContact($contactData);
            } catch (\Exception $e) {
                $externalId = $contactData['id'] ?? 'unknown';
                $this->logger->error('Failed to sync contact', [
                    'external_id' => $externalId,
                    'exception' => $e,
                ]);

                $errors[] = $contactData;

                $this->alertManager->addAlert(
                    $this->alertManager->createNotificationAlertBuilder()
                        ->setType('sync')
                        ->setOperation('import')
                        ->setStep('save')
                        ->setExternalId((string) $externalId)
                        ->setMessage('Failed to save contact: ' . $e->getMessage())
                        ->buildNotificationAlert()
                );
            }
        }

        // Step 3: If fully successful, resolve previous alerts
        if (empty($errors)) {
            $this->alertManager->resolveAll();
            $this->logger->info('Acme CRM contact sync completed successfully');
            return true;
        }

        $this->logger->warning('Acme CRM contact sync completed with errors', [
            'error_count' => count($errors),
        ]);
        return false;
    }

    private function processContact(array $contactData): void
    {
        // Transform and persist contact — throws on failure
    }
}
```

---

## Quick-Reference Checklist

To implement notification alerts for an integration:

- [ ] Register a `NotificationAlertManager` service with source name and resource name
- [ ] Inject the manager into sync services
- [ ] Create `auth` type alerts for authentication/connection failures
- [ ] Create `sync` type alerts for data processing failures
- [ ] Set `operation` and `step` to help admins diagnose where the error occurred
- [ ] Set `externalId` or `itemId` when the error relates to a specific record
- [ ] Call `resolveAll()` on successful sync to clear previous failure alerts
- [ ] Use `oro:notification:alerts:list` CLI to verify alerts appear correctly
- [ ] Verify alerts appear in admin UI: System > Alerts
