<?php

namespace Espo\Custom\Classes\Select\Opportunity\PrimaryFilters;

use Espo\Core\Select\Primary\Filter;
use Espo\Entities\User;
use Espo\ORM\Query\Part\Condition as Cond;
use Espo\ORM\Query\SelectBuilder;

/**
 * CRM-004 "My open enquiries": the open enquiries assigned to the current user.
 */
class MyOpenEnquiries implements Filter
{
    public function __construct(private User $user)
    {}

    public function apply(SelectBuilder $queryBuilder): void
    {
        $queryBuilder->where(
            Cond::and(
                Cond::in(Cond::column('stage'), ['Enquiry', 'Quoted']),
                Cond::equal(Cond::column('legacyStale'), false),
                Cond::equal(Cond::column('assignedUserId'), $this->user->getId())
            )
        );
    }
}
