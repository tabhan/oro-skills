# OroCommerce Cron Jobs — Complete Developer Reference

> Source: https://doc.oroinc.com/master/backend/cron/

## AGENT QUERY HINTS

Use this file when asked about:
- "How do I create a cron job in Oro?"
- "How do I schedule a Symfony command to run periodically?"
- "What is CronCommandScheduleDefinitionInterface?"
- "How does oro:cron work?"
- "How do I make a command run conditionally?"
- "How do I register a cron schedule?"
- "What is the difference between CronCommandActivationInterface and CronCommandScheduleDefinitionInterface?"
- "How do I run a cron command synchronously?"

---

## 1. How Oro Cron Works

Oro cron is built on top of the **OroCronBundle**. It does NOT rely on multiple system cron entries for each task. Instead:

1. The system cron calls `oro:cron` **once every minute**.
2. `oro:cron` queries the database for all scheduled commands that are due to run at the current time.
3. Due commands are dispatched — either via the **message queue** (default) or as **synchronous background processes**.

This means all schedule management happens inside Oro, not in your OS crontab.

### System-Level Cron Entry (set once per server)

**Linux / UNIX:**
```cron
*/1 * * * * /usr/bin/php /path/to/project/bin/console oro:cron --env=prod > /dev/null
```

Some distributions require specifying the user:
```cron
*/1 * * * * www-data /usr/bin/php /path/to/project/bin/console oro:cron --env=prod > /dev/null
```

**Windows:** Use Task Scheduler (Control Panel) to execute the same command every minute.

---

## 2. Key Interfaces

| Interface | Purpose |
|---|---|
| `CronCommandScheduleDefinitionInterface` | Declares the crontab schedule string for a command |
| `CronCommandActivationInterface` | Adds conditional activation logic — command only runs if `isActive()` returns `true` |
| `SynchronousCommandInterface` | Marks a command to run as an immediate background process instead of through the MQ |

All are in the `Oro\Bundle\CronBundle\Command` namespace.

---

## 3. Creating a Cron Command

### Step 1 — Implement the Command with CronCommandScheduleDefinitionInterface

```php
<?php
// src/Bridge/Bundle/BridgeIntegrationBundle/Command/SyncVm2CatalogCommand.php

namespace Bridge\Bundle\BridgeIntegrationBundle\Command;

use Oro\Bundle\CronBundle\Command\CronCommandScheduleDefinitionInterface;
use Symfony\Component\Console\Command\Command;
use Symfony\Component\Console\Input\InputInterface;
use Symfony\Component\Console\Output\OutputInterface;

/**
 * Scheduled command to synchronize the VM2 product catalog.
 * Runs daily at 01:00 (1 AM server time).
 */
class SyncVm2CatalogCommand extends Command implements CronCommandScheduleDefinitionInterface
{
    /**
     * Command name MUST start with "oro:cron:" to be treated as a cron command
     * by the scheduling system.
     */
    protected static $defaultName = 'oro:cron:bridge-vm2';

    public function __construct(
        private readonly \Bridge\Bundle\BridgeIntegrationBundle\Service\VM2\VM2ApiService $vm2Service,
    ) {
        parent::__construct();
    }

    /**
     * Returns the crontab schedule expression.
     * This value is stored in the database by oro:cron:definitions:load.
     *
     * Common patterns:
     *   '* * * * *'     — every minute
     *   '*/5 * * * *'   — every 5 minutes
     *   '0 * * * *'     — every hour at :00
     *   '0 1 * * *'     — daily at 01:00
     *   '5 0 * * *'     — daily at 00:05
     *   '0 2 * * 0'     — weekly on Sunday at 02:00
     *   '0 0 1 * *'     — first day of every month at midnight
     */
    public function getDefaultDefinition(): string
    {
        return '0 1 * * *'; // Daily at 01:00
    }

    protected function configure(): void
    {
        $this->setDescription('Synchronize VM2 product catalog');
    }

    protected function execute(InputInterface $input, OutputInterface $output): int
    {
        $output->writeln('Starting VM2 catalog sync...');

        try {
            $count = $this->vm2Service->syncCatalog();
            $output->writeln(sprintf('Synced %d products.', $count));
            return Command::SUCCESS;
        } catch (\Exception $e) {
            $output->writeln('<error>Sync failed: ' . $e->getMessage() . '</error>');
            return Command::FAILURE;
        }
    }
}
```

### Step 2 — Register as a Service

```yaml
# src/Bridge/Bundle/BridgeIntegrationBundle/Resources/config/services.yml
services:
    Bridge\Bundle\BridgeIntegrationBundle\Command\SyncVm2CatalogCommand:
        arguments:
            - '@Bridge\Bundle\BridgeIntegrationBundle\Service\VM2\VM2ApiService'
        tags:
            - { name: console.command }
```

**WHY the `console.command` tag:** Symfony uses this tag to auto-discover commands. OroCronBundle's schedule loader also scans tagged commands for `CronCommandScheduleDefinitionInterface`.

### Step 3 — Load Schedule into the Database

```bash
php bin/console oro:cron:definitions:load
```

This command:
- Scans all tagged console commands.
- Finds those implementing `CronCommandScheduleDefinitionInterface`.
- Creates or updates `Schedule` records in the database.
- Runs automatically during `oro:platform:update` and `oro:install`.

**Important:** This command **removes previously loaded cron schedules** before reloading. If you have related commands that must reload together (e.g., `oro:workflow:definition:load`), run them in the same sequence.

```bash
# Safe reload sequence
php bin/console oro:cron:definitions:load
php bin/console oro:workflow:definition:load
```

---

## 4. Conditional Execution

Implement `CronCommandActivationInterface` when the command should only run under certain conditions.

```php
<?php
namespace Bridge\Bundle\BridgeIntegrationBundle\Command;

use Oro\Bundle\CronBundle\Command\CronCommandActivationInterface;
use Oro\Bundle\CronBundle\Command\CronCommandScheduleDefinitionInterface;
use Symfony\Component\Console\Command\Command;

/**
 * Syncs customer data from VM2 API only when the integration is enabled.
 */
class SyncVm2CustomersCommand extends Command implements
    CronCommandScheduleDefinitionInterface,
    CronCommandActivationInterface
{
    protected static $defaultName = 'oro:cron:bridge-customer';

    public function __construct(
        private readonly \Bridge\Bundle\BridgeIntegrationBundle\Repository\IntegrationRepository $integrationRepo,
    ) {
        parent::__construct();
    }

    public function getDefaultDefinition(): string
    {
        return '*/30 * * * *'; // Every 30 minutes
    }

    /**
     * Return false to skip this command even if its scheduled time has arrived.
     * Evaluated by oro:cron before dispatching the command.
     */
    public function isActive(): bool
    {
        return $this->integrationRepo->isVm2IntegrationEnabled();
    }

    protected function execute(InputInterface $input, OutputInterface $output): int
    {
        // ... implementation
        return Command::SUCCESS;
    }
}
```

**WHY `isActive()`:** Use this to avoid unnecessary job queue entries when an integration or feature is disabled. It keeps System > Jobs clean and prevents wasted consumer cycles.

---

## 5. Synchronous Execution

By default, `oro:cron` sends scheduled commands to the **message queue** for deferred execution. To run a command immediately as a background OS process instead, implement `SynchronousCommandInterface`:

```php
<?php
namespace Bridge\Bundle\BridgeIntegrationBundle\Command;

use Oro\Bundle\CronBundle\Command\CronCommandScheduleDefinitionInterface;
use Oro\Bundle\CronBundle\Command\SynchronousCommandInterface;
use Symfony\Component\Console\Command\Command;

/**
 * Materialized view refresh — must run synchronously because it cannot be
 * safely deferred via the message queue.
 */
class RefreshMaterializedViewsCommand extends Command implements
    CronCommandScheduleDefinitionInterface,
    SynchronousCommandInterface
{
    protected static $defaultName = 'oro:cron:bridge-mviews';

    public function getDefaultDefinition(): string
    {
        return '0 */4 * * *'; // Every 4 hours
    }

    protected function execute(InputInterface $input, OutputInterface $output): int
    {
        // Directly executed — no MQ involvement
        return Command::SUCCESS;
    }
}
```

**Caution:** Synchronous commands block the `oro:cron` scheduler loop for their duration. Keep them fast, or they may delay other scheduled commands that minute.

---

## 6. Crontab Syntax Quick Reference

```
# ┌───── minute (0–59)
# │ ┌─── hour (0–23)
# │ │ ┌─ day of month (1–31)
# │ │ │ ┌ month (1–12)
# │ │ │ │ ┌ day of week (0–7, 0 and 7 = Sunday)
# │ │ │ │ │
# * * * * *

'0 5 * * *'       # Daily at 05:00
'*/15 * * * *'    # Every 15 minutes
'0 */6 * * *'     # Every 6 hours at :00
'0 9 * * 1-5'     # Weekdays at 09:00 (Monday–Friday)
'0 0 1,15 * *'    # 1st and 15th of each month at midnight
'30 23 * * 0'     # Every Sunday at 23:30
```

---

## 7. Attaching Cron Commands to Feature Toggles

If a cron command should only exist when a feature is enabled, declare it in `features.yml`:

```yaml
# Resources/config/oro/features.yml
features:
    bridge_vm2_integration:
        label: bridge.feature.vm2_integration
        toggle: bridge_integration.vm2_enabled
        cron_jobs:
            - oro:cron:bridge-customer
            - oro:cron:bridge-vm2
```

When the feature is disabled, Oro will **skip** these cron commands even if their schedule is due. See `setup/feature-toggle.md` for the full feature toggle system.

---

## 8. Monitoring and UI

- View all scheduled tasks: **System > Scheduled Tasks** in the back-office.
- The schedule definition, last run time, and next scheduled time are shown per command.
- Cron job execution failures are visible in **System > Jobs** (for MQ-dispatched jobs).

---

## 9. Common Cron Commands in the Braskem Project

| Console Command | Schedule | Purpose |
|---|---|---|
| `oro:cron:bridge-customer` | `*/30 * * * *` | VM2 customer sync |
| `oro:cron:bridge-product` | `0 2 * * *` | SAP product import |
| `oro:cron:bridge-vm2` | `0 1 * * *` | VM2 catalog sync |
| `oro:cron:bridge-division` | `0 3 * * *` | Division sync |
| `oro:cron:bridge-mviews` | `0 */4 * * *` | Materialized view refresh |
| `oro:cron:edge-dump` | `0 4 * * *` | Edge entity import |
| `oro:cron:edge-customer` | `0 5 * * *` | Edge customer user sync |
| `oro:cron:edge-product` | `0 6 * * *` | Edge product ship modes |

---

## 10. Full Example with Feature Toggle and Conditional Activation

```php
<?php
namespace Bridge\Bundle\BridgeIntegrationBundle\Command;

use Oro\Bundle\CronBundle\Command\CronCommandActivationInterface;
use Oro\Bundle\CronBundle\Command\CronCommandScheduleDefinitionInterface;
use Symfony\Component\Console\Command\Command;
use Symfony\Component\Console\Input\InputInterface;
use Symfony\Component\Console\Output\OutputInterface;

/**
 * Imports product data from SAP via SFTP.
 * Only active when the SAP integration is enabled.
 * Schedule: daily at 02:00.
 */
class BridgeProductCommand extends Command implements
    CronCommandScheduleDefinitionInterface,
    CronCommandActivationInterface
{
    protected static $defaultName = 'oro:cron:bridge-product';

    public function __construct(
        private readonly \Oro\Component\MessageQueue\Client\MessageProducerInterface $producer,
        private readonly \Doctrine\Persistence\ManagerRegistry $doctrine,
    ) {
        parent::__construct();
    }

    public function getDefaultDefinition(): string
    {
        return '0 2 * * *';
    }

    public function isActive(): bool
    {
        // Check a config value or integration status
        $config = $this->doctrine->getRepository(
            \Oro\Bundle\ConfigBundle\Entity\ConfigValue::class
        );
        // ... check bridge_integration.sap_enabled
        return true;
    }

    protected function configure(): void
    {
        $this->setDescription('Import SAP products (scheduled, sends to MQ)');
    }

    protected function execute(InputInterface $input, OutputInterface $output): int
    {
        // Dispatch to MQ rather than doing the work inline.
        // This keeps the cron command fast and lets consumers handle retries.
        $this->producer->send(
            \Bridge\Bundle\BridgeIntegrationBundle\Async\Topic\ImportSapProductsTopic::getName(),
            ['batchSize' => 500, 'forceUpdate' => false]
        );

        $output->writeln('SAP product import message queued.');
        return Command::SUCCESS;
    }
}
```

**WHY dispatch to MQ from a cron command:** The cron command itself runs briefly (just enqueues the message), while the actual heavy work runs asynchronously. This keeps `oro:cron` responsive, enables retry logic through the MQ, and shows progress in **System > Jobs**.
