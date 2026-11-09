<?php

namespace Espo\Custom\Classes\DuplicateWhereBuilders;

use Espo\Core\Duplicate\WhereBuilder;
use Espo\ORM\Entity;
use Espo\ORM\Query\Part\WhereClause;
use Espo\ORM\Query\Part\WhereItem;

/**
 * CRM-001: a contact is a potential duplicate when it has the same primary
 * email address as an existing contact (case-insensitive via collation).
 *
 * @implements WhereBuilder<Entity>
 */
class Contact implements WhereBuilder
{
    public function build(Entity $entity): ?WhereItem
    {
        $emailAddress = trim((string) $entity->get('emailAddress'));

        if ($emailAddress === '') {
            return null;
        }

        return WhereClause::fromRaw([
            'emailAddress' => $emailAddress,
        ]);
    }
}
