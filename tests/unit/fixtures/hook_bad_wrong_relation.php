<?php

namespace Espo\Custom\Hooks\Account;

use Espo\Core\Exceptions\Forbidden;
use Espo\Core\Hook\Hook\BeforeRemove;
use Espo\ORM\Entity;
use Espo\ORM\EntityManager;
use Espo\ORM\Repository\Option\RemoveOptions;

/**
 * CRM-003: a firm (Account) that has any enquiry (a related Opportunity) cannot
 * be deleted. There is deliberately no exception for administrators: to remove
 * such a firm, its enquiries must first be moved or deleted on purpose.
 *
 * @implements BeforeRemove<Entity>
 */
class RestrictDeleteWithEnquiries implements BeforeRemove
{
    public function __construct(private EntityManager $entityManager)
    {}

    public function beforeRemove(Entity $entity, RemoveOptions $options): void
    {
        $enquiryCount = $this->entityManager
            ->getRDBRepository('Account')
            ->getRelation($entity, 'contacts')
            ->count();

        if ($enquiryCount > 0) {
            throw new Forbidden(
                'This firm has enquiries and cannot be deleted. ' .
                'Move or delete its enquiries first.'
            );
        }
    }
}
