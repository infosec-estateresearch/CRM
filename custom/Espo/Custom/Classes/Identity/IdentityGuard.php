<?php

namespace Espo\Custom\Classes\Identity;

use Espo\Core\Exceptions\BadRequest;
use Espo\Core\Exceptions\Forbidden;
use Espo\Core\Utils\Metadata;
use Espo\ORM\Entity;
use Espo\ORM\EntityManager;
use Espo\ORM\Query\DeleteBuilder;
use Throwable;

/**
 * CRM-IDINT-001: the server side of identity integrity. Every identity
 * relationship change on Account, Contact and Opportunity passes through here,
 * from the thin hooks under Hooks/<Entity>/ (see the route matrix in
 * docs/IDENTITY-INTEGRITY.md). There is no bypass for administrators or service
 * accounts: the hooks run for every caller.
 *
 * - A change is audited before it happens (updates, links) or right after the
 *   record gets its identifier (creates). A create whose audit cannot be stored
 *   is undone, so it leaves nothing behind (3.1).
 * - Deleting, mass deleting and (through the controller) merging firms and
 *   contacts is refused (3.4, 3.7).
 * - Identifiers are issued only by ERm; CSV import is refused (3.7).
 */
class IdentityGuard
{
    public function __construct(
        private EntityManager $entityManager,
        private IdentityAuditor $auditor,
        private Metadata $metadata
    ) {}

    // ---- save -----------------------------------------------------------------

    public function beforeSave(Entity $entity, object $options): void
    {
        $type = $entity->getEntityType();

        if (!isset(IdentityPolicy::FOREIGN_KEYS[$type])) {
            return;
        }

        if (IdentityPolicy::option($options, 'import')) {
            throw new Forbidden('Import is not available for firms, contacts and enquiries.');
        }

        $isNew = $entity->isNew();

        if ($isNew && !IdentityPolicy::isEmpty($entity->get('id'))) {
            throw new Forbidden('Identifiers are issued only by ERm. A supplied identifier is refused.');
        }

        $this->checkLengths($entity, $type, $isNew);

        if (in_array($type, IdentityPolicy::STATUS_ENTITIES, true)) {
            $this->checkStatus($entity, $type, $isNew);
        }

        if ($type === 'Contact') {
            $this->checkPrimaryStaysLinked($entity);
        }

        if ($isNew) {
            return;
        }

        foreach ($this->changes($entity, $type) as [$relationship, $previous, $new]) {
            $this->auditor->record($relationship, $type, (string) $entity->getId(), $previous, $new);
        }

        if ($type === 'Contact') {
            $this->auditLinkListChange($entity);
        }
    }

    public function afterSave(Entity $entity): void
    {
        $type = $entity->getEntityType();

        if (!isset(IdentityPolicy::FOREIGN_KEYS[$type]) || !$entity->isNew()) {
            return;
        }

        $this->undoCreateOnFailure($entity, function () use ($entity, $type): void {
            foreach (IdentityPolicy::FOREIGN_KEYS[$type] as $attribute => $relationship) {
                $value = $entity->get($attribute);

                if (!IdentityPolicy::isEmpty($value)) {
                    $this->auditor->record($relationship, $type, (string) $entity->getId(), '', (string) $value);
                }
            }

            // A new contact's extra firm links are audited here, from the saved record, so
            // that this does not depend on core firing the relate hooks when it writes the
            // link rows. A link the relate hook has already audited is not recorded twice.
            if ($type === 'Contact') {
                foreach (array_unique(array_map('strval', (array) $entity->get('accountsIds'))) as $firmId) {
                    if ($firmId !== '') {
                        $this->recordNewOnce(
                            IdentityPolicy::REL_CONTACT_FIRM_LINK,
                            'Contact',
                            (string) $entity->getId(),
                            '',
                            $firmId
                        );
                    }
                }
            }
        });
    }

    /** @return list<array{string, string, string}> relationship, previous, new */
    private function changes(Entity $entity, string $type): array
    {
        $out = [];

        foreach (IdentityPolicy::FOREIGN_KEYS[$type] as $attribute => $relationship) {
            if (!$entity->isAttributeChanged($attribute)) {
                continue;
            }

            $previous = (string) $entity->getFetched($attribute);
            $new = (string) $entity->get($attribute);

            if ($previous !== $new) {
                $out[] = [$relationship, $previous, $new];
            }
        }

        if (
            in_array($type, IdentityPolicy::STATUS_ENTITIES, true) &&
            $entity->isAttributeChanged('identityStatus')
        ) {
            $previous = $this->statusWord($entity->getFetched('identityStatus'));
            $new = $this->statusWord($entity->get('identityStatus'));

            if ($previous !== $new) {
                $out[] = [IdentityPolicy::REL_STATUS, $previous, $new];
            }
        }

        return $out;
    }

    /**
     * 3.8: input longer than a stored text field allows is a validation error, never a
     * database error. The limit is the field's maxLength (or len) in the metadata.
     */
    private function checkLengths(Entity $entity, string $type, bool $isNew): void
    {
        $fields = $this->metadata->get(['entityDefs', $type, 'fields']);

        foreach (is_array($fields) ? $fields : [] as $name => $definition) {
            if (!is_array($definition) || ($definition['type'] ?? null) !== 'varchar') {
                continue;
            }

            $limit = $definition['maxLength'] ?? ($definition['len'] ?? null);

            if (!is_int($limit) || $limit <= 0 || !$entity->has($name)) {
                continue;
            }

            if (!$isNew && !$entity->isAttributeChanged($name)) {
                continue;
            }

            $value = $entity->get($name);

            if (is_string($value) && mb_strlen($value) > $limit) {
                throw new BadRequest("The value of {$name} is longer than the {$limit} characters allowed.");
            }
        }
    }

    private function statusWord(mixed $value): string
    {
        return IdentityPolicy::isEmpty($value) ? IdentityPolicy::STATUS_ACTIVE : (string) $value;
    }

    private function checkStatus(Entity $entity, string $type, bool $isNew): void
    {
        $status = $this->statusWord($entity->get('identityStatus'));
        $successorId = $entity->get('successorId');

        if ($isNew) {
            if ($status !== IdentityPolicy::STATUS_ACTIVE || !IdentityPolicy::isEmpty($successorId)) {
                throw new BadRequest('A new record is active and has no successor.');
            }

            return;
        }

        if (!$entity->isAttributeChanged('identityStatus') && !$entity->isAttributeChanged('successorId')) {
            return;
        }

        $successor = IdentityPolicy::isEmpty($successorId) ?
            null : $this->entityManager->getEntityById($type, (string) $successorId);

        $problem = IdentityPolicy::statusProblem($status, $successorId, $successor !== null);

        if ($problem === null && !IdentityPolicy::isEmpty($successorId)) {
            $selfId = (string) $entity->getId();

            if ($selfId === (string) $successorId) {
                $problem = 'A record cannot be its own successor.';
            } elseif (IdentityPolicy::successorLoop($selfId, (string) $successorId, function (string $id) use ($type) {
                $next = $this->entityManager->getEntityById($type, $id);

                return $next ? $next->get('successorId') : null;
            })) {
                $problem = 'That successor would make a cycle.';
            }
        }

        if ($problem !== null) {
            throw new BadRequest($problem);
        }
    }

    private function checkPrimaryStaysLinked(Entity $entity): void
    {
        // Checked when the link list is part of this save (a new contact's links
        // are otherwise written after the save and checked by beforeUnrelate).
        $listInSave = $entity->isNew() ? $entity->has('accountsIds') : $entity->isAttributeChanged('accountsIds');

        if (!$listInSave) {
            return;
        }

        $linked = array_map('strval', (array) $entity->get('accountsIds'));

        if (IdentityPolicy::primaryFirmBroken($entity->get('accountId'), $linked)) {
            throw new BadRequest(
                'The primary firm must be one of the linked firms. ' .
                'Set another linked firm as primary, or clear the primary firm, in the same change.'
            );
        }
    }

    private function auditLinkListChange(Entity $entity): void
    {
        if (!$entity->isAttributeChanged('accountsIds')) {
            return;
        }

        $before = array_map('strval', (array) $entity->getFetched('accountsIds'));
        $after = array_map('strval', (array) $entity->get('accountsIds'));

        foreach (array_diff($after, $before) as $id) {
            $this->auditor->record(IdentityPolicy::REL_CONTACT_FIRM_LINK, 'Contact', (string) $entity->getId(), '', $id);
        }

        foreach (array_diff($before, $after) as $id) {
            $this->auditor->record(IdentityPolicy::REL_CONTACT_FIRM_LINK, 'Contact', (string) $entity->getId(), $id, '');
        }
    }

    // ---- links ----------------------------------------------------------------

    public function beforeRelate(Entity $entity, string $link, Entity $foreign): void
    {
        $this->linkChange($entity, $link, $foreign, true);
    }

    public function beforeUnrelate(Entity $entity, string $link, Entity $foreign): void
    {
        $this->linkChange($entity, $link, $foreign, false);
    }

    public function beforeMassRelate(Entity $entity, string $link): void
    {
        $type = $entity->getEntityType();

        if (in_array($link, IdentityPolicy::BULK_REFUSED_LINKS[$type] ?? [], true)) {
            throw new Forbidden('Bulk linking is not available for identity relationships. Link records one at a time.');
        }
    }

    private function linkChange(Entity $entity, string $link, Entity $foreign, bool $relate): void
    {
        $type = $entity->getEntityType();

        if (in_array($link, IdentityPolicy::EDIT_ONLY_LINKS[$type] ?? [], true)) {
            throw new Forbidden('Retire or supersede a record by editing it, not by linking.');
        }

        $definition = IdentityPolicy::LINKS[$type][$link] ?? null;

        if ($definition === null) {
            return;
        }

        [$relationship, $changedSide, $firmSide] = $definition;

        $changed = $changedSide === 'self' ? $entity : $foreign;
        $firmId = (string) ($firmSide === 'self' ? $entity : $foreign)->getId();
        $changedType = $changed->getEntityType();

        if ($relationship === IdentityPolicy::REL_CONTACT_FIRM_LINK) {
            $previous = $relate ? '' : $firmId;
            $new = $relate ? $firmId : '';

            if (!$relate && IdentityPolicy::unlinkRemovesPrimary($changed->get('accountId'), $firmId)) {
                throw new Forbidden(
                    'This firm is the contact\'s primary firm. Set another linked firm as primary, ' .
                    'or clear the primary firm, before removing the link.'
                );
            }
        } else {
            $attribute = $relationship === IdentityPolicy::REL_PARENT_FIRM ? 'parentId' : 'accountId';
            $previous = $relate ? (string) $changed->get($attribute) : $firmId;
            $new = $relate ? $firmId : '';
        }

        if ($previous === $new) {
            return;
        }

        if ($changed->isNew()) {
            $this->undoCreateOnFailure($changed, function () use ($relationship, $changedType, $changed, $previous, $new): void {
                $this->recordNewOnce($relationship, $changedType, (string) $changed->getId(), $previous, $new);
            });

            return;
        }

        $this->auditor->record($relationship, $changedType, (string) $changed->getId(), $previous, $new);
    }

    // ---- remove ---------------------------------------------------------------

    public function beforeRemove(Entity $entity): void
    {
        throw new Forbidden(
            'Firms and contacts are never deleted. Retire the record, or supersede it with a successor.'
        );
    }

    // ---- helpers --------------------------------------------------------------

    /**
     * Records a change of a record that is being created, unless the identical record
     * is already stored (the record id is unique, so a match is the same change).
     */
    private function recordNewOnce(string $relationship, string $type, string $id, string $previous, string $new): void
    {
        $existing = $this->entityManager->getRDBRepository(IdentityPolicy::AUDIT_ENTITY)->where([
            'relationship' => $relationship,
            'recordType' => $type,
            'recordId' => $id,
            'previousValue' => $previous,
            'newValue' => $new,
        ])->count();

        if ($existing === 0) {
            $this->auditor->record($relationship, $type, $id, $previous, $new);
        }
    }

    /** Removes the firm link rows written for a contact whose create is being undone. */
    private function deleteLinkRows(Entity $entity): void
    {
        if ($entity->getEntityType() !== 'Contact') {
            return;
        }

        $this->entityManager->getQueryExecutor()->execute(
            DeleteBuilder::create()->from('AccountContact')->where(['contactId' => (string) $entity->getId()])->build()
        );
    }

    /**
     * Runs $write; if the audit cannot be stored and the record is one this request
     * is creating, the record is removed again so the create leaves nothing behind.
     */
    private function undoCreateOnFailure(Entity $entity, callable $write): void
    {
        try {
            $write();
        } catch (Forbidden $e) {
            if ($entity->isNew() && !IdentityPolicy::isEmpty($entity->getId())) {
                try {
                    $this->deleteLinkRows($entity);
                } catch (Throwable) {
                    // The link rows of an undone create may remain; see docs/IDENTITY-INTEGRITY.md.
                }

                try {
                    $this->entityManager
                        ->getRDBRepository($entity->getEntityType())
                        ->deleteFromDb((string) $entity->getId());
                } catch (Throwable) {
                    // Nothing more can be done here; the refusal below still stops the request.
                }
            }

            throw $e;
        }
    }
}
