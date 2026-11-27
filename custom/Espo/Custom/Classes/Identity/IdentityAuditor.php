<?php

namespace Espo\Custom\Classes\Identity;

use Espo\Core\Exceptions\Forbidden;
use Espo\Entities\User;
use Espo\ORM\EntityManager;
use Throwable;

/**
 * CRM-IDINT-001 (3.1, audit or fail): writes one IdentityAudit record and proves it
 * is stored. If it cannot be stored the caller's change must not go ahead, so any
 * failure here is a Forbidden that the calling hook lets propagate.
 *
 * The record names the actor, the UTC time, the record changed, the relationship
 * and the previous and new values (identifiers; for a status change, the status
 * words). An empty value means "none".
 */
class IdentityAuditor
{
    public function __construct(
        private EntityManager $entityManager,
        private User $user
    ) {}

    public function record(
        string $relationship,
        string $recordType,
        string $recordId,
        ?string $previous,
        ?string $new
    ): void {
        try {
            $audit = $this->entityManager->getNewEntity(IdentityPolicy::AUDIT_ENTITY);

            $audit->set([
                'name' => $relationship . ' ' . $recordType . ' ' . $recordId,
                'occurredAt' => gmdate('Y-m-d H:i:s'),
                'actorId' => (string) $this->user->getId(),
                'actorName' => (string) $this->user->getUserName(),
                'relationship' => $relationship,
                'recordType' => $recordType,
                'recordId' => $recordId,
                'previousValue' => (string) $previous,
                'newValue' => (string) $new,
            ]);

            $this->entityManager->saveEntity($audit, [IdentityPolicy::AUDIT_WRITE_OPTION => true]);

            $stored = $this->entityManager->getEntityById(IdentityPolicy::AUDIT_ENTITY, $audit->getId());

            if (
                !$stored ||
                $stored->get('recordId') !== $recordId ||
                $stored->get('relationship') !== $relationship ||
                (string) $stored->get('newValue') !== (string) $new ||
                (string) $stored->get('previousValue') !== (string) $previous
            ) {
                throw new \RuntimeException('read-back differs');
            }
        } catch (Throwable) {
            throw new Forbidden(
                'The identity audit record could not be stored, so the change was refused. Nothing was changed.'
            );
        }
    }
}
