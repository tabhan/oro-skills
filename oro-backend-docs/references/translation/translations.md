# OroCommerce Translations & Localization — Agent Knowledge Base

> Source: https://doc.oroinc.com/master/backend/translations/

## AGENT QUERY HINTS

Use this file when asked about:
- "How do I add a translation?" / "How do I translate a string?"
- "What is the translation file structure in Oro?"
- "How do I use the translator service in PHP?"
- "How do I translate strings in Twig templates?"
- "How do I add frontend/JS translations?"
- "What is JsTranslation / jsmessages?"
- "How do I create translations in data fixtures?"
- "What translation domains does Oro use?"
- "What is the difference between translation and localization in Oro?"
- "How do I format dates/numbers/names/addresses by locale?"
- "How do I use LocalizedFallbackValue?"
- "How does locale fallback work in Oro?"
- "How do I add a new language/localization?"
- "What are validators.en.yml or messages.en.yml?"
- "How do I configure translation debug mode?"

---

## Overview

OroCommerce (built on OroPlatform + Symfony) handles internationalization through two complementary systems:

1. **Translation** — Converting UI text strings (labels, messages, button text) from one language to another using Symfony's translator component and Oro's YAML-based translation files.
2. **Localization** — Adapting the *presentation* of data (dates, numbers, currency, addresses, names) to regional conventions. Localization also manages *locale-specific content* stored in the database (e.g., product names in different languages).

**WHY two systems?** Translation covers static UI strings. Localization covers both dynamic formatting and database-stored content that can vary per region. A product name "Produto" (pt_BR) vs "Product" (en_US) is a localization concern, not a translation concern.

---

## Part 1: Translation System

### 1.1 Translation File Structure

Translation files live inside each bundle at:
```
src/MyBundle/Resources/translations/
```

Symfony discovers files named with this pattern:
```
{domain}.{locale}.yml
```

#### Standard Domains and Their Files

| File | Domain | Purpose |
|------|--------|---------|
| `messages.en.yml` | `messages` | Default domain — general UI labels and messages |
| `jsmessages.en.yml` | `jsmessages` | Strings exposed to frontend JavaScript |
| `validators.en.yml` | `validators` | Form validation error messages |
| `entities.en.yml` | `entities` | Entity and field labels used in UI |
| `security.en.yml` | `security` | Security-related messages |

**WHY separate domains?** Domains scope translation keys, preventing collisions between bundles, and allow loading only the needed subset (e.g., only `jsmessages` on the frontend).

#### Example File Layout in a Custom Bundle

```
src/Bridge/Bundle/BridgeThemeBundle/
└── Resources/
    └── translations/
        ├── messages.en.yml       # English UI strings
        ├── messages.pt_BR.yml    # Brazilian Portuguese UI strings
        ├── jsmessages.en.yml     # JS-exposed strings
        ├── validators.en.yml     # Validation messages
        └── entities.en.yml      # Entity labels
```

---

### 1.2 Translation Key Naming Conventions

Oro uses dot-separated hierarchical keys:

```
{bundle_or_feature}.{category}.{element}
```

**WHY hierarchical keys?** They group related strings, prevent naming collisions between bundles, and make the translation UI easier to browse.

#### Good Examples

```yaml
# messages.en.yml
bridge.order.status.pending: Pending
bridge.order.status.shipped: Shipped
bridge.order.action.cancel: Cancel Order
bridge.product.label.price: Price
bridge.dashboard.title: My Dashboard

# validators.en.yml
bridge.product.validation.name_required: Product name is required.
bridge.product.validation.price_positive: Price must be greater than zero.

# entities.en.yml
bridge.entity.division.label: Division
bridge.entity.division.plural_label: Divisions
bridge.entity.division.description: Represents a business division
```

#### Naming Rules

- Use all lowercase with dots as separators
- Start with a bundle/feature prefix (e.g., `bridge`, `aaxis`)
- Use snake_case within each segment if multiple words are needed (e.g., `ship_mode`)
- Keep keys descriptive and stable — changing a key breaks all existing translations
- Do NOT use generic keys like `label`, `title` without a prefix

---

### 1.3 Adding Translatable Strings in YAML Files

#### messages.en.yml — General Messages

```yaml
# src/Bridge/Bundle/BridgeThemeBundle/Resources/translations/messages.en.yml

# Simple string
bridge.customer.greeting: Welcome, %name%!

# With placeholder
bridge.order.placed_on: Order placed on %date%

# Pluralization (Symfony ICU)
bridge.cart.items: >-
    {count, plural,
        one {# item in cart}
        other {# items in cart}
    }

# Longer label
bridge.integration.sap.sync_running: SAP synchronization is currently running. Please wait.
```

#### Providing a Portuguese Translation

```yaml
# src/Bridge/Bundle/BridgeThemeBundle/Resources/translations/messages.pt_BR.yml

bridge.customer.greeting: Bem-vindo, %name%!
bridge.order.placed_on: Pedido realizado em %date%
bridge.cart.items: >-
    {count, plural,
        one {# item no carrinho}
        other {# itens no carrinho}
    }
bridge.integration.sap.sync_running: A sincronização SAP está em execução. Por favor, aguarde.
```

#### validators.en.yml — Form Validation Errors

```yaml
# src/Bridge/Bundle/BridgeThemeBundle/Resources/translations/validators.en.yml

bridge.division.name.not_blank: Division name cannot be empty.
bridge.division.code.invalid: Division code must contain only letters and numbers.
bridge.ship_mode.weight.max_exceeded: "Weight cannot exceed %limit% kg."
```

#### entities.en.yml — Entity Labels

```yaml
# Entity labels are consumed by Oro's grid/form infrastructure.
# The keys follow a strict Oro convention.

bridge.entity.division.label: Division
bridge.entity.division.plural_label: Divisions
bridge.entity.division.description: A business division grouping customers

bridge.entity.ship_mode.label: Ship Mode
bridge.entity.ship_mode.plural_label: Ship Modes
```

---

### 1.4 Using the Translator Service in PHP

The translator is a standard Symfony service. In Oro it is available as `translator`.

#### Dependency Injection (Recommended)

```php
<?php

declare(strict_types=1);

namespace Bridge\Bundle\BridgeThemeBundle\Controller;

use Symfony\Contracts\Translation\TranslatorInterface;

class OrderController
{
    public function __construct(
        private readonly TranslatorInterface $translator,
    ) {
    }

    public function someAction(): void
    {
        // Basic translation (messages domain, current locale)
        $label = $this->translator->trans('bridge.order.status.pending');

        // With parameters
        $greeting = $this->translator->trans(
            'bridge.customer.greeting',
            ['%name%' => $customer->getFullName()]
        );

        // Explicit domain
        $error = $this->translator->trans(
            'bridge.division.name.not_blank',
            [],
            'validators'
        );

        // Explicit locale override
        $ptLabel = $this->translator->trans(
            'bridge.order.status.pending',
            [],
            'messages',
            'pt_BR'
        );
    }
}
```

#### In Symfony Services (service.yml wiring)

```yaml
# Resources/config/services.yml
services:
    bridge.theme.order_mailer:
        class: Bridge\Bundle\BridgeThemeBundle\Service\OrderMailer
        arguments:
            - '@translator'
```

#### In Legacy Container-Aware Code

```php
// Only when extending ContainerAware — prefer constructor injection instead
$label = $this->container->get('translator')->trans('bridge.order.status.pending');
```

#### Pluralization in PHP

```php
// Using the ICU message format (Symfony 5+)
$message = $this->translator->trans(
    'bridge.cart.items',
    ['%count%' => 3]
);

// Legacy transChoice (deprecated, avoid in new code)
// $message = $this->translator->transChoice('bridge.cart.items', 3);
```

---

### 1.5 Using Translations in Twig Templates

```twig
{# Basic translation — uses 'messages' domain by default #}
{{ 'bridge.order.status.pending'|trans }}

{# With parameters #}
{{ 'bridge.customer.greeting'|trans({'%name%': user.fullName}) }}

{# Explicit domain #}
{{ 'bridge.division.name.not_blank'|trans({}, 'validators') }}

{# Explicit locale #}
{{ 'bridge.order.status.pending'|trans({}, 'messages', 'pt_BR') }}

{# Using the trans tag (multi-line) #}
{% trans with {'%name%': user.fullName} %}bridge.customer.greeting{% endtrans %}

{# Count-based pluralization (Symfony ICU format) #}
{{ 'bridge.cart.items'|trans({'%count%': cart.itemCount}) }}
```

**WHY use keys instead of raw strings in Twig?** Using translation keys ensures strings can be translated without modifying templates. Hardcoded English text in Twig cannot be translated.

---

### 1.6 Translations in YAML Configuration Files

Many Oro config files (datagrids, navigation, workflows) accept translation keys directly — Oro resolves them at render time.

#### Datagrid Configuration

```yaml
# Resources/config/oro/datagrids.yml
datagrids:
    bridge-division-grid:
        columns:
            name:
                label: bridge.entity.division.label    # Translation key, not raw text
            code:
                label: bridge.division.grid.column.code
        filters:
            columns:
                name:
                    label: bridge.entity.division.label
        actions:
            edit:
                label: oro.grid.action.edit            # Oro built-in key
            delete:
                label: oro.grid.action.delete
```

#### Navigation Configuration

```yaml
# Resources/config/oro/navigation.yml
menu_config:
    items:
        bridge_division_list:
            label: bridge.menu.division.list           # Translation key
            route: bridge_division_index
        bridge_ship_mode_list:
            label: bridge.menu.ship_mode.list
            route: bridge_ship_mode_index
```

#### Form Type Labels

```php
<?php

use Symfony\Component\Form\AbstractType;
use Symfony\Component\Form\Extension\Core\Type\TextType;
use Symfony\Component\Form\FormBuilderInterface;

class DivisionType extends AbstractType
{
    public function buildForm(FormBuilderInterface $builder, array $options): void
    {
        $builder
            ->add('name', TextType::class, [
                'label' => 'bridge.entity.division.label',  // Translation key
            ])
            ->add('code', TextType::class, [
                'label' => 'bridge.division.form.code',
            ]);
    }
}
```

---

### 1.7 JsTranslation — Frontend Translation Strings

Oro uses a custom `jsmessages` domain to expose translations to JavaScript. These strings are pre-compiled and served as JavaScript modules.

**WHY a separate domain?** Not all backend strings should be sent to the browser. The `jsmessages` domain acts as an explicit whitelist of strings needed on the frontend.

#### Defining JS-Exposed Translations

```yaml
# src/Bridge/Bundle/BridgeThemeBundle/Resources/translations/jsmessages.en.yml

bridge.js.confirm.delete: Are you sure you want to delete this item?
bridge.js.loading: Loading...
bridge.js.error.generic: An error occurred. Please try again.
bridge.js.cart.add_success: Item added to cart.
bridge.js.filter.no_results: No results found.
```

```yaml
# src/Bridge/Bundle/BridgeThemeBundle/Resources/translations/jsmessages.pt_BR.yml

bridge.js.confirm.delete: Tem certeza que deseja excluir este item?
bridge.js.loading: Carregando...
bridge.js.error.generic: Ocorreu um erro. Por favor, tente novamente.
bridge.js.cart.add_success: Item adicionado ao carrinho.
bridge.js.filter.no_results: Nenhum resultado encontrado.
```

#### Using Translations in JavaScript / RequireJS Modules

Oro provides the `orotranslation/js/translator` module (AMD/RequireJS):

```javascript
// Using AMD require (Oro's legacy JS approach)
define(function(require) {
    'use strict';

    var __ = require('orotranslation/js/translator');

    // Basic translation
    var label = __('bridge.js.confirm.delete');

    // With parameters (uses sprintf-style substitution)
    var message = __('bridge.customer.greeting', { name: 'Alice' });

    return {
        confirm: function() {
            return confirm(label);
        }
    };
});
```

```javascript
// Using ES modules (modern Oro JS)
import __ from 'orotranslation/js/translator';

const label = __('bridge.js.confirm.delete');
const greeting = __('bridge.customer.greeting', { name: customerName });
```

#### Building JS Translations

After adding or modifying `jsmessages.*.yml`, rebuild the JS translation assets:

```bash
# Dump JS translations (compiles jsmessages domain to JS files)
php bin/console oro:translation:dump

# Or rebuild all assets
php bin/console oro:assets:build
```

**WHY run dump?** The JS translator does not read YAML at runtime — it reads pre-compiled JSON/JS files generated by `oro:translation:dump`. Skipping this step means frontend strings will not update.

---

### 1.8 Translation Domains in Oro

| Domain | File Pattern | Used By |
|--------|-------------|---------|
| `messages` | `messages.{locale}.yml` | General UI text — default domain |
| `jsmessages` | `jsmessages.{locale}.yml` | Frontend JavaScript code |
| `validators` | `validators.{locale}.yml` | Symfony form validation |
| `entities` | `entities.{locale}.yml` | Entity/field labels in UI grids and forms |
| `security` | `security.{locale}.yml` | Auth and access control messages |
| `workflows` | `workflows.{locale}.yml` | Workflow step/transition labels |
| `email` | `email.{locale}.yml` | Email template subject/body fragments |

**WHY use the `entities` domain?** Oro's entity management (grids, filters, field labels in reports) automatically looks up labels from the `entities` domain. If an entity field label is in `messages`, the entity management UI may not find it.

---

### 1.9 Translation Debug Configuration

To debug translator behavior, Oro provides configuration flags (set per environment, typically in `config/config_dev.yml` or environment variables):

```yaml
# config/packages/translation.yaml (Symfony config)
framework:
    translator:
        fallbacks: ['en']   # Fallback locale chain
        logging: true       # Log missing translations (dev only)

# Oro-specific debug config
oro_translation:
    debug_translator: true   # Enable translator debug mode
```

```yaml
# To debug JS translations specifically
oro_translation:
    js_translation:
        debug_translator: true   # Enable JS translation debug mode
        domains:                 # Explicitly list domains to compile
            - jsmessages
            - messages
```

**WHY debug mode?** In debug mode, missing translation keys are logged (and sometimes highlighted visually), making it easy to catch untranslated strings during development.

---

### 1.10 Translation Strategies and Locale Fallback

Oro uses a `TranslationStrategyProvider` with pluggable `TranslationStrategyInterface` implementations to control locale fallback behavior.

**DefaultTranslationStrategy** — Falls back through a single locale chain. If `pt_BR` is missing, it falls back to `pt`, then to `en`.

```
pt_BR → pt → en
```

Custom strategies can be registered:

```yaml
# services.yml
services:
    acme.translation.custom_strategy:
        class: Acme\Bundle\DemoBundle\Translation\CustomTranslationStrategy
        tags:
            - { name: oro_translation.extension.translation_strategy }
```

---

### 1.11 Translation Context Resolver

Oro provides a `TranslationContextResolverInterface` to humanize raw translation keys in the translation management UI, giving translators meaningful context.

```yaml
# services.yml
services:
    bridge.translation.context_resolver:
        class: Bridge\Bundle\BridgeThemeBundle\Translation\BridgeTranslationContextResolver
        arguments:
            - '@translator'
        tags:
            - { name: oro_translation.extension.translation_context_resolver, priority: -100 }
```

```php
<?php

namespace Bridge\Bundle\BridgeThemeBundle\Translation;

use Oro\Bundle\TranslationBundle\Extension\TranslationContextResolverInterface;

class BridgeTranslationContextResolver implements TranslationContextResolverInterface
{
    public function resolve(string $id): ?string
    {
        // Return human-readable context for keys starting with 'bridge.'
        if (str_starts_with($id, 'bridge.')) {
            return 'Bridge Commerce Portal';
        }
        return null;
    }
}
```

---

## Part 2: Data Fixtures for Translations

When loading demo/initial data via Doctrine data fixtures, Oro provides a base class to apply translations within fixtures.

### 2.1 AbstractTranslatableEntityFixture

**Class:** `Oro\Bundle\TranslationBundle\DataFixtures\AbstractTranslatableEntityFixture`

This base class:
1. Scans translation files matching the configured domain (default: `entities`)
2. Identifies all available locales
3. Provides a `translate()` helper for use in `loadEntities()`

**WHY use this?** Without it, fixtures would hardcode English strings. Using the abstract class, fixtures automatically create translated entities for all locales where translation files exist.

#### Key Constants and Methods

| Member | Type | Description |
|--------|------|-------------|
| `ENTITY_DOMAIN` | constant | Domain to scan (default: `"entities"`) |
| `DOMAIN_FILE_REGEXP` | constant | Regex for matching translation files |
| `load()` | method | Entrypoint — do not override, calls `loadEntities()` |
| `loadEntities()` | abstract | Override this to create your entities |
| `getTranslationLocales()` | method | Returns all locales with matching translation files |
| `translate($id, $prefix, $locale)` | method | Returns translated string for given key, prefix, locale |
| `getTranslationId($entityId, $prefix)` | method | Builds a translation key from entity ID and prefix |

#### Implementation Example

```php
<?php

declare(strict_types=1);

namespace Bridge\Bundle\BridgeEntityBundle\DataFixtures\ORM;

use Bridge\Bundle\BridgeEntityBundle\Entity\Division;
use Doctrine\Persistence\ObjectManager;
use Oro\Bundle\TranslationBundle\DataFixtures\AbstractTranslatableEntityFixture;

/**
 * Loads Division entities with translations for all available locales.
 */
class LoadDivisionData extends AbstractTranslatableEntityFixture
{
    // Override domain if entity labels are in a custom domain
    protected const ENTITY_DOMAIN = 'entities';

    // Division codes to seed
    private const DIVISIONS = ['north', 'south', 'east', 'west'];

    protected function loadEntities(ObjectManager $manager): void
    {
        $divisionRepository = $manager->getRepository(Division::class);

        foreach (self::DIVISIONS as $divisionCode) {
            $division = $divisionRepository->findOneBy(['code' => $divisionCode])
                ?? new Division();

            $division->setCode($divisionCode);

            // Set the default (English) name
            $division->setName(
                $this->translate($divisionCode, 'bridge.division', 'en')
            );

            // Apply translations for all available locales
            foreach ($this->getTranslationLocales() as $locale) {
                $translatedName = $this->translate($divisionCode, 'bridge.division', $locale);
                // Store locale-specific value if your entity supports it
                // (e.g., via LocalizedFallbackValue or a translation table)
                $division->setTranslatedName($locale, $translatedName);
            }

            $manager->persist($division);
        }

        $manager->flush();
    }
}
```

#### Corresponding Translation File

The fixture scans `entities.{locale}.yml` for keys matching:
```
bridge.division.{division_code}
```

```yaml
# Resources/translations/entities.en.yml
bridge.division.north: North Region
bridge.division.south: South Region
bridge.division.east: East Region
bridge.division.west: West Region
```

```yaml
# Resources/translations/entities.pt_BR.yml
bridge.division.north: Região Norte
bridge.division.south: Região Sul
bridge.division.east: Região Leste
bridge.division.west: Região Oeste
```

---

## Part 3: Localization System

### 3.1 Localization vs Translation — Key Distinction

| Aspect | Translation | Localization |
|--------|-------------|-------------|
| What it handles | UI string text in different languages | Data formatting + locale-specific content |
| Storage | YAML files in bundle | Database (Localization entities) + config YAML |
| Example | "Add to Cart" → "Adicionar ao Carrinho" | Product name "Widget" (en) vs "Widget" (pt_BR) |
| Mechanism | Symfony translator + translation files | LocalizedFallbackValue entity + LocalizationManager |
| Config | Translation domain YAML files | `locale_data.yml`, `name_format.yml`, `address_format.yml` |

**WHY this distinction matters for agents:** When a developer asks "how do I show a product name in Portuguese," that is a *localization* question (LocalizedFallbackValue). When they ask "how do I translate the 'Add to Cart' button," that is a *translation* question (messages.pt_BR.yml).

---

### 3.2 System Configuration

Access via: **System > Configuration > General Setup > Localization**

| Setting | Purpose |
|---------|---------|
| Primary Location | Country for default address format and currency |
| Format Address per country | Apply country-specific address rules |
| Timezone | Renders all time/datetime values |
| First Quarter Starts on | Correct quarterly reports |
| Temperature Unit | Location map display |
| Wind Speed Unit | Location map display |
| Default Localization | Language for back-office and storefront UI |
| Enabled Localizations | Which localizations are active (auto-generated) |

---

### 3.3 Localization Configuration Files

Each bundle places these files in `Resources/config/oro/`:

#### locale_data.yml

Defines country-level data (ISO 3166 codes):

```yaml
# Resources/config/oro/locale_data.yml
US:
    currency_code: USD
    phone_prefix: '1'
    default_locale: en_US
BR:
    currency_code: BRL
    phone_prefix: '55'
    default_locale: pt_BR
MX:
    currency_code: MXN
    phone_prefix: '52'
    default_locale: es_MX
DE:
    currency_code: EUR
    phone_prefix: '49'
    default_locale: de_DE
```

#### name_format.yml

Locale-specific person name format strings:

```yaml
# Resources/config/oro/name_format.yml

# Placeholders: %prefix%, %first_name%, %middle_name%, %last_name%, %suffix%
# UPPERCASE placeholder → uppercases the value

en_US: "%prefix% %first_name% %middle_name% %last_name% %suffix%"
pt_BR: "%first_name% %last_name%"
ja_JP: "%last_name% %first_name%"
ru_RU: "%last_name% %first_name% %middle_name%"
zh_CN: "%last_name%%first_name%"
```

#### address_format.yml

Country-specific address layout:

```yaml
# Resources/config/oro/address_format.yml

# Placeholders: name, organization, street, street2, city, postal_code,
#               region, region_code, country, country_iso2, country_iso3
# UPPERCASE placeholder → uppercases the value

US:
    format: "%name%\n%organization%\n%street%\n%CITY% %REGION_CODE% %country_iso2% %postal_code%"
BR:
    format: "%name%\n%organization%\n%street%\n%city% - %REGION_CODE%\n%postal_code%\n%country%"
DE:
    format: "%name%\n%organization%\n%street%\n%postal_code% %CITY%\n%country%"
JP:
    format: "〒%postal_code%\n%region%%city%%street%\n%organization%\n%name%"
```

**WHY configure these per-country?** Different countries have different postal conventions. Without country-specific formats, addresses look wrong to local users and may fail postal delivery.

---

### 3.4 LocalizedFallbackValue — Locale-Specific Database Content

`LocalizedFallbackValue` is Oro's entity for storing content in multiple localizations in the database. Use it when the *value itself* (not just its display format) differs per locale.

**Common use cases:**
- Product names and descriptions per locale
- Category names per locale
- CMS page content per locale
- Email template content per locale

#### How It Works

An entity (e.g., `Product`) has a collection relationship to `LocalizedFallbackValue` entities. Each entry in the collection belongs to a specific `Localization` (or null for the default/fallback value).

```
Product
 └── names (Collection<LocalizedFallbackValue>)
      ├── [localization=null]    string="Widget"         # Default (English)
      ├── [localization=pt_BR]   string="Widget"         # Portuguese (same)
      └── [localization=es_MX]   string="Componente"     # Spanish (different)
```

#### Reading Localized Values in Twig

```twig
{# Renders the value for the current localization, with fallback #}
{{ product.names|localized_value }}

{# Explicit localization object #}
{{ localization.titles|localized_value }}
```

#### Reading Localized Values in PHP

```php
use Oro\Bundle\LocaleBundle\Helper\LocalizationHelper;

// Inject LocalizationHelper via constructor
$localizedName = $this->localizationHelper->getLocalizedValue(
    $product->getNames()
);
```

#### Reading Localized Values in Layout YAML

```yaml
# In a layout update YAML
'=data["locale"].getLocalizedValue(data["product"].getNames())'
```

#### Reading Localized Values in Datagrids

```yaml
# datagrids.yml
datagrids:
    my-product-grid:
        properties:
            title:
                type: localized_value    # Special property type
                data_name: names         # Collection property on entity
        columns:
            title:
                label: oro.product.names.label
        sorters:
            columns:
                title:
                    data_name: names     # Joins the appropriate locale
        filters:
            columns:
                title:
                    type: string
                    data_name: names
```

**NOTE on datagrids:** "If the current localization is not detected, SQL relation will be joined to the default fallback values."

---

### 3.5 LocalizationManager — Managing Localization Objects

**Service ID:** `oro_locale.manager.localization`

**Class:** `Oro\Bundle\LocaleBundle\Manager\LocalizationManager`

**IMPORTANT:** Localization objects are cached. Disable cache when persisting/deleting localizations.

```php
<?php

use Oro\Bundle\LocaleBundle\Manager\LocalizationManager;

class MyService
{
    public function __construct(
        private readonly LocalizationManager $localizationManager,
    ) {
    }

    public function getLocalization(int $id): mixed
    {
        // Get by ID (uses cache by default)
        return $this->localizationManager->getLocalization($id);
    }

    public function getAllLocalizations(): array
    {
        // Get all localizations
        return $this->localizationManager->getLocalizations();
    }

    public function getSomeLocalizations(): array
    {
        // Get specific localizations by IDs
        return $this->localizationManager->getLocalizations([1, 3, 5]);
    }

    public function getDefault(): mixed
    {
        // Get default localization from system config
        return $this->localizationManager->getDefaultLocalization();
    }

    public function saveLocalization(mixed $localization): void
    {
        // When persisting, DISABLE cache to avoid stale data
        $this->localizationManager->getLocalization(
            $localization->getId(),
            false   // $useCache = false
        );
    }
}
```

#### Cache Management

```php
// Clear localization cache (call after persisting changes)
$this->localizationManager->clearCache();

// Pre-warm the cache (load all from DB into cache)
$this->localizationManager->warmUpCache();
```

---

### 3.6 Current Localization Detection

**Class:** `Oro\Bundle\LocaleBundle\Helper\LocalizationHelper`
**Method:** `getCurrentLocalization()`
**Service:** `oro_locale.helper.localization`

```php
<?php

use Oro\Bundle\LocaleBundle\Helper\LocalizationHelper;

class MyService
{
    public function __construct(
        private readonly LocalizationHelper $localizationHelper,
    ) {
    }

    public function getCurrentLocale(): mixed
    {
        return $this->localizationHelper->getCurrentLocalization();
    }
}
```

#### Custom Localization Extension

Provide custom logic for detecting the current localization (e.g., based on subdomain or customer group):

```php
<?php

namespace Acme\Bundle\DemoBundle\Extension;

use Oro\Bundle\LocaleBundle\Entity\Localization;
use Oro\Bundle\LocaleBundle\Extension\CurrentLocalizationExtensionInterface;

class CurrentLocalizationExtension implements CurrentLocalizationExtensionInterface
{
    public function getCurrentLocalization(): ?Localization
    {
        // Custom logic — e.g., detect from request subdomain
        // Return null to defer to the next extension in the chain
        return null;
    }
}
```

```yaml
# services.yml
services:
    acme_demo.extension.current_localization:
        class: Acme\Bundle\DemoBundle\Extension\CurrentLocalizationExtension
        tags:
            - { name: oro_locale.extension.current_localization }
```

---

## Part 4: Formatting Services

### 4.1 Date and Datetime Formatting

**Class:** `Oro\Bundle\LocaleBundle\Formatter\DateTimeFormatter`

#### PHP Usage

```php
$formatter = $container->get('oro_locale.formatter.datetime');

// Format date only
$formatted = $formatter->formatDate(new \DateTime('2024-01-15'));
// outputs: "Jan 15, 2024" (en_US)

// Format time only
$formatted = $formatter->formatTime(new \DateTime('2024-01-15 14:30:00'));
// outputs: "2:30 PM"

// Format full datetime
$formatted = $formatter->format(new \DateTime('2024-01-15 14:30:00'));
// outputs: "Jan 15, 2024, 2:30 PM"
```

#### Twig Filters

```twig
{{ order.createdAt|oro_format_date }}
{{ order.createdAt|oro_format_datetime }}
{{ order.shippedAt|oro_format_date({'locale': 'pt_BR'}) }}
```

#### JavaScript Module

```javascript
import datetimeFormatter from 'orolocale/js/formatter/datetime';

datetimeFormatter.formatDate('2024-01-15');
datetimeFormatter.formatDateTime('2024-01-15T14:30:00Z');
```

---

### 4.2 Number Formatting

**Class:** `Oro\Bundle\LocaleBundle\Formatter\NumberFormatter`

Uses PHP's `intl` extension (`NumberFormatter` class internally).

#### PHP Usage

```php
$formatter = $container->get('oro_locale.formatter.number');

// Decimal
$formatter->formatDecimal(1234.56);        // "1,234.56" (en_US)

// Currency
$formatter->formatCurrency(1234.56, 'BRL', [], [], [], 'pt_BR');
// outputs: "R$ 1.234,56"

// Percentage
$formatter->formatPercent(0.1567);         // "15.67%"

// Ordinal
$formatter->formatOrdinal(3);              // "3rd"

// Spellout
$formatter->formatSpellout(42);            // "forty-two"
```

#### Twig Filters

```twig
{{ product.price|oro_format_currency }}
{{ product.price|oro_format_currency({'currency': 'BRL'}) }}
{{ ratio|oro_format_percent }}
{{ amount|oro_format_decimal }}
{{ count|oro_format_number('decimal') }}
```

#### JavaScript Module

```javascript
import numberFormatter from 'orolocale/js/formatter/number';

numberFormatter.formatCurrency(-50000.45);   // "($50,000.45)" in USD
numberFormatter.formatDecimal(1234.56);      // "1,234.56"
numberFormatter.formatPercent(0.15);         // "15%"
numberFormatter.unformat('$50,000.45');      // 50000.45 (parse back)
```

---

### 4.3 Name Formatting

**Service:** `oro_locale.formatter.name`
**Class:** `Oro\Bundle\LocaleBundle\Formatter\NameFormatter`

#### Entity Requirements

Your entity must implement `Oro\Bundle\LocaleBundle\Model\FullNameInterface` (or individual interfaces):
- `FirstNameInterface` — `getFirstName()`
- `MiddleNameInterface` — `getMiddleName()`
- `LastNameInterface` — `getLastName()`
- `NamePrefixInterface` — `getNamePrefix()`
- `NameSuffixInterface` — `getNameSuffix()`

#### PHP Usage

```php
$formatter = $container->get('oro_locale.formatter.name');

// Format using system locale
$formatted = $formatter->format($person);

// Format using explicit locale
$formatted = $formatter->format($person, 'ja_JP');
// For Japanese: "山田 太郎" (last_name first_name)
```

#### Twig Filter

```twig
{{ user|oro_format_name }}
{{ customer|oro_format_name({'locale': 'pt_BR'}) }}
```

#### JavaScript Module

```javascript
import nameFormatter from 'orolocale/js/formatter/name';

nameFormatter.format({
    prefix: 'Mr.',
    first_name: 'John',
    middle_name: 'K.',
    last_name: 'Smith',
    suffix: 'Jr.'
}, 'en_US');
// "Mr. John K. Smith Jr."
```

---

### 4.4 Address Formatting

**Service:** `oro_locale.formatter.address`
**Class:** `Oro\Bundle\LocaleBundle\Formatter\AddressFormatter`

#### Entity Requirements

Address entity must implement `Oro\Bundle\LocaleBundle\Model\AddressInterface`.

#### PHP Usage

```php
$formatter = $container->get('oro_locale.formatter.address');

// Format with country-specific format, newline separator
$formatted = $formatter->format($address, 'US', "\n");

// Output for US:
// Mr. Roy K Greenwell
// Products Inc.
// 2413 Capitol Avenue
// ROMNEY IN US 47981

// Get format string for a country
$formatString = $formatter->getAddressFormat('BR');
```

#### Twig Filters

```twig
{# Plain text with newlines #}
{{ address|oro_format_address }}

{# HTML with CSS classes for granular styling #}
{{ address|oro_format_address_html }}
```

#### JavaScript Module

```javascript
import addressFormatter from 'orolocale/js/formatter/address';

addressFormatter.format({
    first_name: 'John',
    last_name: 'Smith',
    organization: 'Acme Corp',
    street: '123 Main St',
    city: 'Springfield',
    region_code: 'IL',
    postal_code: '62701',
    country_iso2: 'US'
}, 'US', '\n');
```

---

## Part 5: Locale Settings Service

**Service ID:** `oro_locale.settings`
**Class:** `Oro\Bundle\LocaleBundle\Model\LocaleSettings`

Central service for all locale-related configuration.

```php
<?php

use Oro\Bundle\LocaleBundle\Model\LocaleSettings;

class MyService
{
    public function __construct(
        private readonly LocaleSettings $localeSettings,
    ) {
    }

    public function getLocaleInfo(): array
    {
        return [
            'locale'      => $this->localeSettings->getLocale(),
            'language'    => $this->localeSettings->getLanguage(),
            'timezone'    => $this->localeSettings->getTimeZone(),
            'currency'    => $this->localeSettings->getCurrency(),
            'country'     => $this->localeSettings->getCountry(),
        ];
    }

    public function getCurrencySymbol(string $currencyCode): string
    {
        return $this->localeSettings->getCurrencySymbolByCurrency($currencyCode);
    }
}
```

#### Static Utility Methods

```php
use Oro\Bundle\LocaleBundle\Model\LocaleSettings;

// Validate a locale string against environment capabilities
$validLocale = LocaleSettings::getValidLocale('pt_BR');

// Get all available locales
$locales = LocaleSettings::getLocales();

// Map locale to country
$country = LocaleSettings::getCountryByLocale('pt_BR');  // "BR"
```

#### Data Sources and Regeneration

Locale settings data is loaded from YAML files (`locale_data.yml`, `name_format.yml`, `address_format.yml`) and dumped to container parameters at build time:

```bash
# Regenerate locale data after modifying config YAML files
php bin/console cache:clear
php bin/console oro:localization:dump
```

---

## Part 6: Quick Reference and Common Patterns

### 6.1 Adding a New Translation String — Checklist

1. Add the key to `messages.en.yml` (and other locale files if available)
2. Add the same key to `jsmessages.en.yml` if the string is also needed on frontend
3. If it's a validation message, add to `validators.en.yml`
4. If it's an entity label, add to `entities.en.yml`
5. Use the key in PHP (`$translator->trans('key')`), Twig (`{{ 'key'|trans }}`), or JS (`__('key')`)
6. Run `php bin/console cache:clear` after changes
7. If JS string: run `php bin/console oro:translation:dump`

### 6.2 Common Translation Key Prefixes in This Project

| Prefix | Bundle |
|--------|--------|
| `bridge.` | Bridge custom bundles |
| `aaxis.` | Aaxis integration bundle |
| `oro.` | OroCommerce platform |
| `oro_product.` | OroCommerce product bundle |
| `oro_order.` | OroCommerce order bundle |

### 6.3 Translation Loading Command

After adding new translation files or modifying existing ones:

```bash
# Clear cache to pick up new translation files
php bin/console cache:clear

# Dump JS translations (required for jsmessages changes)
php bin/console oro:translation:dump

# Check for missing translations (dev debugging)
php bin/console debug:translation en Bridge\Bundle\BridgeThemeBundle
```

### 6.4 Form Type with Translatable Entity

Oro provides a `translatable_entity` form type that efficiently handles translated entities:

```php
use Oro\Bundle\TranslationBundle\Form\Type\TranslatableEntityType;

$builder->add('division', TranslatableEntityType::class, [
    'class'    => Division::class,
    'property' => 'name',
    'label'    => 'bridge.form.division.label',
]);
```

**WHY this type?** It performs translation in a single DB request instead of N+1 queries per entity.

For Select2 autocomplete:

```php
use Oro\Bundle\TranslationBundle\Form\Type\Select2TranslatableEntityType;

$builder->add('division', Select2TranslatableEntityType::class, [
    'class'    => Division::class,
    'property' => 'name',
]);
```

---

## Part 7: Common Mistakes and Troubleshooting

### Missing Translation Shows Key Instead of Text

**Symptom:** UI shows `bridge.order.status.pending` instead of "Pending".
**Cause:** Translation file not found, wrong domain, or cache not cleared.
**Fix:**
1. Verify file exists at `Resources/translations/messages.en.yml`
2. Check key spelling matches exactly (case-sensitive)
3. Run `php bin/console cache:clear`

### JS Translation Not Updated

**Symptom:** Frontend still shows old text or key after updating `jsmessages.en.yml`.
**Cause:** JS translations are pre-compiled and not read from YAML at runtime.
**Fix:**
```bash
php bin/console oro:translation:dump
php bin/console oro:assets:build  # Or just cache:clear + dump
```

### Locale Settings Not Updated After Config Change

**Symptom:** Name/address format changes in YAML not reflected.
**Fix:**
```bash
php bin/console cache:clear
php bin/console oro:localization:dump
```

### LocalizedFallbackValue Shows Default Instead of Locale-Specific Value

**Symptom:** Product shows English name even when Portuguese localization is active.
**Cause:** No `LocalizedFallbackValue` entry for the `pt_BR` localization, or wrong localization object assigned.
**Fix:** Ensure the collection has an entry with the correct `Localization` entity linked (not just a locale string).

### Datagrid Sorting/Filtering Not Working on Localized Columns

**Symptom:** Sort/filter on a `localized_value` column fails or returns wrong results.
**Cause:** Localization not detected — SQL joins to default fallback.
**Fix:** Ensure the current localization is set in the request context. This is automatic for storefront requests but may need explicit setup in custom contexts.

---

## Part 8: File Discovery — Where to Find Translation Files in This Project

```
src/
├── Bridge/Bundle/
│   ├── BridgeThemeBundle/
│   │   └── Resources/translations/
│   │       ├── messages.en.yml
│   │       ├── jsmessages.en.yml
│   │       └── validators.en.yml
│   ├── BridgeEntityBundle/
│   │   └── Resources/translations/
│   │       └── entities.en.yml
│   └── BridgeCommonBundle/
│       └── Resources/translations/
└── Aaxis/Bundle/
    └── AaxisIntegrationBundle/
        └── Resources/translations/

# Localization config files (per bundle)
src/Bridge/Bundle/*/Resources/config/oro/
├── locale_data.yml       # Country/currency/phone data
├── name_format.yml       # Name format by locale
└── address_format.yml    # Address format by country
```

---

## Related Documentation

- [Symfony Translation Component](https://symfony.com/doc/current/translation.html)
- OroTranslationBundle: `vendor/oro/platform/src/Oro/Bundle/TranslationBundle/`
- OroLocaleBundle: `vendor/oro/platform/src/Oro/Bundle/LocaleBundle/`
- GitHub: [OroLocaleBundle](https://github.com/oroinc/platform/tree/6.1/src/Oro/Bundle/LocaleBundle)
- GitHub: [OroTranslationBundle](https://github.com/oroinc/platform/tree/6.1/src/Oro/Bundle/TranslationBundle)
