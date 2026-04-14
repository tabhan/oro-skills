# Message Queue, Cron Jobs, and Feature Toggles

> Source: https://doc.oroinc.com/master/backend/mq/
> Real-world examples drawn from: `src/Bridge/Bundle/BridgeIntegrationBundle` and `src/Aaxis/Bundle/AaxisIntegrationBundle`

---

## AGENT QUERY HINTS

This file answers questions like:
- "How do I add a new message queue topic in OroCommerce?"
- "How do I create a cron job in OroCommerce?"
- "How do I send a message to the queue from a controller or service?"
- "How do I create a message processor?"
- "How do I toggle features on/off at runtime?"
- "How do I read a system configuration value in PHP?"
- "How do I make a configuration value differ per website?"
- "How does the async integration flow work end to end?"
- "Why use async instead of synchronous processing?"
- "How do I prevent a cron command from running twice simultaneously?"

---

## WHY ASYNC PROCESSING?

The message queue exists because some operations are too slow or risky to run inside an HTTP request:

| Synchronous (bad for HTTP) | Async via MQ (correct approach) |
|---------------------------|----------------------------------|
| SAP order ingest (100+ items) | Controller returns 200 immediately, MQ processes the items |
| External API calls (Digibee, Zoho) | HTTP timeout is irrelevant; MQ retries on failure |
| Database bulk-writes | Done in background, no user waiting |
| File import from SFTP | Cron triggers, MQ fans out per-file |

**The rule:** If the operation takes more than ~200ms or touches external systems, it should be async.

Without the MQ consumer running, messages silently accumulate in the database and are never processed. This is why admin login can break in some configurations — notifications and reindex jobs queue but never execute.

---

## CONCEPTS

### Topic

A topic is the named "channel" for a category of message. It defines what fields a message body must contain and what types those fields must be. Topics extend `AbstractTopic`.

### Processor

A processor is the class that receives messages for one or more topics and performs the actual work. It must return `ACK` (success), `REJECT` (permanent failure), or `REQUEUE` (temporary failure, retry).

### Queue Name

Processors can be routed to named queues (e.g., `integration`, `default`). Different consumers can be started per queue for throughput isolation.

### Consumer Daemon

The MQ consumer is a long-running process:
```bash
# Run the consumer (must be running for any async work to execute)
php bin/console oro:message-queue:consume --env=prod

# Run consumer limited to a specific queue only
php bin/console oro:message-queue:consume integration --env=prod
```

The consumer reads messages from the database (CE) or RabbitMQ (EE) and dispatches them to the matching processor.

---

## COMPLETE EXAMPLE: ADDING A NEW ASYNC INTEGRATION

This section shows the full pattern as used in `BridgeIntegrationBundle` for Digibee delivery sync.

### Step 1: Define the Topic

The topic declares the message contract — what fields are required and their types.

**File:** `src/Bridge/Bundle/BridgeIntegrationBundle/Async/Topic/DigibeeDeliverySyncTopic.php`

```php
<?php

namespace Bridge\Bundle\BridgeIntegrationBundle\Async\Topic;

use Oro\Component\MessageQueue\Topic\AbstractTopic;
use Symfony\Component\OptionsResolver\OptionsResolver;

class DigibeeDeliverySyncTopic extends AbstractTopic
{
    // The topic name is a string constant used to route messages.
    // Convention: use dot notation, bundle prefix first.
    public static function getName(): string
    {
        return 'bridge.digibee_delivery_sync';
    }

    public static function getDescription(): string
    {
        return 'Async processing of Digibee delivery sync';
    }

    // configureMessageBody validates that every message sent to this topic
    // has the correct shape. The OptionsResolver throws if required fields
    // are missing or types are wrong — fail fast at send time.
    public function configureMessageBody(OptionsResolver $resolver): void
    {
        $resolver
            ->setRequired(['uuid', 'method', 'payload'])
            ->setAllowedTypes('uuid', 'string')
            ->setAllowedTypes('method', 'string')
            ->setAllowedTypes('payload', 'array');
    }
}
```

**Register in `services.yml`** with the `oro_message_queue.topic` tag:

```yaml
# src/Bridge/Bundle/BridgeIntegrationBundle/Resources/config/services.yml

services:
    Bridge\Bundle\BridgeIntegrationBundle\Async\Topic\DigibeeDeliverySyncTopic:
        tags:
            - { name: oro_message_queue.topic }
```

WHY the tag: Oro scans tagged services to build its topic registry. Without the tag, the topic is unknown and sending to it throws an exception.

---

### Step 2: Write the Processor

The processor implements two interfaces:
- `MessageProcessorInterface` — provides the `process()` method
- `TopicSubscriberInterface` — declares which topic(s) this processor handles

**File:** `src/Bridge/Bundle/BridgeIntegrationBundle/Async/DigibeeDeliverySyncProcessor.php`

```php
<?php

namespace Bridge\Bundle\BridgeIntegrationBundle\Async;

use Bridge\Bundle\BridgeIntegrationBundle\Async\Topic\DigibeeDeliverySyncTopic;
use Bridge\Bundle\BridgeIntegrationBundle\Service\Bridge\DigibeeDeliverySync;
use Oro\Component\MessageQueue\Consumption\MessageProcessorInterface;
use Oro\Component\MessageQueue\Transport\MessageInterface;
use Oro\Component\MessageQueue\Transport\SessionInterface;
use Oro\Component\MessageQueue\Client\TopicSubscriberInterface;
use Psr\Log\LoggerInterface;

class DigibeeDeliverySyncProcessor implements MessageProcessorInterface, TopicSubscriberInterface
{
    private DigibeeDeliverySync $digibeeDeliverySync;
    private LoggerInterface $logger;

    public function __construct(DigibeeDeliverySync $digibeeDeliverySync, LoggerInterface $logger)
    {
        $this->digibeeDeliverySync = $digibeeDeliverySync;
        $this->logger = $logger;
    }

    public function process(MessageInterface $message, SessionInterface $session): string
    {
        // Track timing — helps diagnose slow processors in logs
        $startTime = microtime(true);

        try {
            // getBody() returns the decoded array (OptionsResolver already validated it)
            $body = $message->getBody();
            $this->digibeeDeliverySync->execute($body['uuid'], $body['method'], $body['payload']);

            $elapsedMs = round((microtime(true) - $startTime) * 1000, 2);
            $this->logger->debug("DigibeeDeliverySync finished ack {$elapsedMs}ms");

            // ACK = message processed successfully, remove from queue
            return self::ACK;

        } catch (\Exception $e) {
            $elapsedMs = round((microtime(true) - $startTime) * 1000, 2);
            $this->logger->error("DigibeeDeliverySync finished reject {$elapsedMs}ms", [
                'error' => $e->getMessage(),
                'trace' => $e->getTraceAsString()
            ]);

            // REJECT = permanent failure, do not requeue.
            // Use REQUEUE instead if the failure is transient (e.g., network timeout).
            return self::REJECT;
        }
    }

    // getSubscribedTopics maps topic names to queue names.
    // The processor will only receive messages for listed topics.
    public static function getSubscribedTopics(): array
    {
        return [
            DigibeeDeliverySyncTopic::getName() => ['destinationName' => 'integration']
        ];
    }
}
```

**Return values:**

| Constant | Meaning | Use when |
|----------|---------|----------|
| `self::ACK` | Success | Work completed, remove message |
| `self::REJECT` | Permanent failure | Bad data, logic error — do not retry |
| `self::REQUEUE` | Transient failure | Network issue, database lock — retry later |

**Register in `services.yml`** with the `oro_message_queue.client.message_processor` tag:

```yaml
services:
    Bridge\Bundle\BridgeIntegrationBundle\Async\DigibeeDeliverySyncProcessor:
        tags:
            - { name: oro_message_queue.client.message_processor, queueName: integration }
```

The `queueName` value must match the `destinationName` in `getSubscribedTopics()`.

---

### Step 3: Send a Message from a Controller

Use `MessageProducerInterface` (injected via constructor) to enqueue work:

**File:** `src/Bridge/Bundle/BridgeIntegrationBundle/Controller/Api/DigibeeIntegrationController.php`

```php
<?php

namespace Bridge\Bundle\BridgeIntegrationBundle\Controller\Api;

use Bridge\Bundle\BridgeIntegrationBundle\Async\Topic\DigibeeDeliverySyncTopic;
use Oro\Component\MessageQueue\Client\MessageProducerInterface;
use Ramsey\Uuid\Uuid;
use Symfony\Bundle\FrameworkBundle\Controller\AbstractController;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\HttpFoundation\Response;
use Symfony\Component\Routing\Annotation\Route;

class DigibeeIntegrationController extends AbstractController
{
    private MessageProducerInterface $messageProducer;

    public function __construct(MessageProducerInterface $messageProducer)
    {
        $this->messageProducer = $messageProducer;
    }

    /**
     * @Route("/admin/api/sap_delivery_integration", name="bridge_api_sap_delivery_integration", methods={"POST"})
     */
    public function postDelivery(Request $request): Response
    {
        $uuid = Uuid::uuid4()->toString();
        $payload = $request->request->all();

        // WHY send to MQ instead of calling the service directly:
        // - The Digibee API call can take several seconds per record
        // - Webhooks expect a fast 200 response (< 2s), not a full processing ack
        // - If the DB write fails, REJECT prevents data loss via retry or dead-letter
        // - The HTTP connection drops when the client moves on — async survives this
        $this->messageProducer->send(DigibeeDeliverySyncTopic::getName(), [
            'uuid'    => $uuid,
            'method'  => 'webservice',
            'payload' => [$payload],
        ]);

        // Return immediately. The actual sync happens in the background.
        return $this->json([
            'success' => [
                'code'    => 200,
                'message' => 'Record has been initially processed, waiting for logic process in async mode.'
            ]
        ]);
    }
}
```

**Inject `MessageProducerInterface` in services.yml** (autowire handles it automatically if using `autowire: true`):

```yaml
services:
    _defaults:
        autowire: true
        autoconfigure: true

    Bridge\Bundle\BridgeIntegrationBundle\Controller\Api\DigibeeIntegrationController:
        tags: ['controller.service_arguments']
```

---

## CRON JOBS

Cron commands in OroCommerce are standard Symfony console commands that additionally implement `CronCommandScheduleDefinitionInterface`. Oro's CronBundle reads the schedule and registers it with the system cron daemon.

### Step 1: Write the Command

**Base class pattern** (from `BridgeBaseCommand`): the project uses an abstract base command to share common behavior — enabled/disabled check, process locking, and timing. Copy this pattern for any new cron command.

**File:** `src/Bridge/Bundle/BridgeIntegrationBundle/Command/BridgeBaseCommand.php`

```php
<?php

namespace Bridge\Bundle\BridgeIntegrationBundle\Command;

use Oro\Bundle\ConfigBundle\Config\ConfigManager;
use Psr\Log\LoggerInterface;
use Symfony\Component\Console\Command\Command;
use Symfony\Component\Console\Command\LockableTrait;
use Symfony\Component\Console\Input\InputInterface;
use Symfony\Component\Console\Output\OutputInterface;

abstract class BridgeBaseCommand extends Command
{
    // LockableTrait provides $this->lock() / $this->release()
    // This prevents two simultaneous cron executions of the same command.
    // WHY: cron fires every N minutes. If the previous run is still executing,
    // a second instance would cause duplicate data or race conditions.
    use LockableTrait;

    protected LoggerInterface $logger;
    protected ConfigManager $configManager;

    protected function execute(InputInterface $input, OutputInterface $output): int
    {
        // Check a system configuration flag before doing any work.
        // Operators can disable individual cron jobs from the admin UI
        // without touching code or removing the crontab entry.
        if (!$this->isCommandEnabled()) {
            $output->writeln(sprintf('Command "%s" is disabled in system configuration.', $this->getName()));
            return self::SUCCESS;
        }

        // Acquire process lock. If another instance holds the lock, exit cleanly.
        if (!$this->lock()) {
            $output->writeln('The command is already running in another process.');
            return self::SUCCESS;
        }

        try {
            return $this->doExecute($input, $output);
        } finally {
            // Always release the lock, even if doExecute throws.
            $this->release();
        }
    }

    abstract protected function doExecute(InputInterface $input, OutputInterface $output): int;

    // Subclasses return the Configuration constant name for their enabled flag.
    // Example: return Configuration::COMMAND_BRIDGE_CUSTOMER_ENABLED;
    abstract protected function getEnabledConfigKey(): string;

    protected function isCommandEnabled(): bool
    {
        return (bool) $this->configManager->get(
            Configuration::ROOT_NODE . '.' . $this->getEnabledConfigKey()
        );
    }

    protected function executeWithTiming(string $serviceName, callable $callback): void
    {
        $startTime = microtime(true);
        $callback();
        $duration = round((microtime(true) - $startTime) * 1000, 2);
        $this->logger->info(sprintf('Command [%s] Execution time: %s ms', $serviceName, $duration));
    }
}
```

**File:** `src/Bridge/Bundle/BridgeIntegrationBundle/Command/BridgeCustomerCommand.php`

```php
<?php

namespace Bridge\Bundle\BridgeIntegrationBundle\Command;

use Bridge\Bundle\BridgeIntegrationBundle\DependencyInjection\Configuration;
use Bridge\Bundle\BridgeIntegrationBundle\Service\SAP\ImportCustomerSFTP;
use Bridge\Bundle\BridgeIntegrationBundle\Service\Bridge\BridgeCustomerSync;
use Oro\Bundle\ConfigBundle\Config\ConfigManager;
use Oro\Bundle\CronBundle\Command\CronCommandScheduleDefinitionInterface;
use Psr\Log\LoggerInterface;
use Ramsey\Uuid\Uuid;
use Symfony\Component\Console\Attribute\AsCommand;
use Symfony\Component\Console\Input\InputInterface;
use Symfony\Component\Console\Output\OutputInterface;

// #[AsCommand] sets the CLI name used in crontab and bin/console calls.
// This is the Symfony 6+ replacement for configuring ->setName() in configure().
#[AsCommand(name: 'oro:cron:bridge-customer')]
class BridgeCustomerCommand extends BridgeBaseCommand implements CronCommandScheduleDefinitionInterface
{
    private ImportCustomerSFTP $importCustomerSFTP;
    private BridgeCustomerSync $customerSyncService;

    public function __construct(
        ImportCustomerSFTP $importCustomerSFTP,
        LoggerInterface $logger,
        BridgeCustomerSync $customerSyncService,
        ConfigManager $configManager
    ) {
        parent::__construct();
        $this->importCustomerSFTP = $importCustomerSFTP;
        $this->logger = $logger;
        $this->customerSyncService = $customerSyncService;
        $this->configManager = $configManager;
    }

    protected function getEnabledConfigKey(): string
    {
        return Configuration::COMMAND_BRIDGE_CUSTOMER_ENABLED;
    }

    // getDefaultDefinition() returns a standard cron expression.
    // OroCommerce registers this with the system cron automatically.
    // WHY: operators can override the schedule in the admin UI without
    // editing crontab — the definition here is just the default.
    public function getDefaultDefinition(): string
    {
        return '5,35 * * * *'; // Every 30 minutes at minute 5 and 35
    }

    protected function configure(): void
    {
        $this->setDescription('Import customers from SFTP and sync addresses - runs every 30 minutes');
    }

    protected function doExecute(InputInterface $input, OutputInterface $output): int
    {
        $uuid = Uuid::uuid4()->toString();

        // executeWithTiming wraps calls and logs duration — useful for SLA monitoring
        $this->executeWithTiming('importCustomerSFTP', function () use ($uuid) {
            $this->importCustomerSFTP->execute($uuid, '');
        });

        $this->executeWithTiming('customerSyncService', function () use ($uuid) {
            $this->customerSyncService->execute($uuid, '', []);
        });

        return self::SUCCESS;
    }
}
```

### Step 2: Register the Command

With `autowire: true` and `autoconfigure: true`, Symfony auto-tags console commands. No explicit tag needed if your bundle uses the namespace-based resource loader:

```yaml
# services.yml
services:
    _defaults:
        autowire: true
        autoconfigure: true
        public: false

    Bridge\Bundle\BridgeIntegrationBundle\:
        resource: "../../*"
        exclude: "../../{DependencyInjection,Resources}"
```

### Step 3: Run the Oro Cron Daemon

OroCommerce manages cron scheduling through its own scheduler — you do NOT add commands directly to system crontab. Instead, add a single entry:

```cron
# /etc/cron.d/orocommerce
* * * * * www-data /path/to/php /path/to/bin/console oro:cron --env=prod >> /dev/null 2>&1
```

The `oro:cron` command checks which jobs are due to run and executes them. Schedules defined by `getDefaultDefinition()` are stored in the database and visible/editable via admin UI.

---

## FEATURE TOGGLES

OroCommerce has a formal feature toggle system via `FeatureBundle`. Features can be globally enabled/disabled and can automatically restrict routes, entities, and API resources.

### Define a Feature in `features.yml`

**File:** `src/Acme/Bundle/AcmeBundle/Resources/config/oro/features.yml`

```yaml
features:
    # Feature key — used in PHP checks and YAML guards
    acme_order_notifications:
        label: acme.feature.order_notifications.label
        description: acme.feature.order_notifications.description

        # 'toggle' links the feature to a system configuration boolean.
        # When the config value is false, the feature is disabled.
        # The config key uses dot notation: <bundle_alias>.<field_name>
        toggle: acme_bundle.order_notifications_enabled

        # When this feature is disabled, these routes return 403
        routes:
            - acme_order_notification_index
            - acme_order_notification_view

        # These entity classes become inaccessible via API when disabled
        api_resources:
            - Acme\Bundle\AcmeBundle\Entity\OrderNotification

        # These navigation menu items are hidden when disabled
        navigation_items:
            - application_menu.notifications_tab.acme_order_notification_list

        # These system configuration fields are hidden when disabled
        configuration:
            - acme_bundle.order_notifications_recipient_email
```

**No tag needed** — `features.yml` is auto-discovered from `Resources/config/oro/`.

### Check a Feature in PHP

Inject `FeatureChecker` and call `isFeatureEnabled()`:

```php
<?php

use Oro\Bundle\FeatureToggleBundle\Checker\FeatureChecker;

class OrderNotificationService
{
    private FeatureChecker $featureChecker;

    public function __construct(FeatureChecker $featureChecker)
    {
        $this->featureChecker = $featureChecker;
    }

    public function sendNotification(Order $order): void
    {
        // Guard with feature check before doing any work.
        // This is cheaper than reading config directly and respects
        // all feature flag sources (config toggle, entity-level, etc.)
        if (!$this->featureChecker->isFeatureEnabled('acme_order_notifications')) {
            return;
        }

        // ... send notification
    }
}
```

### Check a Feature in YAML Service Definition

Use the `oro_featuretogle.feature` tag to auto-disable services when a feature is off:

```yaml
services:
    Acme\Bundle\AcmeBundle\Service\OrderNotificationService:
        tags:
            - { name: oro_featuretogle.feature, feature: acme_order_notifications }
```

When the feature is disabled, calls to this service are silently no-op'd (for classes implementing `FeatureToggleableInterface`) or the service is entirely removed from the container (for certain extension points).

---

## SYSTEM CONFIGURATION VALUES

System configuration (`ConfigBundle`) stores settings per scope: global, organization, website, customer group, customer user. The admin UI at `/admin/config/system/` displays these fields.

### Define Configuration Fields

**File:** `src/Bridge/Bundle/BridgeIntegrationBundle/DependencyInjection/Configuration.php`

```php
<?php

namespace Bridge\Bundle\BridgeIntegrationBundle\DependencyInjection;

use Oro\Bundle\ConfigBundle\DependencyInjection\SettingsBuilder;
use Symfony\Component\Config\Definition\Builder\TreeBuilder;
use Symfony\Component\Config\Definition\ConfigurationInterface;

class Configuration implements ConfigurationInterface
{
    // ROOT_NODE is the bundle alias used as the config key prefix.
    // All config keys become: bridge_integration.<field_name>
    public const ROOT_NODE = 'bridge_integration';

    // Define constants for each config key to avoid magic strings throughout the codebase.
    public const COMMAND_BRIDGE_CUSTOMER_ENABLED = 'command_bridge_customer_enabled';
    public const SAP_FINANCE_ENABLED             = 'sap_finance_enabled';
    public const SAP_FINANCE_INFORMATION_TIMEOUT = 'sap_finance_information_timeout';
    public const VM2_AUTHORIZATION               = 'vm2_authorization';

    public function getConfigTreeBuilder(): TreeBuilder
    {
        $treeBuilder = new TreeBuilder(self::ROOT_NODE);
        $rootNode    = $treeBuilder->getRootNode();

        // SettingsBuilder::append registers each key with its default value.
        // The value stored here is the fallback used when no admin override exists.
        SettingsBuilder::append(
            $rootNode,
            [
                self::COMMAND_BRIDGE_CUSTOMER_ENABLED => ['value' => true],
                self::SAP_FINANCE_ENABLED             => ['value' => true],
                self::SAP_FINANCE_INFORMATION_TIMEOUT => ['value' => 5],
                self::VM2_AUTHORIZATION               => ['value' => null],
            ]
        );

        return $treeBuilder;
    }
}
```

**File:** `src/Bridge/Bundle/BridgeIntegrationBundle/Resources/config/oro/system_configuration.yml`

```yaml
system_configuration:
    groups:
        bridge_integration:
            title: bridge.system_configuration.groups.integration.title
            icon: "fa-bold"
        command_toggles:
            title: bridge.system_configuration.groups.command_toggles.title

    fields:
        # Boolean toggle — shows as a checkbox in admin UI
        bridge_integration.command_bridge_customer_enabled:
            data_type: boolean
            type: Oro\Bundle\ConfigBundle\Form\Type\ConfigCheckbox
            priority: 120
            options:
                label: bridge.system_configuration.fields.command_bridge_customer_enabled.label
                tooltip: bridge.system_configuration.fields.command_bridge_customer_enabled.tooltip
                required: false

        # Integer with range validation
        bridge_integration.sap_finance_information_timeout:
            data_type: integer
            type: Symfony\Component\Form\Extension\Core\Type\IntegerType
            priority: 29
            options:
                label: bridge.system_configuration.fields.sap_finance_information_timeout.label
                required: false
                constraints:
                    - Range:
                          min: 1
                          max: 1440

        # Encrypted password field — stored encrypted, shown as masked in UI
        bridge_integration.vm2_authorization:
            data_type: string
            type: Oro\Bundle\FormBundle\Form\Type\OroEncodedPlaceholderPasswordType
            search_type: text
            priority: 80
            options:
                label: bridge.system_configuration.fields.vm2_authorization.label
                resettable: true
                required: false
                constraints:
                    - Length:
                          max: 255

    tree:
        system_configuration:
            platform:
                children:
                    integrations:
                        children:
                            bridge_integration:
                                priority: 1000
                                children:
                                    command_toggles:
                                        priority: 1
                                        children:
                                            - bridge_integration.command_bridge_customer_enabled
```

### Read Configuration in PHP

```php
<?php

use Oro\Bundle\ConfigBundle\Config\ConfigManager;
use Bridge\Bundle\BridgeIntegrationBundle\DependencyInjection\Configuration;

class MyService
{
    private ConfigManager $configManager;

    public function __construct(ConfigManager $configManager)
    {
        $this->configManager = $configManager;
    }

    private function getConfigValue(string $key): mixed
    {
        // Config keys use dot notation: <root_node>.<field_name>
        return $this->configManager->get(Configuration::ROOT_NODE . '.' . $key);
    }

    public function isEnabled(): bool
    {
        return (bool) $this->getConfigValue(Configuration::SAP_FINANCE_ENABLED);
    }

    public function getTimeout(): int
    {
        return (int) $this->getConfigValue(Configuration::SAP_FINANCE_INFORMATION_TIMEOUT);
    }
}
```

### Scope: Reading Config Per-Website

By default, `ConfigManager->get()` returns the most specific value for the current request scope (global → organization → website — most specific wins). To read a value for a specific website, pass a `Website` entity as the third argument:

```php
<?php

use Oro\Bundle\ConfigBundle\Config\ConfigManager;
use Oro\Bundle\WebsiteBundle\Entity\Website;

class WebsiteAwareService
{
    private ConfigManager $configManager;

    public function __construct(ConfigManager $configManager)
    {
        $this->configManager = $configManager;
    }

    public function getTimeoutForWebsite(Website $website): int
    {
        // The third argument ($scopeIdentifier) tells ConfigManager to resolve
        // the value as if the current scope were this specific website.
        // If the website has no override, it falls back to organization, then global.
        return (int) $this->configManager->get(
            'bridge_integration.' . Configuration::SAP_FINANCE_INFORMATION_TIMEOUT,
            false,          // $default — return raw value, not default fallback
            false,          // $full — return scalar value, not metadata array
            $website        // $scopeIdentifier
        );
    }

    /**
     * Read the same setting for multiple websites at once.
     * Returns array keyed by website ID.
     */
    public function getTimeoutForAllWebsites(array $websites): array
    {
        return $this->configManager->getValues(
            'bridge_integration.' . Configuration::SAP_FINANCE_INFORMATION_TIMEOUT,
            $websites
        );
    }
}
```

**Scope hierarchy (most specific wins):**
1. Customer user
2. Customer
3. Customer group
4. Website
5. Organization
6. Global

---

## FULL ASYNC CHAIN WALKTHROUGH

This traces the complete flow for a Digibee delivery webhook: external event fires → message enqueued → processor handles it → result stored.

```
1. Digibee (external SAP system) POSTs to:
   POST /admin/api/sap_delivery_integration

2. DigibeeIntegrationController::postDelivery() runs (HTTP thread, must be fast):
   a. Validates the endpoint is enabled via ConfigManager flag
   b. Generates a UUID for traceability across logs
   c. Calls $this->messageProducer->send('bridge.digibee_delivery_sync', [...])
      - The message is persisted to the database (CE) or RabbitMQ (EE)
      - This call returns immediately — no waiting for processing
   d. Returns HTTP 200 JSON in < 10ms

3. MQ Consumer (background daemon) picks up the message:
   a. Matches 'bridge.digibee_delivery_sync' to DigibeeDeliverySyncProcessor
   b. OptionsResolver validates message body shape against DigibeeDeliverySyncTopic
   c. Calls DigibeeDeliverySyncProcessor::process()

4. DigibeeDeliverySyncProcessor::process():
   a. Extracts uuid, method, payload from $message->getBody()
   b. Calls $this->digibeeDeliverySync->execute(uuid, method, payload)
      - DigibeeDeliverySync performs the actual DB writes and business logic
      - This is where the "real" work happens — can take seconds, that is OK
   c. Logs timing information
   d. Returns self::ACK — message removed from queue

5. If execute() throws an exception:
   a. Error is logged with full stack trace
   b. Returns self::REJECT — message is not requeued
   c. With RabbitMQ (EE), a dead-letter queue can capture REJECT'd messages
      for later inspection

6. Result stored:
   - DigibeeDeliverySync writes processed data to OroCommerce entities
   - AaxisIntegrationService logs start/finish times for the integration dashboard
   - The integration dashboard at /admin/aaxis/integration/ shows the result
```

---

## COMMON PITFALLS

### Pitfall 1: Not running the MQ consumer

Messages queue silently with no error. Check:
```bash
php bin/console oro:message-queue:topics         # list registered topics
php bin/console oro:message-queue:consume --env=prod  # start consumer
```

### Pitfall 2: Returning REJECT for transient errors

Network timeouts, database locks, and third-party API rate limits are transient. Use `self::REQUEUE` so the message is retried:
```php
} catch (NetworkException $e) {
    $this->logger->warning('Transient error, will requeue', ['error' => $e->getMessage()]);
    return self::REQUEUE;  // retried automatically
} catch (\Exception $e) {
    $this->logger->error('Permanent failure', ['error' => $e->getMessage()]);
    return self::REJECT;   // do not retry
}
```

### Pitfall 3: Forgetting the `oro_message_queue.topic` tag

The topic must be tagged in `services.yml`. Without it, `$messageProducer->send()` throws:
> `MessageTopicRegistry: Topic "bridge.my_topic" is not registered.`

### Pitfall 4: Missing `queueName` alignment

The `queueName` in the `oro_message_queue.client.message_processor` tag and the `destinationName` in `getSubscribedTopics()` must match. Mismatches cause messages to go to the wrong queue and never be consumed.

### Pitfall 5: Not using LockableTrait in cron commands

Without a process lock, overlapping cron runs cause duplicate records. Always add:
```php
use Symfony\Component\Console\Command\LockableTrait;
// ...
if (!$this->lock()) {
    return self::SUCCESS;
}
```

### Pitfall 6: Reading config with a wrong key format

Config keys use dot notation with the bundle root node:
```php
// CORRECT
$this->configManager->get('bridge_integration.sap_customer_enabled');

// WRONG — missing root node prefix
$this->configManager->get('sap_customer_enabled');
```

---

## REFERENCE: MQ SERVICE TAGS

| Tag | Purpose |
|-----|---------|
| `oro_message_queue.topic` | Register a Topic class |
| `oro_message_queue.client.message_processor` | Register a Processor class |

`queueName` values used in this project:
- `integration` — all external system sync processors (Digibee, Zoho, SAP, Edge, Aaxis)
- `default` — Oro platform background tasks

---

## REFERENCE: CRON EXPRESSION EXAMPLES

| Expression | When it runs |
|------------|-------------|
| `5,35 * * * *` | Every 30 minutes, at :05 and :35 past each hour |
| `*/5 * * * *` | Every 5 minutes |
| `0 * * * *` | Every hour on the hour |
| `0 2 * * *` | Every day at 2:00 AM |
| `0 1 * * 0` | Every Sunday at 1:00 AM |

---

## REFERENCE: RELEVANT FILES IN THIS PROJECT

| File | Purpose |
|------|---------|
| `src/Bridge/Bundle/BridgeIntegrationBundle/Async/Topic/` | All topic definitions |
| `src/Bridge/Bundle/BridgeIntegrationBundle/Async/` | All processor classes |
| `src/Bridge/Bundle/BridgeIntegrationBundle/Command/BridgeBaseCommand.php` | Cron base class with lock + enable check |
| `src/Bridge/Bundle/BridgeIntegrationBundle/Command/` | All cron commands |
| `src/Bridge/Bundle/BridgeIntegrationBundle/Resources/config/services.yml` | MQ topic + processor service tags |
| `src/Bridge/Bundle/BridgeIntegrationBundle/DependencyInjection/Configuration.php` | Config constants and defaults |
| `src/Bridge/Bundle/BridgeIntegrationBundle/Resources/config/oro/system_configuration.yml` | Admin UI config field definitions |
| `src/Bridge/Bundle/BridgeIntegrationBundle/Controller/Api/DigibeeIntegrationController.php` | Example: send message from controller |
| `src/Aaxis/Bundle/AaxisIntegrationBundle/Async/Topic/` | Aaxis-specific topic definitions |
| `src/Aaxis/Bundle/AaxisIntegrationBundle/Async/` | Aaxis-specific processor classes |
