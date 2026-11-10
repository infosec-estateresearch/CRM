<?php

namespace Espo\Custom\Classes\Select\Opportunity\PrimaryFilters;

use Espo\Core\Select\Primary\Filter;
use Espo\ORM\Query\Part\Condition as Cond;
use Espo\ORM\Query\SelectBuilder;

/**
 * CRM-004 "Open enquiries" (the default list): stage Enquiry or Quoted, and not
 * flagged legacy stale (D2).
 */
class OpenEnquiries implements Filter
{
    public function apply(SelectBuilder $queryBuilder): void
    {
        $queryBuilder->where(
            Cond::and(
                Cond::in(Cond::column('stage'), ['Enquiry', 'Quoted']),
                Cond::equal(Cond::column('legacyStale'), false)
            )
        );
    }
}
