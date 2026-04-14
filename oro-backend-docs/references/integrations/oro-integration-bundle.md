# OroIntegrationBundle: Custom Integrations

> Source: https://doc.oroinc.com/master/backend/integrations/integration-config/

## AGENT QUERY HINTS

Use this file when asked about:
- "How do I create a custom integration in OroCommerce?"
- "What is a Channel in OroIntegrationBundle?"
- "How do I implement a Transport for integration?"
- "How do I create a Connector for syncing data?"
- "How does the integration sync process work?"
- "What is reverse synchronization?"
- "How do payment or shipping integrations work?"
- "How do I configure integration settings in the UI?"
- "What is the difference between Integration and Import/Export?"
- "When should I use OroIntegrationBundle vs Import/Export?"

---

## Overview

`OroIntegrationBundle` provides a native framework for building **bidirectional, real-time integrations** with third-party systems directly within the OroCommerce admin UI. It handles:

- Persistent integration configuration stored in the database (editable in admin)
- User access control and security for integration credentials
- Scheduled and on-demand data synchronization
- Reverse synchronization (pushing changes from Oro to external systems)
- Built-in support for payment and shipping method integrations

**WHY use OroIntegrationBundle instead of Import/Export**: Choose OroIntegrationBundle when you need real-time or near-real-time sync, UI-managed credentials, bidirectional data flow, or when building payment/shipping integrations. Import/Export is better for batch file-exchange scenarios.

**WHY use Import/Export instead of OroIntegrationBundle**: Import/Export is simpler to build, easier for non-Oro developers to maintain, and better for large periodic batch loads where latency is acceptable.

---

## Core Concepts

### Channel (Integration)

A **Channel** (also called an Integration) is the top-level configuration entity representing a connection to a specific external system. It is stored as a `Channel` entity in the database and is configurable through the admin UI at **System > Integrations**.

Each Channel has:
- A **type** — identifies which integration class handles it (e.g., `mailchimp`, `google_calendar`)
- A **transport** — connection settings (credentials, endpoints)
- A **status** — enabled/disabled
- One or more **connectors** — responsible for syncing specific resource types

### Transport

A **Transport** stores and manages connection parameters for an integration (API keys, OAuth tokens, base URLs, etc.). It is a Doctrine entity that persists credentials and is displayed as a form in the integration configuration UI.

### Connector

A **Connector** handles the synchronization of a specific resource type within a Channel. For example, a CRM integration might have one Connector for contacts, another for deals. Connectors implement the actual sync logic (calling the external API, transforming data, persisting to Doctrine).

### Sync Process

The sync process runs as a Symfony console command, typically triggered by:
- A cron job (scheduled sync)
- A UI button (manual sync)
- A message queue consumer (async sync)

---

## Creating a Custom Integration: Step-by-Step

### Step 1: Define the Channel Type

The Channel Type class identifies your integration and links it to its transport and connectors.

```php
namespace Acme\Bundle\DemoBundle\Integration;

use Oro\Bundle\IntegrationBundle\Provider\ChannelInterface;
use Oro\Bundle\IntegrationBundle\Provider\IconAwareIntegrationInterface;

class AcmeChannelType implements ChannelInterface, IconAwareIntegrationInterface
{
    public const TYPE = 'acme_crm';

    // Human-readable name shown in the UI
    public function getLabel(): string
    {
        return 'Acme CRM';
    }

    // Icon shown next to integration name in the UI
    public function getIcon(): string
    {
        return 'bundles/acmedemo/img/acme-logo.png';
    }
}
```

Register as a service with the `oro_integration.channel` tag:

```yaml
# src/Acme/Bundle/DemoBundle/Resources/config/services.yml
services:
    acme_demo.integration.channel:
        class: Acme\Bundle\DemoBundle\Integration\AcmeChannelType
        tags:
            - { name: oro_integration.channel, type: acme_crm }
```

### Step 2: Define the Transport Entity

The Transport is a Doctrine entity that stores integration credentials.

```php
namespace Acme\Bundle\DemoBundle\Entity;

use Doctrine\ORM\Mapping as ORM;
use Oro\Bundle\IntegrationBundle\Entity\Transport;

#[ORM\Entity]
#[ORM\Table(name: 'acme_transport')]
class AcmeTransport extends Transport
{
    #[ORM\Column(name: 'api_key', type: 'string', length: 255, nullable: true)]
    private ?string $apiKey = null;

    #[ORM\Column(name: 'api_url', type: 'string', length: 512, nullable: true)]
    private ?string $apiUrl = null;

    public function getApiKey(): ?string
    {
        return $this->apiKey;
    }

    public function setApiKey(?string $apiKey): void
    {
        // Return a new instance to maintain immutability is not idiomatic for Doctrine entities,
        // but mutation is acceptable here since Doctrine manages lifecycle.
        $this->apiKey = $apiKey;
    }

    public function getApiUrl(): ?string
    {
        return $this->apiUrl;
    }

    public function setApiUrl(?string $apiUrl): void
    {
        $this->apiUrl = $apiUrl;
    }

    public function getSettingsBag(): \Symfony\Component\HttpFoundation\ParameterBag
    {
        return new \Symfony\Component\HttpFoundation\ParameterBag([
            'api_key' => $this->apiKey,
            'api_url' => $this->apiUrl,
        ]);
    }
}
```

### Step 3: Define the Transport Form Type

The form type renders the transport settings in the integration configuration UI:

```php
namespace Acme\Bundle\DemoBundle\Form\Type;

use Acme\Bundle\DemoBundle\Entity\AcmeTransport;
use Symfony\Component\Form\AbstractType;
use Symfony\Component\Form\Extension\Core\Type\TextType;
use Symfony\Component\Form\Extension\Core\Type\UrlType;
use Symfony\Component\Form\FormBuilderInterface;
use Symfony\Component\OptionsResolver\OptionsResolver;

class AcmeTransportSettingsType extends AbstractType
{
    public function buildForm(FormBuilderInterface $builder, array $options): void
    {
        $builder
            ->add('apiKey', TextType::class, [
                'label' => 'API Key',
                'required' => true,
                'attr' => ['placeholder' => 'Enter your Acme CRM API key'],
            ])
            ->add('apiUrl', UrlType::class, [
                'label' => 'API Endpoint URL',
                'required' => true,
            ]);
    }

    public function configureOptions(OptionsResolver $resolver): void
    {
        $resolver->setDefaults([
            'data_class' => AcmeTransport::class,
        ]);
    }
}
```

### Step 4: Implement the Transport Service

The transport service wraps the transport entity and provides the actual connection logic (HTTP client setup, authentication):

```php
namespace Acme\Bundle\DemoBundle\Integration;

use Acme\Bundle\DemoBundle\Entity\AcmeTransport as AcmeTransportEntity;
use Oro\Bundle\IntegrationBundle\Entity\Transport;
use Oro\Bundle\IntegrationBundle\Provider\TransportInterface;
use Symfony\Component\HttpFoundation\ParameterBag;

class AcmeTransport implements TransportInterface
{
    private ?ParameterBag $settings = null;

    // Called by the integration framework to initialize the transport
    // with the persisted settings from the database
    public function init(Transport $transportEntity): void
    {
        $this->settings = $transportEntity->getSettingsBag();
    }

    public function getSettingsFormType(): string
    {
        return AcmeTransportSettingsType::class;
    }

    public function getSettingsEntityFQCN(): string
    {
        return AcmeTransportEntity::class;
    }

    public function getLabel(): string
    {
        return 'Acme CRM Transport';
    }

    // Example: make an authenticated API call
    public function getContacts(int $page = 1): array
    {
        $apiKey = $this->settings->get('api_key');
        $apiUrl = $this->settings->get('api_url');

        // Make HTTP request to external API using $apiKey and $apiUrl
        // Return array of contact data
        return [];
    }
}
```

Register as a service:

```yaml
    acme_demo.integration.transport:
        class: Acme\Bundle\DemoBundle\Integration\AcmeTransport
        tags:
            - { name: oro_integration.transport, type: acme_crm, channel_type: acme_crm }
```

### Step 5: Implement the Connector

The connector handles synchronization of a specific resource type. It reads data from the external system via the transport and processes it.

```php
namespace Acme\Bundle\DemoBundle\Integration;

use Acme\Bundle\DemoBundle\Entity\Contact;
use Doctrine\ORM\EntityManagerInterface;
use Oro\Bundle\IntegrationBundle\Provider\AbstractConnector;

class AcmeContactConnector extends AbstractConnector
{
    public const TYPE = 'contact';

    private EntityManagerInterface $em;

    public function __construct(EntityManagerInterface $em)
    {
        $this->em = $em;
    }

    public function getLabel(): string
    {
        return 'Acme CRM Contacts';
    }

    // Returns the type identifier used in configuration
    public function getType(): string
    {
        return self::TYPE;
    }

    // Returns the import job name (uses the standard CSV import job by default)
    public function getImportJobName(): string
    {
        return 'acme_contact_import';
    }

    // Returns the import processor alias (must match service tag alias)
    public function getImportEntityFQCN(): string
    {
        return Contact::class;
    }

    // Called by the sync process — fetches data from external system
    protected function getConnectorSource(): \Iterator
    {
        /** @var AcmeTransport $transport */
        $transport = $this->getTransport();
        $contacts = $transport->getContacts();

        // Yield one record at a time to support large datasets
        // without loading everything into memory
        foreach ($contacts as $contactData) {
            yield $contactData;
        }
    }
}
```

Register as a service:

```yaml
    acme_demo.integration.connector.contact:
        class: Acme\Bundle\DemoBundle\Integration\AcmeContactConnector
        arguments:
            - '@doctrine.orm.entity_manager'
        tags:
            - { name: oro_integration.connector, type: contact, channel_type: acme_crm }
```

**Connector tag attributes:**

| Attribute | Required | Description |
|---|---|---|
| `name` | yes | Always `oro_integration.connector` |
| `type` | yes | Connector type identifier (unique within channel type) |
| `channel_type` | yes | Must match the Channel type identifier |

---

## Running Synchronization

### Manual Sync via CLI

```bash
# Sync all connectors for a specific integration channel (by ID)
php bin/console oro:integration:sync --id=1

# Sync a specific connector only
php bin/console oro:integration:sync --id=1 --connector=contact

# Run in production environment
php bin/console oro:integration:sync --id=1 --env=prod
```

### Scheduled Sync via Cron

Register a cron job that calls the sync command:

```yaml
# Resources/config/oro/cron_jobs.yml
oro_cron:
    acme_crm_sync:
        command: oro:integration:sync
        schedule: '0 */6 * * *'   # Every 6 hours
        arguments:
            id: 1
```

Or implement a custom cron command:

```php
namespace Acme\Bundle\DemoBundle\Command;

use Oro\Bundle\CronBundle\Command\CronCommandScheduleDefinitionInterface;
use Oro\Bundle\IntegrationBundle\Command\SyncCommand;
use Symfony\Component\Console\Command\Command;
use Symfony\Component\Console\Input\InputInterface;
use Symfony\Component\Console\Output\OutputInterface;

class AcmeSyncCronCommand extends Command implements CronCommandScheduleDefinitionInterface
{
    protected static $defaultName = 'oro:cron:acme:sync';

    public function getDefaultDefinition(): string
    {
        // Run every 6 hours
        return '0 */6 * * *';
    }

    protected function execute(InputInterface $input, OutputInterface $output): int
    {
        // Delegate to the standard integration sync command or implement custom logic
        return Command::SUCCESS;
    }
}
```

---

## Reverse Synchronization

Reverse synchronization pushes changes made in OroCommerce back to the external system. This is typically triggered by Doctrine events (entity lifecycle callbacks).

### Pattern: Doctrine Event Listener

```php
namespace Acme\Bundle\DemoBundle\EventListener;

use Acme\Bundle\DemoBundle\Entity\Contact;
use Acme\Bundle\DemoBundle\Integration\AcmeTransport;
use Doctrine\ORM\Event\PostUpdateEventArgs;
use Oro\Bundle\IntegrationBundle\Entity\Repository\ChannelRepository;

class ContactChangeListener
{
    private AcmeTransport $transport;
    private ChannelRepository $channelRepository;

    public function __construct(AcmeTransport $transport, ChannelRepository $channelRepository)
    {
        $this->transport = $transport;
        $this->channelRepository = $channelRepository;
    }

    // Fires after a Contact entity is updated in the database
    public function postUpdate(PostUpdateEventArgs $event): void
    {
        $entity = $event->getObject();
        if (!$entity instanceof Contact) {
            return;
        }

        // Find the active integration channel
        $channel = $this->channelRepository->findOneBy([
            'type' => 'acme_crm',
            'enabled' => true,
        ]);

        if ($channel === null) {
            return;
        }

        // Push the update to the external system
        $this->transport->init($channel->getTransport());
        $this->transport->updateContact($entity);
    }
}
```

Register as a Doctrine event listener:

```yaml
    acme_demo.event_listener.contact_change:
        class: Acme\Bundle\DemoBundle\EventListener\ContactChangeListener
        arguments:
            - '@acme_demo.integration.transport'
            - '@oro_integration.repository.channel'
        tags:
            - { name: doctrine.event_listener, event: postUpdate }
```

### Pattern: Message Queue (Recommended for Performance)

For large-scale or latency-sensitive reverse sync, use the message queue instead of synchronous listeners:

```php
// In your event listener, instead of calling the API directly:
public function postUpdate(PostUpdateEventArgs $event): void
{
    $entity = $event->getObject();
    if (!$entity instanceof Contact) {
        return;
    }

    // Dispatch a message instead of making a synchronous API call
    $this->messageProducer->send(
        AcmeSyncTopic::getName(),
        ['entity_id' => $entity->getId(), 'operation' => 'update']
    );
}
```

---

## Integration Configuration: Service Tag Reference

### Channel Type Tag

```yaml
tags:
    - { name: oro_integration.channel, type: '<unique_type_id>' }
```

### Transport Tag

```yaml
tags:
    - { name: oro_integration.transport, type: '<unique_type_id>', channel_type: '<channel_type_id>' }
```

### Connector Tag

```yaml
tags:
    - { name: oro_integration.connector, type: '<connector_type_id>', channel_type: '<channel_type_id>' }
```

---

## Integration vs Import/Export: Decision Guide

| Requirement | Use OroIntegrationBundle | Use Import/Export |
|---|---|---|
| Real-time or near-real-time sync | Yes | No |
| UI-managed credentials (API keys, OAuth) | Yes | No |
| Bidirectional data flow | Yes | Limited |
| Payment or shipping methods | Yes (required) | No |
| Simple periodic batch load | Overkill | Yes |
| Non-Oro developer maintenance | Complex | Easier |
| File-based data exchange | Not designed for | Yes |
| Large one-time data loads | Possible | Recommended |

---

## Complete Implementation Checklist

To create a new integration:

- [ ] Create Channel Type class implementing `ChannelInterface`
- [ ] Register Channel Type with `oro_integration.channel` tag
- [ ] Create Transport entity extending `Oro\Bundle\IntegrationBundle\Entity\Transport`
- [ ] Create Transport form type for admin UI settings
- [ ] Create Transport service implementing `TransportInterface`
- [ ] Register Transport service with `oro_integration.transport` tag
- [ ] Create Connector class extending `AbstractConnector`
- [ ] Implement `getConnectorSource()` to yield data from external API
- [ ] Register Connector with `oro_integration.connector` tag
- [ ] Run `php bin/console oro:platform:update --force` for DB schema
- [ ] Configure the integration via admin UI: System > Integrations > Create
- [ ] Set up cron or manual trigger for sync command
- [ ] (Optional) Implement reverse sync via Doctrine listeners or MQ
