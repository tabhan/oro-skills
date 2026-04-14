# OroCommerce: CRUD Pages and Routing

> Source: https://doc.oroinc.com/master/backend/entities/crud/

## AGENT QUERY HINTS

This file answers:
- How do I create CRUD (Create/Read/Update/Delete) pages for a custom entity in OroCommerce?
- How do I define routes for a custom bundle in Oro?
- What is the standard controller pattern for Oro entities?
- How do I create an entity form type in Oro?
- What is the standard Twig template structure for entity views?
- How do I add breadcrumbs and page titles?
- How do I wire the grid into the entity list page?
- What is the difference between `routing.yml` and `Resources/config/oro/routing.yml`?
- How do I add a "Create" button to the entity list page?
- How do I handle form submission in a controller?
- What is UpdateHandlerFacade and how do I use it?
- How do I protect CRUD operations with ACL (#[Acl], #[AclAncestor])?
- How do I add view/edit/delete buttons to a datagrid?
- How do I customize the delete operation for an entity?
- How do I add an entity to the navigation menu?

---

## Core Concept: WHY CRUD Pages Need Special Wiring

OroCommerce uses standard Symfony controllers and forms, but layers on top:
- **Auto-discovered routing** from `Resources/config/oro/routing.yml`
- **OroUI layout system** for breadcrumbs, page titles, and action buttons
- **OroForm** component for entity forms with extended field support
- **OroNavigation** for history tracking and page titles
- **ACL attributes** on controller actions for permission enforcement

A complete CRUD setup requires: Routes → Controller → Form Type → Twig Templates → Grid (for list page).

---

## Step 1: Define Routes

OroCommerce auto-discovers routes from `Resources/config/oro/routing.yml`. This file imports a standard Symfony routing file:

```yaml
# src/Bridge/Bundle/BridgeNewsBundle/Resources/config/oro/routing.yml
# WHY this file: Oro's kernel scans for this exact path in all bundles.
# Routes registered here are auto-loaded — no application-level import needed.

bridge_news:
    resource:     "@BridgeNewsBundle/Resources/config/routing.yml"
    prefix:       /admin    # All routes get /admin prefix
    type:         yaml
```

```yaml
# src/Bridge/Bundle/BridgeNewsBundle/Resources/config/routing.yml
# This is the actual Symfony routing file imported above.

# Entity list (index) page
bridge_news_article_index:
    path:         /news/articles
    methods:      [GET]
    defaults:
        _controller: Bridge\Bundle\BridgeNewsBundle\Controller\NewsArticleController::indexAction

# Create new entity form
bridge_news_article_create:
    path:         /news/articles/create
    methods:      [GET, POST]
    defaults:
        _controller: Bridge\Bundle\BridgeNewsBundle\Controller\NewsArticleController::createAction

# View a single entity
bridge_news_article_view:
    path:         /news/articles/{id}
    methods:      [GET]
    defaults:
        _controller: Bridge\Bundle\BridgeNewsBundle\Controller\NewsArticleController::viewAction
    requirements:
        id: \d+

# Edit an existing entity
bridge_news_article_edit:
    path:         /news/articles/{id}/edit
    methods:      [GET, POST]
    defaults:
        _controller: Bridge\Bundle\BridgeNewsBundle\Controller\NewsArticleController::editAction
    requirements:
        id: \d+

# Delete an entity (POST only — DELETE is called via AJAX from the grid)
bridge_news_article_delete:
    path:         /news/articles/{id}/delete
    methods:      [DELETE]
    defaults:
        _controller: Bridge\Bundle\BridgeNewsBundle\Controller\NewsArticleController::deleteAction
    requirements:
        id: \d+
```

---

## Step 2: Create the Form Type

The form type handles both creating and editing the entity. In Oro, form types extend `AbstractType` but must be registered as services:

```php
<?php
// src/Bridge/Bundle/BridgeNewsBundle/Form/Type/NewsArticleType.php

namespace Bridge\Bundle\BridgeNewsBundle\Form\Type;

use Bridge\Bundle\BridgeNewsBundle\Entity\NewsArticle;
use Symfony\Component\Form\AbstractType;
use Symfony\Component\Form\Extension\Core\Type\TextareaType;
use Symfony\Component\Form\Extension\Core\Type\TextType;
use Symfony\Component\Form\Extension\Core\Type\DateTimeType;
use Symfony\Component\Form\FormBuilderInterface;
use Symfony\Component\OptionsResolver\OptionsResolver;

class NewsArticleType extends AbstractType
{
    public function buildForm(FormBuilderInterface $builder, array $options): void
    {
        $builder
            ->add('title', TextType::class, [
                // label: translation key for the field label.
                // WHY translation key: Oro UI is always translatable.
                'label'    => 'bridge.news.article.title.label',
                'required' => true,
            ])
            ->add('content', TextareaType::class, [
                'label'    => 'bridge.news.article.content.label',
                'required' => false,
                'attr'     => ['rows' => 10],
            ])
            ->add('publishedAt', DateTimeType::class, [
                'label'    => 'bridge.news.article.published_at.label',
                'required' => false,
                // WHY widget: 'single_text': renders as HTML5 datetime-local input.
                'widget'   => 'single_text',
            ]);
    }

    public function configureOptions(OptionsResolver $resolver): void
    {
        $resolver->setDefaults([
            // data_class: tells Symfony which entity this form maps to.
            'data_class' => NewsArticle::class,
        ]);
    }

    // getBlockPrefix() defines the HTML id/class prefix for the form.
    // Keep it lowercase and unique to avoid CSS/JS conflicts with other forms.
    public function getBlockPrefix(): string
    {
        return 'bridge_news_article';
    }
}
```

Register the form type as a service:

```yaml
# src/Bridge/Bundle/BridgeNewsBundle/Resources/config/services.yml
services:
    Bridge\Bundle\BridgeNewsBundle\Form\Type\NewsArticleType:
        tags:
            - { name: form.type }
```

---

## Step 3: Create the Controller

```php
<?php
// src/Bridge/Bundle/BridgeNewsBundle/Controller/NewsArticleController.php

namespace Bridge\Bundle\BridgeNewsBundle\Controller;

use Bridge\Bundle\BridgeNewsBundle\Entity\NewsArticle;
use Bridge\Bundle\BridgeNewsBundle\Form\Type\NewsArticleType;
use Doctrine\ORM\EntityManagerInterface;
use Oro\Bundle\SecurityBundle\Attribute\Acl;
use Oro\Bundle\SecurityBundle\Attribute\AclAncestor;
use Symfony\Bundle\FrameworkBundle\Controller\AbstractController;
use Symfony\Component\HttpFoundation\RedirectResponse;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\HttpFoundation\Response;
use Symfony\Contracts\Translation\TranslatorInterface;

class NewsArticleController extends AbstractController
{
    public function __construct(
        private readonly EntityManagerInterface $entityManager,
        private readonly TranslatorInterface $translator,
    ) {}

    /**
     * Entity list page — shows the datagrid.
     *
     * #[Acl] declares the ACL resource AND protects this action.
     * type: 'entity' links the ACL to the entity class (enables row-level security).
     * permission: 'VIEW' — user needs VIEW permission to access this route.
     */
    #[Acl(
        id: 'bridge_news_article_view',
        type: 'entity',
        class: NewsArticle::class,
        permission: 'VIEW'
    )]
    public function indexAction(): Response
    {
        // The list page renders the datagrid — no data is passed directly.
        // The grid controller fetches data via AJAX.
        return $this->render('@BridgeNews/NewsArticle/index.html.twig');
    }

    /**
     * View a single entity record.
     *
     * #[AclAncestor] reuses the ACL defined above — no new permission definition.
     * WHY: View and index share the same permission. One ACL entry covers both.
     */
    #[AclAncestor('bridge_news_article_view')]
    public function viewAction(int $id): Response
    {
        $article = $this->entityManager->find(NewsArticle::class, $id);

        if ($article === null) {
            throw $this->createNotFoundException(
                sprintf('NewsArticle with ID %d not found.', $id)
            );
        }

        return $this->render('@BridgeNews/NewsArticle/view.html.twig', [
            'entity' => $article,
        ]);
    }

    /**
     * Create a new entity record.
     * #[Acl] with permission: 'CREATE' — user needs CREATE permission.
     */
    #[Acl(
        id: 'bridge_news_article_create',
        type: 'entity',
        class: NewsArticle::class,
        permission: 'CREATE'
    )]
    public function createAction(Request $request): Response
    {
        $article = new NewsArticle();
        $form    = $this->createForm(NewsArticleType::class, $article);

        $form->handleRequest($request);

        if ($form->isSubmitted() && $form->isValid()) {
            $this->entityManager->persist($article);
            $this->entityManager->flush();

            $this->addFlash(
                'success',
                $this->translator->trans('bridge.news.article.saved.message')
            );

            // Redirect to view page after successful creation.
            return $this->redirectToRoute('bridge_news_article_view', [
                'id' => $article->getId(),
            ]);
        }

        return $this->render('@BridgeNews/NewsArticle/create.html.twig', [
            'entity' => $article,
            'form'   => $form->createView(),
        ]);
    }

    /**
     * Edit an existing entity record.
     */
    #[Acl(
        id: 'bridge_news_article_edit',
        type: 'entity',
        class: NewsArticle::class,
        permission: 'EDIT'
    )]
    public function editAction(int $id, Request $request): Response
    {
        $article = $this->entityManager->find(NewsArticle::class, $id);

        if ($article === null) {
            throw $this->createNotFoundException(
                sprintf('NewsArticle with ID %d not found.', $id)
            );
        }

        $form = $this->createForm(NewsArticleType::class, $article);
        $form->handleRequest($request);

        if ($form->isSubmitted() && $form->isValid()) {
            // WHY no persist(): the entity is already managed by Doctrine
            // (retrieved via find()). Only flush() is needed to save changes.
            $this->entityManager->flush();

            $this->addFlash(
                'success',
                $this->translator->trans('bridge.news.article.updated.message')
            );

            return $this->redirectToRoute('bridge_news_article_view', [
                'id' => $article->getId(),
            ]);
        }

        return $this->render('@BridgeNews/NewsArticle/edit.html.twig', [
            'entity' => $article,
            'form'   => $form->createView(),
        ]);
    }

    /**
     * Delete an entity record.
     * Called via AJAX DELETE request from the datagrid delete action.
     */
    #[Acl(
        id: 'bridge_news_article_delete',
        type: 'entity',
        class: NewsArticle::class,
        permission: 'DELETE'
    )]
    public function deleteAction(int $id, Request $request): Response
    {
        $article = $this->entityManager->find(NewsArticle::class, $id);

        if ($article === null) {
            throw $this->createNotFoundException(
                sprintf('NewsArticle with ID %d not found.', $id)
            );
        }

        // WHY check for DELETE method: protect against CSRF via accidental GETs.
        if ($this->isCsrfTokenValid('bridge_news_article_delete', $request->request->get('_token'))
            || $request->isMethod('DELETE')
        ) {
            $this->entityManager->remove($article);
            $this->entityManager->flush();
        }

        return $this->redirectToRoute('bridge_news_article_index');
    }
}
```

---

## Step 4: Register the Controller as a Service

```yaml
# src/Bridge/Bundle/BridgeNewsBundle/Resources/config/services.yml
services:
    Bridge\Bundle\BridgeNewsBundle\Controller\NewsArticleController:
        # WHY public: true: Symfony's router needs to instantiate this from a string.
        public: true
        arguments:
            - '@doctrine.orm.entity_manager'
            - '@translator'
        tags:
            - { name: controller.service_arguments }
```

---

## Step 5: Create Twig Templates

### List Page (index.html.twig)

```twig
{# src/Bridge/Bundle/BridgeNewsBundle/Resources/views/NewsArticle/index.html.twig #}
{% extends '@OroUI/actions/index.html.twig' %}

{# WHY extend OroUI index template: provides the standard Oro page chrome —
   header, breadcrumbs, toolbar, and flash messages automatically. #}

{% import '@OroDataGrid/macros.html.twig' as dataGrid %}

{# Set the page title — shown in <title> tag and breadcrumbs #}
{% block pageTitle %}
    {{ 'bridge.news.articles.page_title'|trans }}
{% endblock %}

{# Inject the "Create News Article" button into the page toolbar #}
{% block navButtons %}
    {% if is_granted('bridge_news_article_create') %}
        <a href="{{ path('bridge_news_article_create') }}" class="btn btn-primary">
            <i class="fa fa-plus"></i>
            {{ 'bridge.news.article.create_button.label'|trans }}
        </a>
    {% endif %}
{% endblock %}

{# Render the datagrid — the grid name matches the key in datagrids.yml #}
{% block content %}
    {{ dataGrid.renderGrid('bridge-news-article-grid') }}
{% endblock %}
```

### View Page (view.html.twig)

```twig
{# src/Bridge/Bundle/BridgeNewsBundle/Resources/views/NewsArticle/view.html.twig #}
{% extends '@OroUI/actions/view.html.twig' %}

{# WHY extend OroUI view template: provides standard back-office view chrome —
   breadcrumbs with entity navigation, action buttons block, subtitle area. #}

{% block pageTitle %}
    {{ entity.title }}
{% endblock %}

{# Action buttons shown in the view page header #}
{% block navButtons %}
    {% if is_granted('bridge_news_article_edit') %}
        <a href="{{ path('bridge_news_article_edit', { id: entity.id }) }}"
           class="btn btn-primary">
            {{ 'bridge.news.article.edit_button.label'|trans }}
        </a>
    {% endif %}
    {% if is_granted('bridge_news_article_delete') %}
        {{ UI.deleteButton({
            'dataUrl': path('bridge_news_article_delete', { id: entity.id }),
            'dataRedirect': path('bridge_news_article_index'),
            'aCss': 'no-hash remove-button',
            'id': 'btn-remove-news-article',
            'dataId': entity.id,
            'entity_label': 'News Article'|trans
        }) }}
    {% endif %}
{% endblock %}

{# Entity data sections #}
{% block content_data %}
    <div class="widget-content">
        {% set generalSection %}
            <div class="row-fluid form-horizontal">
                <div class="responsive-block">
                    {{ UI.renderProperty('bridge.news.article.title.label'|trans, entity.title) }}
                    {{ UI.renderProperty('bridge.news.article.published_at.label'|trans,
                        entity.publishedAt ? entity.publishedAt|oro_format_datetime : '') }}
                </div>
                <div class="responsive-block">
                    {{ UI.renderHtmlProperty('bridge.news.article.content.label'|trans, entity.content) }}
                </div>
            </div>
        {% endset %}

        {{ UI.scrollData(entity.id, {
            'general': {
                'title': 'General Information'|trans,
                'data': generalSection
            }
        }) }}
    </div>
{% endblock %}
```

### Create Page (create.html.twig)

```twig
{# src/Bridge/Bundle/BridgeNewsBundle/Resources/views/NewsArticle/create.html.twig #}
{% extends '@OroUI/actions/create.html.twig' %}

{% block pageTitle %}
    {{ 'bridge.news.article.create_page_title'|trans }}
{% endblock %}

{% block content %}
    {{ form_start(form, { action: path('bridge_news_article_create'), method: 'POST' }) }}

    <div class="widget-content">
        <div class="row-fluid form-horizontal">
            <div class="responsive-block">
                {{ form_row(form.title) }}
                {{ form_row(form.publishedAt) }}
            </div>
            <div class="responsive-block">
                {{ form_row(form.content) }}
            </div>
        </div>
    </div>

    <div class="widget-actions form-actions">
        <button type="submit" class="btn btn-success">
            {{ 'bridge.news.article.save_button.label'|trans }}
        </button>
        <a href="{{ path('bridge_news_article_index') }}" class="btn">
            {{ 'Cancel'|trans }}
        </a>
    </div>

    {{ form_end(form) }}
{% endblock %}
```

### Edit Page (edit.html.twig)

```twig
{# src/Bridge/Bundle/BridgeNewsBundle/Resources/views/NewsArticle/edit.html.twig #}
{% extends '@OroUI/actions/update.html.twig' %}

{% block pageTitle %}
    {{ 'bridge.news.article.edit_page_title'|trans({'{title}': entity.title}) }}
{% endblock %}

{% block content %}
    {{ form_start(form, {
        action: path('bridge_news_article_edit', { id: entity.id }),
        method: 'POST'
    }) }}

    <div class="widget-content">
        <div class="row-fluid form-horizontal">
            <div class="responsive-block">
                {{ form_row(form.title) }}
                {{ form_row(form.publishedAt) }}
            </div>
            <div class="responsive-block">
                {{ form_row(form.content) }}
            </div>
        </div>
    </div>

    <div class="widget-actions form-actions">
        <button type="submit" class="btn btn-success">
            {{ 'bridge.news.article.save_button.label'|trans }}
        </button>
        <a href="{{ path('bridge_news_article_view', { id: entity.id }) }}" class="btn">
            {{ 'Cancel'|trans }}
        </a>
    </div>

    {{ form_end(form) }}
{% endblock %}
```

---

## Step 6: Add Navigation Menu Entry

```yaml
# src/Bridge/Bundle/BridgeNewsBundle/Resources/config/oro/navigation.yml
navigation:
    menu_config:
        items:
            # Define the menu item
            bridge_news_article_list:
                label: bridge.news.article.menu.label
                route: bridge_news_article_index
                # acl_resource: controls when this item is visible.
                # WHY: Hidden from users without view permission.
                acl_resource: bridge_news_article_view

        tree:
            # Place the item in the application_menu (main left sidebar)
            application_menu:
                children:
                    # Under an existing section, e.g., "content_management_tab"
                    content_management_tab:
                        children:
                            bridge_news_article_list: ~
```

---

## Step 7: Wire the Datagrid

Create the grid definition so the list page has data:

```yaml
# src/Bridge/Bundle/BridgeNewsBundle/Resources/config/oro/datagrids.yml
datagrids:
    bridge-news-article-grid:
        acl_resource: bridge_news_article_view

        source:
            type: orm
            query:
                select:
                    - a.id
                    - a.title
                    - a.publishedAt
                from:
                    - { table: Bridge\Bundle\BridgeNewsBundle\Entity\NewsArticle, alias: a }
                where:
                    and:
                        - a.deletedAt IS NULL

        columns:
            title:
                label: bridge.news.article.title.label
                frontend_type: string
            publishedAt:
                label: bridge.news.article.published_at.label
                frontend_type: datetime

        properties:
            id: ~
            view_link:
                type: url
                route: bridge_news_article_view
                params: [id]
            edit_link:
                type: url
                route: bridge_news_article_edit
                params: [id]
            delete_link:
                type: url
                route: bridge_news_article_delete
                params: [id]

        sorters:
            columns:
                title:
                    data_name: a.title
                publishedAt:
                    data_name: a.publishedAt
            default:
                publishedAt: DESC

        filters:
            columns:
                title:
                    type: string
                    data_name: a.title

        actions:
            view:
                type: navigate
                label: oro.grid.action.view
                icon: eye
                link: view_link
                rowAction: true
                acl_resource: bridge_news_article_view
            edit:
                type: navigate
                label: oro.grid.action.edit
                icon: pencil
                link: edit_link
                acl_resource: bridge_news_article_edit
            delete:
                type: delete
                label: oro.grid.action.delete
                icon: trash-o
                link: delete_link
                confirmation: true
                acl_resource: bridge_news_article_delete

        options:
            entity_pagination: true
            export: true
```

---

## Full File Checklist

After creating all files, verify:

- [ ] `Resources/config/oro/routing.yml` exists and imports the routing file
- [ ] `Resources/config/routing.yml` defines all 5 routes (index, view, create, edit, delete)
- [ ] Controller class exists with all 5 action methods
- [ ] Controller is registered as a service in `services.yml`
- [ ] Form type class exists and is registered as a service
- [ ] Twig templates exist: `index.html.twig`, `view.html.twig`, `create.html.twig`, `edit.html.twig`
- [ ] Datagrid is defined in `Resources/config/oro/datagrids.yml`
- [ ] Navigation menu entry in `Resources/config/oro/navigation.yml`
- [ ] Route names in `#[Config]` attribute match the actual route names
- [ ] Run `php bin/console cache:clear` and `php bin/console oro:platform:update --force`

---

## Common Pitfalls

| Pitfall | Problem | Fix |
|---------|---------|-----|
| Controller not registered as service | `Controller not found` error | Add to `services.yml` with `public: true` tag |
| Route name mismatch in `#[Config]` | Entity list has broken links in admin panel | Match route names exactly in `#[Config]` and `routing.yml` |
| Missing `id` in template route paths | Broken URLs in view/edit pages | Always pass `{ id: entity.id }` to path() |
| `createForm()` with wrong data_class | Form validation fails silently | Verify `data_class` in `configureOptions()` |
| Forgetting `form->handleRequest($request)` | Form never processes POST data | Always call before `isSubmitted()` |
| Using `persist()` on an existing entity | Doctrine tries to INSERT instead of UPDATE | Only call `persist()` on new entities |
| Caching routing without clearing | Old routes served after adding new ones | Run `php bin/console cache:clear` |

---

## UpdateHandlerFacade (Alternative to Manual Form Handling)

Oro provides `Oro\Bundle\FormBundle\Model\UpdateHandlerFacade` which abstracts the form-handle-persist-redirect cycle. Useful for entities with "Save and New" / "Save and Return" button behaviors:

```php
use Oro\Bundle\FormBundle\Model\UpdateHandlerFacade;

class QuestionController extends AbstractController
{
    #[Route(path: '/create', name: 'create')]
    #[Acl(id: 'acme_demo_question_create', type: 'entity',
          class: Question::class, permission: 'CREATE')]
    #[Template('@AcmeDemo/Question/update.html.twig')]
    public function createAction(Request $request): array|RedirectResponse
    {
        $entity = new Question();
        return $this->container->get(UpdateHandlerFacade::class)->update(
            $entity,
            $this->createForm(QuestionType::class, $entity),
            'Question created.',  // flash message on success
            $request,
            null                  // null = use default EntityManager persist/flush
        );
    }

    public static function getSubscribedServices(): array
    {
        return array_merge(parent::getSubscribedServices(), [
            UpdateHandlerFacade::class,
        ]);
    }
}
```

### UpdateHandlerFacade parameter reference

| Parameter | Type | Description |
|-----------|------|-------------|
| `$entity` | object | The entity being created or updated |
| `$form` | FormInterface | Form instance with entity as data |
| `$message` | string | Flash message shown after successful save |
| `$request` | Request | The current HTTP Request |
| `$handler` | callable\|null | Custom save handler; `null` uses default EntityManager |

The facade returns:
- `array` — on GET requests (for template rendering)
- `array` — on failed POST validation (form re-rendered with errors)
- `RedirectResponse` — on successful POST (redirects based on submit button clicked)

### Delete operation with default DELETE action

When an entity has `routeName` in `#[Config]`, delete works automatically via Oro's operation system. No custom delete action needed — add only to the datagrid:

```yaml
# In datagrids.yml — link to the oro_api_delete_{entity} route pattern
delete_link:
    type: url
    route: oro_api_delete_question   # Oro generates this route for entities with API
    params: [id]
```
