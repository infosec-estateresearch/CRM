<?php

namespace Espo\Custom\Hooks\Task;

use Espo\Core\Hook\Hook\BeforeSave;
use Espo\ORM\Entity;
use Espo\ORM\Repository\Option\SaveOptions;

/**
 * CRM-008-G (item 2): keep the Salesforce completion date of an imported Task.
 * Core Task.dateCompleted is readOnly, and the core hook
 * Espo\Modules\Crm\Hooks\Task\DateCompleted sets it to now whenever the status becomes
 * Completed. The importer sends the Salesforce value in sfCompletedAt instead; this hook
 * runs after core ($order 20) and copies it to dateCompleted when the status is Completed,
 * sfCompletedAt is set and the entity is new or sfCompletedAt changed. Any other save keeps
 * core's behaviour, so a staff member re-completing a reopened Task gets core's now.
 * The rule table is mirrored in tests/unit/activity_policy.py (completed_date_after_save).
 *
 * @implements BeforeSave<Entity>
 */
class PreserveSalesforceCompletedDate implements BeforeSave
{
    public static int $order = 20;

    public function beforeSave(Entity $entity, SaveOptions $options): void
    {
        if ($entity->get('status') !== 'Completed') {
            return;
        }

        $sfCompletedAt = $entity->get('sfCompletedAt');

        if (!$sfCompletedAt) {
            return;
        }

        if (!$entity->isNew() && !$entity->isAttributeChanged('sfCompletedAt')) {
            return;
        }

        $entity->set('dateCompleted', $sfCompletedAt);
    }
}
