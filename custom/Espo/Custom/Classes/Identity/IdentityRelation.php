<?php

namespace Espo\Custom\Classes\Identity;

use Espo\ORM\Entity;
use Espo\ORM\EntityManager;
use Espo\ORM\Query\Select;
use Espo\ORM\Repository\RDBRelation;
use Throwable;

/**
 * CRM-IDINT-001R2 (S2, S3): the relation object of firms, contacts and enquiries. Each
 * relate, unrelate and mass relate runs, with the platform's hooks and the identity
 * audit, in one transaction: a refusal or a failed audit leaves nothing behind, and no
 * compensating write is needed. When the transaction fails, the guard forgets what it
 * remembered of the audit records written in it.
 *
 * @extends RDBRelation<Entity>
 */
class IdentityRelation extends RDBRelation
{
    public function __construct(
        private EntityManager $manager,
        Entity $entity,
        string $relationName,
        \Espo\ORM\Repository\HookMediator $hookMediator
    ) {
        parent::__construct($manager, $entity, $relationName, $hookMediator);
    }

    public function relate(Entity $entity, ?array $columnData = null, array $options = []): void
    {
        $this->atomically(function () use ($entity, $columnData, $options): void {
            parent::relate($entity, $columnData, $options);
        });
    }

    public function unrelate(Entity $entity, array $options = []): void
    {
        $this->atomically(function () use ($entity, $options): void {
            parent::unrelate($entity, $options);
        });
    }

    public function massRelate(Select $query, array $options = []): void
    {
        $this->atomically(function () use ($query, $options): void {
            parent::massRelate($query, $options);
        });
    }

    private function atomically(\Closure $change): void
    {
        try {
            $this->manager->getTransactionManager()->run($change);
        } catch (Throwable $e) {
            IdentityGuard::resetRequestState();

            throw $e;
        }
    }
}
