# OroCommerce Message Queue — Complete Developer Reference

> Source: https://doc.oroinc.com/master/backend/mq/

## AGENT QUERY HINTS

Use this file when asked about:
- "How do I send a message to the queue?"
- "How do I create a message processor?"
- "How do I define a message topic?"
- "How do I run long-running background tasks?"
- "What is ACK / REJECT / REQUEUE?"
- "How do I track job progress?"
- "How does MQ work in Oro?"
- "What transport should I use — DBAL vs RabbitMQ?"
- "How do I create child/parallel jobs?"
- "How do dependent jobs work?"

---

## 1. Architecture Overview

OroCommerce's message queue enables **asynchronous, decoupled processing**. The sender does not wait for the receiver to process the message. This is the backbone of all background operations in Oro — imports, exports, email sending, search indexing, pricing recalculation, and more.

### Core Components

| Component | Interface / Class | Responsibility |
|---|---|---|
| **Topic** | `TopicInterface` | Defines the message type, body schema, and priority |
| **Producer** | `MessageProducerInterface` | Sends messages to the queue |
| **Processor** | `MessageProcessorInterface` | Consumes and processes messages |
| **Consumer** | CLI: `oro:message-queue:consume` | Pulls messages and dispatches to processors |
| **JobRunner** | `JobRunner` | Tracks long-running tasks, enables sub-jobs |
| **Transport** | DBAL or AMQP (RabbitMQ) | Underlying message broker |

### Message Flow

```
[Producer] --> [Queue / Broker] --> [Consumer loop] --> [Processor]
                                                              |
                                                       [JobRunner] (optional)
```

---

## 2. Transport Options

### DBAL Transport (Default — all editions)

Uses the application's PostgreSQL/MySQL database as a broker. No external infrastructure required.

```yaml
# config/parameters.yml or app.yml
oro_message_queue:
  transport:
    default: 'dbal'
    dbal:
      connection: default           # Doctrine DBAL connection name
      table: oro_message_queue      # Table used as the queue
      pid_file_dir: /tmp/oro-message-queue
      consumer_process_pattern: ':consume'
      polling_interval: 1000        # Milliseconds between polls (default: 1000)
```

**Limitations of DBAL:**
- Polling-based — the consumer checks for new messages every second.
- Effectively one message per second per consumer process.
- If a consumer crashes mid-message, the message remains locked. The `RedeliverOrphanMessagesExtension` eventually redelivers it.

### AMQP / RabbitMQ Transport (Enterprise Edition)

Superior performance. Event-driven. Supports complex routing, multiple queues, and separate consumer pools.

```yaml
# config/parameters.yml
parameters:
  message_queue_transport_dsn: '%env(ORO_MQ_DSN)%'
  env(ORO_MQ_DSN): 'dbal:'   # Override with amqp:// in production

# Environment variable for RabbitMQ:
# ORO_MQ_DSN=amqp://guest:guest@localhost:5672
```

**WHY choose RabbitMQ:** When you need high throughput (many messages per second), multiple parallel consumers, or priority queues. Required for Enterprise-grade deployments.

---

## 3. Defining a Message Topic

A **Topic** is a named contract that describes:
- The message identifier (string name)
- The expected body structure (validated via `OptionsResolver`)
- The default processing priority

### Step 1 — Implement `TopicInterface`

```php
<?php
// src/Bridge/Bundle/BridgeIntegrationBundle/Async/Topic/SyncProductsTopic.php

namespace Bridge\Bundle\BridgeIntegrationBundle\Async\Topic;

use Oro\Component\MessageQueue\Topic\AbstractTopic;
use Symfony\Component\OptionsResolver\OptionsResolver;

/**
 * Topic for triggering asynchronous SAP product synchronization.
 */
class SyncProductsTopic extends AbstractTopic
{
    /**
     * Unique topic name — use dot-separated lowercase identifiers.
     * Convention: <vendor>.<bundle_short>.<action>
     */
    public static function getName(): string
    {
        return 'bridge.integration.sync_products';
    }

    /**
     * Short human-readable description shown in admin UI and logs.
     * Keep under 80 characters.
     */
    public static function getDescription(): string
    {
        return 'Synchronize products from SAP via SFTP';
    }

    /**
     * Default priority — affects queue ordering.
     * Constants from Oro\Component\MessageQueue\Client\MessagePriority:
     *   VERY_LOW | LOW | NORMAL | HIGH | VERY_HIGH
     */
    public function getDefaultPriority(string $queueName): string
    {
        return \Oro\Component\MessageQueue\Client\MessagePriority::NORMAL;
    }

    /**
     * Declare and validate the message body structure.
     * Called before sending AND before processing — invalid messages are rejected.
     */
    public function configureMessageBody(OptionsResolver $resolver): void
    {
        $resolver
            ->setDefined(['batchSize', 'forceUpdate'])
            ->setDefaults([
                'batchSize'   => 100,
                'forceUpdate' => false,
            ])
            ->addAllowedTypes('batchSize', 'int')
            ->addAllowedTypes('forceUpdate', 'bool');
    }
}
```

**Key rules for topic names:**
- Lowercase letters, digits, dots (`.`), and underscores (`_`) only.
- Must be globally unique across all bundles.

### Step 2 — Register as a Service

```yaml
# src/Bridge/Bundle/BridgeIntegrationBundle/Resources/config/services.yml
services:
    _defaults:
        tags:
            - { name: oro_message_queue.topic }

    Bridge\Bundle\BridgeIntegrationBundle\Async\Topic\SyncProductsTopic: ~
```

**WHY the `_defaults` tag approach:** It applies `oro_message_queue.topic` to every service in the file. For topic-only files this is clean. If the file has other services, tag each topic explicitly instead.

### Job-Aware Topics

If the processor for this topic will create a Job (for tracking/monitoring), implement `JobAwareTopicInterface` too:

```php
use Oro\Component\MessageQueue\Topic\JobAwareTopicInterface;

class SyncProductsTopic extends AbstractTopic implements JobAwareTopicInterface
{
    // ...

    /**
     * Returns a unique job name derived from the message body.
     * Called immediately when the message is created (before queuing).
     * This enables deduplication — runUniqueByMessage uses this name.
     */
    public function createJobName(array $messageBody): string
    {
        return sprintf('bridge.integration.sync_products:batch_%d', $messageBody['batchSize']);
    }
}
```

---

## 4. Creating a Message Processor

A **Processor** receives one message at a time and returns a status code telling the broker what to do next.

### Return Status Codes

| Constant | Value | Meaning |
|---|---|---|
| `self::ACK` | `'oro.message_queue.consumption.ack'` | Message processed successfully. Remove from queue. |
| `self::REJECT` | `'oro.message_queue.consumption.reject'` | Message is bad/unprocessable. Discard it (do not requeue). |
| `self::REQUEUE` | `'oro.message_queue.consumption.requeue'` | Processing failed temporarily. Put back in queue for retry. |

### Basic Processor

```php
<?php
// src/Bridge/Bundle/BridgeIntegrationBundle/Async/SyncProductsProcessor.php

namespace Bridge\Bundle\BridgeIntegrationBundle\Async;

use Bridge\Bundle\BridgeIntegrationBundle\Async\Topic\SyncProductsTopic;
use Bridge\Bundle\BridgeIntegrationBundle\Service\SAP\ImportProductSFTP;
use Oro\Component\MessageQueue\Consumption\MessageProcessorInterface;
use Oro\Component\MessageQueue\Transport\MessageInterface;
use Oro\Component\MessageQueue\Transport\SessionInterface;
use Oro\Component\MessageQueue\Client\TopicSubscriberInterface;
use Psr\Log\LoggerInterface;

/**
 * Processes product synchronization messages from the SAP integration topic.
 */
class SyncProductsProcessor implements MessageProcessorInterface, TopicSubscriberInterface
{
    public function __construct(
        private readonly ImportProductSFTP $importService,
        private readonly LoggerInterface $logger,
    ) {}

    /**
     * Declares which topics this processor handles.
     * The framework routes messages automatically.
     */
    public static function getSubscribedTopics(): array
    {
        return [SyncProductsTopic::getName()];
    }

    /**
     * Main processing method. Called once per message.
     *
     * @param MessageInterface $message  The raw message from the broker.
     *                                  Use $message->getBody() to get the decoded array.
     * @param SessionInterface $session  Transport session (rarely used directly).
     * @return string  One of: self::ACK, self::REJECT, self::REQUEUE
     */
    public function process(MessageInterface $message, SessionInterface $session): string
    {
        $body = $message->getBody(); // Already decoded to array by the framework

        try {
            $this->importService->import(
                batchSize:   $body['batchSize'],
                forceUpdate: $body['forceUpdate'],
            );

            return self::ACK;

        } catch (\RuntimeException $e) {
            // Transient error (e.g., SFTP timeout) — retry later
            $this->logger->warning(
                'Product sync failed, requeueing',
                ['error' => $e->getMessage(), 'body' => $body]
            );
            return self::REQUEUE;

        } catch (\InvalidArgumentException $e) {
            // Bad message — do not retry
            $this->logger->error(
                'Invalid product sync message, rejecting',
                ['error' => $e->getMessage(), 'body' => $body]
            );
            return self::REJECT;
        }
    }
}
```

### Register Processor as a Service

```yaml
# src/Bridge/Bundle/BridgeIntegrationBundle/Resources/config/services.yml
services:
    Bridge\Bundle\BridgeIntegrationBundle\Async\SyncProductsProcessor:
        arguments:
            - '@Bridge\Bundle\BridgeIntegrationBundle\Service\SAP\ImportProductSFTP'
            - '@logger'
        tags:
            - { name: oro_message_queue.client.message_processor }
```

**WHY `TopicSubscriberInterface`:** It lets the processor declare its own topic subscriptions, keeping the routing logic inside the processor class rather than scattered in YAML. The framework reads `getSubscribedTopics()` at compile time.

---

## 5. Sending Messages (Producer)

Inject `MessageProducerInterface` and call `send()`.

```php
<?php
// src/Bridge/Bundle/BridgeIntegrationBundle/Command/SyncProductsCommand.php

use Bridge\Bundle\BridgeIntegrationBundle\Async\Topic\SyncProductsTopic;
use Oro\Component\MessageQueue\Client\MessageProducerInterface;

class SyncProductsCommand extends Command
{
    public function __construct(
        private readonly MessageProducerInterface $producer,
    ) {
        parent::__construct();
    }

    protected function execute(InputInterface $input, OutputInterface $output): int
    {
        // Send a message — the body must match the topic's OptionsResolver schema
        $this->producer->send(
            SyncProductsTopic::getName(),
            [
                'batchSize'   => 500,
                'forceUpdate' => false,
            ]
        );

        $output->writeln('Sync message queued.');
        return Command::SUCCESS;
    }
}
```

**The producer validates the message body** against the topic's `configureMessageBody()` before enqueuing. If invalid, it logs an error (or throws `InvalidMessageBodyException` in debug mode).

---

## 6. Jobs API — Long-Running and Parallel Tasks

Use the **Jobs API** when:
- The task takes more than a few seconds.
- You need progress monitoring in the admin UI (**System > Jobs**).
- You need to prevent duplicate execution (unique jobs).
- You need to run sub-tasks in parallel and coordinate their completion.

### Core API — `JobRunner`

| Method | When to use |
|---|---|
| `runUnique($ownerId, $name, $closure)` | Single unique job — prevents duplicate runs of the same job name |
| `runUniqueByMessage($message, $closure)` | Preferred when topic implements `JobAwareTopicInterface` — job name comes from `createJobName()` |
| `createDelayed($name, $closure)` | Create a child job that will be processed by a separate message/processor |
| `runDelayed($jobId, $closure)` | Execute a previously created delayed (child) job |

### Pattern A — Single Unique Job

```php
public function process(MessageInterface $message, SessionInterface $session): string
{
    $body = $message->getBody();

    $result = $this->jobRunner->runUniqueByMessage(
        $message,
        function (JobRunner $runner, Job $job) use ($body): bool {
            // All work happens inside this closure.
            // Return true  => job STATUS_SUCCESS, processor returns ACK
            // Return false => job STATUS_FAILED,  processor returns REJECT
            $this->doImport($body);
            return true;
        }
    );

    return $result ? self::ACK : self::REJECT;
}
```

### Pattern B — Parallel Child Jobs (Fan-Out)

Use this when you want to split a large task into many parallel chunks.

**Step 1 Processor — creates child jobs and dispatches sub-messages:**

```php
public function process(MessageInterface $message, SessionInterface $session): string
{
    $body   = $message->getBody();
    $chunks = $this->splitIntoBatches($body['ids'], 100);

    $result = $this->jobRunner->runUniqueByMessage(
        $message,
        function (JobRunner $runner, Job $rootJob) use ($chunks): bool {
            foreach ($chunks as $index => $chunk) {
                // createDelayed creates a child job record in the DB
                $runner->createDelayed(
                    sprintf('bridge.integration.sync_products.chunk:%d', $index),
                    function (JobRunner $runner, Job $childJob) use ($chunk): void {
                        // Send a new message to process this specific chunk.
                        // Pass the child job ID so Step 2 can resolve it.
                        $this->producer->send(SyncProductsChunkTopic::getName(), [
                            'ids'   => $chunk,
                            'jobId' => $childJob->getId(),
                        ]);
                    }
                );
            }
            return true;
        }
    );

    return $result ? self::ACK : self::REJECT;
}
```

**Step 2 Processor — processes one chunk, resolves child job:**

```php
public function process(MessageInterface $message, SessionInterface $session): string
{
    $body = $message->getBody();

    $result = $this->jobRunner->runDelayed(
        $body['jobId'],          // The child job ID passed from Step 1
        function (JobRunner $runner, Job $job) use ($body): bool {
            $this->processChunk($body['ids']);
            return true;
        }
    );

    return $result ? self::ACK : self::REJECT;
}
```

### Pattern C — Dependent Jobs (Run after completion)

Trigger follow-up messages only after the root job finishes:

```php
$result = $this->jobRunner->runUniqueByMessage(
    $message,
    function (JobRunner $runner, Job $rootJob) use ($body): bool {
        // Schedule dependent messages to send after THIS job completes
        $context = $this->dependentJobService->createDependentJobContext($rootJob->getRootJob());
        $context->addDependentJob(NotifyAdminTopic::getName(), ['subject' => 'Sync done']);
        $context->addDependentJob(
            RebuildSearchIndexTopic::getName(),
            ['entities' => ['Product']],
            \Oro\Component\MessageQueue\Client\MessagePriority::HIGH
        );
        $this->dependentJobService->saveDependentJob($context);

        $this->doWork($body);
        return true;
    }
);
```

**Note:** Dependent jobs only work on root jobs created by `runUnique` / `runUniqueByMessage`. They do **not** work on child jobs created by `runDelayed`.

---

## 7. Job Statuses

| Status | Meaning |
|---|---|
| `STATUS_NEW` | Created but not yet picked up by a consumer |
| `STATUS_RUNNING` | Currently being processed |
| `STATUS_SUCCESS` | Closure returned `true` |
| `STATUS_FAILED` | Closure returned `false` or threw an exception |
| `STATUS_CANCELLED` | Manually interrupted via admin UI |
| `STATUS_STALE` | Exceeded inactivity timeout or max redelivery attempts |

### Configuring Stale Thresholds

```yaml
# config/config.yml or Resources/config/oro/app.yml
oro_message_queue:
  time_before_stale:
    default: 1800           # 30 minutes — global default
    jobs:
      'bridge.integration.sync_products': 7200   # 2 hours for this specific job
  redelivery_max_runtime:
    default: -1             # Disabled globally
    jobs:
      'bridge.integration.sync_products.chunk': 600  # 10 minutes per chunk
```

---

## 8. Error Handling and Retries

### REQUEUE vs REJECT

- Return `self::REQUEUE` for **transient** failures (network timeout, DB lock, external API down). The message goes back in the queue.
- Return `self::REJECT` for **permanent** failures (malformed message, business logic violation). The message is discarded.

### Message Body Validation

The framework validates message bodies in two places:

1. **On send** (producer side): Invalid body is logged as an error. In debug mode, `InvalidMessageBodyException` is thrown.
2. **On consume** (`MessageBodyResolverExtension`): Invalid body is rejected before the processor runs.

### Consumer Automatic Interruption

The consumer halts itself (after finishing the current message) when:
- Memory limit exceeded
- Time limit reached
- Message count limit reached
- Cache was cleared
- DB schema was updated
- Maintenance mode disabled

Always run the consumer under a process manager (Supervisor, systemd) so it restarts automatically.

---

## 9. Consumer Heartbeat

The consumer sends periodic heartbeat signals. The `oro:cron:message-queue:consumer_heartbeat_check` cron command verifies liveness and notifies admins if consumers are down.

```yaml
oro_message_queue:
  consumer:
    heartbeat_update_period: 20  # minutes (default: 15)
    # Set to 0 to disable heartbeat notifications
```

---

## 10. Complete Annotated Example

Below is a full, production-style example for a SAP product import.

### Topic

```php
<?php
namespace Bridge\Bundle\BridgeIntegrationBundle\Async\Topic;

use Oro\Component\MessageQueue\Topic\AbstractTopic;
use Oro\Component\MessageQueue\Topic\JobAwareTopicInterface;
use Symfony\Component\OptionsResolver\OptionsResolver;

class ImportSapProductsTopic extends AbstractTopic implements JobAwareTopicInterface
{
    public static function getName(): string
    {
        return 'bridge.integration.import_sap_products';
    }

    public static function getDescription(): string
    {
        return 'Import products from SAP SFTP in batches';
    }

    public function getDefaultPriority(string $queueName): string
    {
        return \Oro\Component\MessageQueue\Client\MessagePriority::NORMAL;
    }

    public function configureMessageBody(OptionsResolver $resolver): void
    {
        $resolver
            ->setRequired(['batchSize'])
            ->setDefaults(['forceUpdate' => false])
            ->addAllowedTypes('batchSize', 'int')
            ->addAllowedTypes('forceUpdate', 'bool')
            ->addAllowedValues('batchSize', fn(int $v) => $v > 0 && $v <= 1000);
    }

    public function createJobName(array $messageBody): string
    {
        return 'bridge.integration.import_sap_products';
    }
}
```

### Processor

```php
<?php
namespace Bridge\Bundle\BridgeIntegrationBundle\Async;

use Bridge\Bundle\BridgeIntegrationBundle\Async\Topic\ImportSapProductsTopic;
use Bridge\Bundle\BridgeIntegrationBundle\Service\SAP\ImportProductSFTP;
use Oro\Component\MessageQueue\Client\TopicSubscriberInterface;
use Oro\Component\MessageQueue\Consumption\MessageProcessorInterface;
use Oro\Component\MessageQueue\Job\JobRunner;
use Oro\Component\MessageQueue\Job\Job;
use Oro\Component\MessageQueue\Transport\MessageInterface;
use Oro\Component\MessageQueue\Transport\SessionInterface;
use Psr\Log\LoggerInterface;

class ImportSapProductsProcessor implements MessageProcessorInterface, TopicSubscriberInterface
{
    public function __construct(
        private readonly JobRunner $jobRunner,
        private readonly ImportProductSFTP $importService,
        private readonly LoggerInterface $logger,
    ) {}

    public static function getSubscribedTopics(): array
    {
        return [ImportSapProductsTopic::getName()];
    }

    public function process(MessageInterface $message, SessionInterface $session): string
    {
        $body = $message->getBody();

        $result = $this->jobRunner->runUniqueByMessage(
            $message,
            function (JobRunner $runner, Job $job) use ($body): bool {
                try {
                    $imported = $this->importService->import(
                        $body['batchSize'],
                        $body['forceUpdate'],
                    );

                    $this->logger->info(
                        'SAP product import complete',
                        ['imported' => $imported, 'jobId' => $job->getId()]
                    );

                    return true;

                } catch (\Exception $e) {
                    $this->logger->error(
                        'SAP product import failed',
                        ['error' => $e->getMessage(), 'body' => $body]
                    );
                    return false; // Marks job as STATUS_FAILED
                }
            }
        );

        return $result ? self::ACK : self::REJECT;
    }
}
```

### Service Registration

```yaml
# Resources/config/services.yml
services:
    Bridge\Bundle\BridgeIntegrationBundle\Async\Topic\ImportSapProductsTopic:
        tags:
            - { name: oro_message_queue.topic }

    Bridge\Bundle\BridgeIntegrationBundle\Async\ImportSapProductsProcessor:
        arguments:
            - '@oro_message_queue.client.job_runner'
            - '@Bridge\Bundle\BridgeIntegrationBundle\Service\SAP\ImportProductSFTP'
            - '@logger'
        tags:
            - { name: oro_message_queue.client.message_processor }
```

### Sending

```php
$this->producer->send(
    ImportSapProductsTopic::getName(),
    ['batchSize' => 200, 'forceUpdate' => false]
);
```

---

## 11. Admin UI

- **System > Jobs** — view all jobs, their statuses, child jobs, and runtime.
- You can manually **interrupt** a running job from the UI (sets status to `STATUS_CANCELLED`).

---

## 12. Running the Consumer

```bash
# Development
php bin/console oro:message-queue:consume -vvv

# Production (recommended settings)
php bin/console --env=prod --no-debug oro:message-queue:consume \
    --memory-limit=512 \    # MB — consumer exits if PHP exceeds this
    --time-limit=600        # Seconds — consumer exits after 10 min (prevents DB connection staleness)

# Explicit queue and processor (for debugging one processor)
php bin/console --env=prod oro:message-queue:transport:consume \
    oro.default \
    bridge.integration.import_sap_products_processor
```

**Memory limit guidance:** Set 2-3x lower than `memory_limit` in php.ini. If php.ini is `1024M`, set `--memory-limit=256` or `--memory-limit=384`.

**WHY time limits on DBAL:** Long-running consumers can hit PostgreSQL connection timeouts. Restarting every 5-10 minutes avoids this without losing messages.
