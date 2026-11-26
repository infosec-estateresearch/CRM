<?php

namespace Espo\Custom\Classes\Identity;

use Espo\Core\Exceptions\BadRequest;
use Espo\Core\Exceptions\Forbidden;
use Espo\Core\Utils\Metadata;
use Espo\ORM\Entity;
use Espo\ORM\EntityManager;
use Espo\ORM\Query\DeleteBuilder;
use Espo\ORM\Query\Select;
use Espo\ORM\Query\UpdateBuilder;
use Espo\ORM\Repository\Option\SaveOptions;
use Throwable;

/**
 * CRM-IDINT-001R: the server side of identity integrity. Every identity relationship
 * change on Account, Contact and Opportunity passes through here, from the thin hooks
 * under Hooks/<Entity>/ and the record hooks under Classes/Identity/RecordHooks/ (see
 * the route matrix in docs/IDENTITY-INTEGRITY.md). There is no bypass for
 * administrators or service accounts: the hooks run for every caller.
 *
 * Only extension points the platform really calls are used:
 * - BeforeSave and BeforeRemove (before hooks), AfterSave, AfterRelate, AfterUnrelate and
 *   AfterMassRelate (the platform has no before-relation hook for custom code);
 * - the record link, unlink, delete, create and update hooks (recordDefs);
 * - recordDefs switches (actions.merge.disabled, massActions.delete.disabled,
 *   relationships.<link>.massLink).
 *
 * A relation change has already happened when its after hook runs, so the after hook
 * records the audit and, if the audit cannot be stored, puts the change back and refuses
 * (3.1). A save is audited before it is written (BeforeSave). A create whose audit cannot
 * be stored is undone.
 */
class IdentityGuard
{
    /**
     * The last link change audited for each link in this request ("linked" or "unlinked").
     * The platform may report the same change twice (when a contact's primary firm is
     * cleared it unrelates a firm the link-multiple save has just unrelated); a second
     * identical change cannot be a change, so it is not audited again.
     *
     * @var array<string, string>
     */
    private static array $linkState = [];

    /** Forgets the per-request link ledger (a new request, or a test, starts clean). */
    public static function resetRequestState(): void
    {
        self::$linkState = [];
    }

    public function __construct(
        private EntityManager $entityManager,
        private IdentityAuditor $auditor,
        private Metadata $metadata
    ) {}

    // ---- save -----------------------------------------------------------------

    public function beforeSave(Entity $entity, SaveOptions $options): void
    {
        $type = $entity->getEntityType();

        if (!isset(IdentityPolicy::FOREIGN_KEYS[$type])) {
            return;
        }

        // The platform has already assigned the identifier of a new record when this hook
        // runs, and its API discards a client-supplied one; import is the route that could
        // carry identifiers in, so it is refused here (3.7).
        if ($options->get('import')) {
            throw new Forbidden('Import is not available for firms, contacts and enquiries.');
        }

        $isNew = $entity->isNew();

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
        // are otherwise written after the save and checked on unrelate).
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

    // ---- record input (create and update hooks) -------------------------------

    /** A record create or update that carries a link list the link routes own is refused. */
    public function refuseLinkListInput(Entity $entity): void
    {
        foreach (IdentityPolicy::REFUSED_INPUT_ATTRIBUTES[$entity->getEntityType()] ?? [] as $attribute) {
            if ($entity->has($attribute)) {
                throw new Forbidden(
                    'Branches and predecessors are changed through the link routes, and a successor by ' .
                    'retiring or superseding the record. They cannot be set in a record save.'
                );
            }
        }
    }

    // ---- links: before the change (record link and unlink hooks) --------------

    /**
     * Refusals that need no audit and no change: a successor is never set by linking, and
     * the primary firm's link is never removed on its own. Called by the record link and
     * unlink hooks, which the platform runs before it relates or unrelates.
     */
    public function refuseLinkChange(Entity $entity, string $link, Entity $foreign, bool $relate): void
    {
        $type = $entity->getEntityType();

        if (isset(IdentityPolicy::EDIT_ONLY_LINKS[$type][$link])) {
            throw new Forbidden('Retire or supersede a record by editing it, not by linking.');
        }

        if ($relate || !isset(IdentityPolicy::LINKS[$type][$link])) {
            return;
        }

        [$relationship, $changedSide, $firmSide] = IdentityPolicy::LINKS[$type][$link];

        if ($relationship !== IdentityPolicy::REL_CONTACT_FIRM_LINK) {
            return;
        }

        $changed = $changedSide === 'self' ? $entity : $foreign;
        $firm = $firmSide === 'self' ? $entity : $foreign;

        if (IdentityPolicy::unlinkRemovesPrimary($changed->get('accountId'), (string) $firm->getId())) {
            throw $this->primaryUnlinkRefusal();
        }
    }

    private function primaryUnlinkRefusal(): Forbidden
    {
        return new Forbidden(
            'This firm is the contact\'s primary firm. Set another linked firm as primary, ' .
            'or clear the primary firm, before removing the link.'
        );
    }

    // ---- links: after the change (hooks the platform calls on every relate) ----

    public function afterRelate(Entity $entity, string $link, Entity $foreign): void
    {
        $this->linkChanged($entity, $link, $foreign, true);
    }

    public function afterUnrelate(Entity $entity, string $link, Entity $foreign): void
    {
        $this->linkChanged($entity, $link, $foreign, false);
    }

    private function linkChanged(Entity $entity, string $link, Entity $foreign, bool $relate): void
    {
        $type = $entity->getEntityType();

        $editOnly = IdentityPolicy::EDIT_ONLY_LINKS[$type][$link] ?? null;
        $definition = IdentityPolicy::LINKS[$type][$link] ?? null;

        if ($editOnly !== null) {
            [$changedSide, $kind, $attribute] = $editOnly;
            $changed = $changedSide === 'self' ? $entity : $foreign;
            $firmId = (string) ($changedSide === 'self' ? $foreign : $entity)->getId();

            $this->putBack($kind, $attribute, $changed, $firmId, $relate, $this->previousKey($changed, $kind, (string) $attribute));

            throw new Forbidden('Retire or supersede a record by editing it, not by linking.');
        }

        if ($definition === null) {
            return;
        }

        [$relationship, $changedSide, $firmSide, $kind, $attribute] = $definition;

        $changed = $changedSide === 'self' ? $entity : $foreign;
        $firmId = (string) ($firmSide === 'self' ? $entity : $foreign)->getId();
        $changedType = $changed->getEntityType();
        $changedId = (string) $changed->getId();

        if ($kind === IdentityPolicy::KIND_MANY_MANY) {
            $previous = $relate ? '' : $firmId;
            $new = $relate ? $firmId : '';
        } elseif ($relate) {
            $previous = $this->previousKey($changed, $kind, (string) $attribute);
            $new = $kind === IdentityPolicy::KIND_HAS_MANY ? $firmId : (string) $foreign->getId();
        } else {
            $previous = $kind === IdentityPolicy::KIND_HAS_MANY ? $firmId : (string) $foreign->getId();
            $new = '';
        }

        if ($previous === $new) {
            return;
        }

        // Backstop for a contact's primary firm: its link is never removed on its own.
        if (
            !$relate &&
            $relationship === IdentityPolicy::REL_CONTACT_FIRM_LINK &&
            IdentityPolicy::unlinkRemovesPrimary($changed->get('accountId'), $firmId)
        ) {
            $this->putBack($kind, $attribute, $changed, $firmId, false, $previous);

            throw $this->primaryUnlinkRefusal();
        }

        $ledgerKey = implode('|', [$changedType, $changedId, $relationship, $firmId]);
        $state = $relate ? 'linked' : 'unlinked';

        if ((self::$linkState[$ledgerKey] ?? null) === $state) {
            return;
        }

        if ($changed->isNew()) {
            try {
                $this->undoCreateOnFailure($changed, function () use ($relationship, $changedType, $changedId, $previous, $new): void {
                    $this->auditor->record($relationship, $changedType, $changedId, $previous, $new);
                });
            } catch (Forbidden $e) {
                unset(self::$linkState[$ledgerKey]);

                throw $e;
            }

            self::$linkState[$ledgerKey] = $state;

            return;
        }

        try {
            $this->auditor->record($relationship, $changedType, $changedId, $previous, $new);
        } catch (Forbidden $e) {
            unset(self::$linkState[$ledgerKey]);

            $this->putBack(
                $kind,
                $attribute,
                $changed,
                $firmId,
                $relate,
                $relate ? $previous : $firmId
            );

            throw $e;
        }

        self::$linkState[$ledgerKey] = $state;
    }

    /**
     * The identifier a foreign key held before a relate, as far as the record in hand
     * knows it. For a link whose key is on the foreign record (hasMany) it is the value
     * that record was loaded with; a record the platform only identified (relate by
     * identifier) has none loaded, so the key is taken to have been empty. For a link
     * whose key is on the record itself (belongsTo) the platform's mapper has already
     * overwritten the value in hand, so the previous key is not known and is taken to
     * have been empty (the platform's own use of such a relate is only to set a primary
     * firm where there was none).
     */
    private function previousKey(Entity $changed, string $kind, string $attribute): string
    {
        if ($kind !== IdentityPolicy::KIND_HAS_MANY || $attribute === '' || !$changed->has($attribute)) {
            return '';
        }

        return (string) $changed->get($attribute);
    }

    /**
     * Puts a relation change back, so a change whose audit could not be stored does not
     * stay. $firmId is the firm end of the link; $previous the key value to restore after
     * a relate (empty for none). Everything goes through the ORM query builder, so no
     * hook runs again.
     */
    private function putBack(
        string $kind,
        ?string $attribute,
        Entity $changed,
        string $firmId,
        bool $relate,
        string $previous
    ): void {
        try {
            if ($kind === IdentityPolicy::KIND_MANY_MANY) {
                $this->entityManager->getQueryExecutor()->execute(
                    UpdateBuilder::create()
                        ->in(IdentityPolicy::JUNCTION)
                        ->set(['deleted' => $relate])
                        ->where(['accountId' => $firmId, 'contactId' => (string) $changed->getId()])
                        ->build()
                );

                return;
            }

            // A key restored after an unrelate is the firm that held it; after a relate, the
            // value the record had before (null when there was none).
            $value = $relate ? ($previous === '' ? null : $previous) : $firmId;

            $this->entityManager->getQueryExecutor()->execute(
                UpdateBuilder::create()
                    ->in($changed->getEntityType())
                    ->set([(string) $attribute => $value])
                    ->where(['id' => (string) $changed->getId()])
                    ->build()
            );
        } catch (Throwable) {
            // Nothing more can be done here; the refusal that follows still stops the request.
        }
    }

    public function afterMassRelate(Entity $entity, string $link, Select $query): void
    {
        $type = $entity->getEntityType();

        if (!in_array($link, IdentityPolicy::BULK_REFUSED_LINKS[$type] ?? [], true)) {
            return;
        }

        $foreignType = $query->getFrom();
        $definition = IdentityPolicy::LINKS[$type][$link] ?? IdentityPolicy::EDIT_ONLY_LINKS[$type][$link] ?? null;

        if ($definition !== null) {
            $foreignId = (string) $entity->getId();

            foreach ($this->entityManager->getRDBRepository($foreignType)->clone($query)->find() as $foreign) {
                if (isset(IdentityPolicy::EDIT_ONLY_LINKS[$type][$link])) {
                    [$changedSide, $kind, $attribute] = $definition;
                } else {
                    [, $changedSide, , $kind, $attribute] = $definition;
                }

                $changed = $changedSide === 'self' ? $entity : $foreign;
                $firmId = $changedSide === 'self' ? (string) $foreign->getId() : $foreignId;

                $this->putBack($kind, $attribute, $changed, $firmId, true, '');
            }
        }

        throw new Forbidden('Bulk linking is not available for identity relationships. Link records one at a time.');
    }

    // ---- remove ---------------------------------------------------------------

    public function beforeRemove(Entity $entity): void
    {
        throw $this->removalRefusal();
    }

    public function removalRefusal(): Forbidden
    {
        return new Forbidden(
            'Identity records (firms, contacts and their audit history) are never deleted. Retire a firm or contact, or supersede it with a successor.'
        );
    }

    // ---- helpers --------------------------------------------------------------

    /**
     * Runs $write; if the audit cannot be stored and the record is one this request
     * is creating, the record and its firm link rows are removed again so the create
     * leaves nothing behind.
     */
    private function undoCreateOnFailure(Entity $entity, callable $write): void
    {
        try {
            $write();
        } catch (Forbidden $e) {
            if ($entity->isNew() && !IdentityPolicy::isEmpty($entity->getId())) {
                $this->deleteRows($entity);
            }

            throw $e;
        }
    }

    private function deleteRows(Entity $entity): void
    {
        $executor = $this->entityManager->getQueryExecutor();

        if ($entity->getEntityType() === 'Contact') {
            try {
                $executor->execute(
                    DeleteBuilder::create()
                        ->from(IdentityPolicy::JUNCTION)
                        ->where(['contactId' => (string) $entity->getId()])
                        ->build()
                );
            } catch (Throwable) {
                // The link rows of an undone create may remain; see docs/IDENTITY-INTEGRITY.md.
            }
        }

        try {
            $executor->execute(
                DeleteBuilder::create()
                    ->from($entity->getEntityType())
                    ->where(['id' => (string) $entity->getId()])
                    ->build()
            );
        } catch (Throwable) {
            // Nothing more can be done here; the refusal that follows still stops the request.
        }
    }
}
