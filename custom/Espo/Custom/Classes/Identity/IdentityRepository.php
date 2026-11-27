<?php

namespace Espo\Custom\Classes\Identity;

use Espo\Core\Repositories\Database;
use Espo\ORM\Entity;
use Espo\ORM\Repository\RDBRelation;
use Throwable;

/**
 * CRM-IDINT-001R2 (S2, S3): the repository of firms, contacts and enquiries
 * (entityDefs repositoryClassName). Its relation object (IdentityRelation) runs each
 * relate, unrelate and mass relate, with every hook and the audit, in one transaction.
 * A save is one transaction through entityDefs transactionalSave.
 *
 * When a save fails, its transaction has been rolled back, so nothing the guard
 * remembered of the audit records written in it may survive in this request.
 */
class IdentityRepository extends Database
{
    public function save(Entity $entity, array $options = []): void
    {
        try {
            parent::save($entity, $options);
        } catch (Throwable $e) {
            IdentityGuard::resetRequestState();

            throw $e;
        }
    }

    public function getRelation(Entity $entity, string $relationName): RDBRelation
    {
        return new IdentityRelation($this->entityManager, $entity, $relationName, $this->hookMediator);
    }
}
