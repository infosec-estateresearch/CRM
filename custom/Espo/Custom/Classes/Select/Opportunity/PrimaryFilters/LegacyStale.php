<?php

namespace Espo\Custom\Classes\Select\Opportunity\PrimaryFilters;

use Espo\Core\Select\Primary\Filter;
use Espo\ORM\Query\Part\Condition as Cond;
use Espo\ORM\Query\SelectBuilder;

/**
 * CRM-004 "Legacy stale" (D2): enquiries the importer flagged as stale.
 */
class LegacyStale implements Filter
{
    public function apply(SelectBuilder $queryBuilder): void
    {
        $queryBuilder->where(
            Cond::equal(Cond::column('legacyStale'), true)
        );
    }
}
