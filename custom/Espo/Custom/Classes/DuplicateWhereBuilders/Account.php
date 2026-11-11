<?php

namespace Espo\Custom\Classes\DuplicateWhereBuilders;

use Espo\Core\Duplicate\WhereBuilder;
use Espo\ORM\Entity;
use Espo\ORM\Query\Part\Condition as Cond;
use Espo\ORM\Query\Part\WhereItem;

/**
 * CRM-001: a firm is a potential duplicate when it has the same name and the
 * same billing (firm) address postcode. Same-name branches at different
 * postcodes are therefore not duplicates. Comparison is case-insensitive
 * through the database collation; surrounding spaces are trimmed here.
 *
 * @implements WhereBuilder<Entity>
 */
class Account implements WhereBuilder
{
    public function build(Entity $entity): ?WhereItem
    {
        $name = trim((string) $entity->get('name'));

        if ($name === '') {
            return null;
        }

        $postcode = trim((string) $entity->get('billingAddressPostalCode'));

        $postcodeCondition = $postcode === '' ?
            Cond::or(
                Cond::equal(Cond::column('billingAddressPostalCode'), null),
                Cond::equal(Cond::column('billingAddressPostalCode'), '')
            ) :
            Cond::equal(Cond::column('billingAddressPostalCode'), $postcode);

        return Cond::and(
            Cond::equal(Cond::column('name'), $name),
            $postcodeCondition
        );
    }
}
