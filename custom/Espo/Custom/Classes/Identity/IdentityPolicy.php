<?php

namespace Espo\Custom\Classes\Identity;

/**
 * CRM-IDINT-001: the identity rules, with no EspoCRM dependency so they can be
 * run and tested on their own (tests/unit/test_identity.py executes this file
 * under php when it is installed).
 *
 * Identifiers: FirmID = Account.id, ContactID = Contact.id. Identity
 * relationships: a firm's parent firm, a contact's primary firm, a contact's
 * other firm links, an enquiry's firm and a successor link.
 */
final class IdentityPolicy
{
    public const STATUS_ACTIVE = 'active';
    public const STATUS_RETIRED = 'retired';
    public const STATUS_SUPERSEDED = 'superseded';
    public const STATUSES = [self::STATUS_ACTIVE, self::STATUS_RETIRED, self::STATUS_SUPERSEDED];

    /** Longest successor chain followed before it is treated as a cycle. */
    public const MAX_CHAIN = 1000;

    public const REL_PARENT_FIRM = 'parentFirm';
    public const REL_PRIMARY_FIRM = 'primaryFirm';
    public const REL_CONTACT_FIRM_LINK = 'contactFirmLink';
    public const REL_ENQUIRY_FIRM = 'enquiryFirm';
    public const REL_SUCCESSOR = 'successor';
    public const REL_STATUS = 'status';

    public const RELATIONSHIPS = [
        self::REL_PARENT_FIRM,
        self::REL_PRIMARY_FIRM,
        self::REL_CONTACT_FIRM_LINK,
        self::REL_ENQUIRY_FIRM,
        self::REL_SUCCESSOR,
        self::REL_STATUS,
    ];

    /** Foreign-key attributes that carry an identity relationship, by entity type. */
    public const FOREIGN_KEYS = [
        'Account' => ['parentId' => self::REL_PARENT_FIRM, 'successorId' => self::REL_SUCCESSOR],
        'Contact' => ['accountId' => self::REL_PRIMARY_FIRM, 'successorId' => self::REL_SUCCESSOR],
        'Opportunity' => ['accountId' => self::REL_ENQUIRY_FIRM],
    ];

    /** Entity types that have an identity status and a successor. */
    public const STATUS_ENTITIES = ['Account', 'Contact'];

    /**
     * Link changes (relate or unrelate) that carry an identity relationship, by the
     * entity type whose after-relate / after-unrelate hook sees them.
     * [entityType][link] => [relationship, which side is the changed record,
     *                        which side carries the firm, link kind,
     *                        foreign-key attribute on the changed record or null]
     * 'self' is the record the hook runs for; 'foreign' is the other end. The kind is
     * how the platform stores the link: 'manyMany' is a row of the AccountContact
     * junction, 'hasMany' a foreign key on the foreign record, 'belongsTo' a foreign key
     * on the record itself.
     */
    public const LINKS = [
        'Account' => [
            'branches' => [self::REL_PARENT_FIRM, 'foreign', 'self', self::KIND_HAS_MANY, 'parentId'],
            'parent' => [self::REL_PARENT_FIRM, 'self', 'foreign', self::KIND_BELONGS_TO, 'parentId'],
            'contacts' => [self::REL_CONTACT_FIRM_LINK, 'foreign', 'self', self::KIND_MANY_MANY, null],
            'contactsPrimary' => [self::REL_PRIMARY_FIRM, 'foreign', 'self', self::KIND_HAS_MANY, 'accountId'],
            'opportunities' => [self::REL_ENQUIRY_FIRM, 'foreign', 'self', self::KIND_HAS_MANY, 'accountId'],
        ],
        'Contact' => [
            'accounts' => [self::REL_CONTACT_FIRM_LINK, 'self', 'foreign', self::KIND_MANY_MANY, null],
            'account' => [self::REL_PRIMARY_FIRM, 'self', 'foreign', self::KIND_BELONGS_TO, 'accountId'],
        ],
        'Opportunity' => [
            'account' => [self::REL_ENQUIRY_FIRM, 'self', 'foreign', self::KIND_BELONGS_TO, 'accountId'],
        ],
    ];

    public const KIND_MANY_MANY = 'manyMany';
    public const KIND_HAS_MANY = 'hasMany';
    public const KIND_BELONGS_TO = 'belongsTo';

    /** The junction entity of a contact's firm links (EspoCRM Crm module). */
    public const JUNCTION = 'AccountContact';

    /**
     * Links that may never be changed through a link or unlink: use the record edit.
     * [entityType][link] => [which side is the changed record, link kind, foreign-key attribute]
     */
    public const EDIT_ONLY_LINKS = [
        'Account' => [
            'successor' => ['self', self::KIND_BELONGS_TO, 'successorId'],
            'predecessors' => ['foreign', self::KIND_HAS_MANY, 'successorId'],
        ],
        'Contact' => [
            'successor' => ['self', self::KIND_BELONGS_TO, 'successorId'],
            'predecessors' => ['foreign', self::KIND_HAS_MANY, 'successorId'],
        ],
    ];

    /**
     * Link-multiple attributes whose input is refused on create and edit: a firm's
     * branches and every record's predecessors are changed through the link routes
     * (or, for a successor, through the status workflow), so the change is audited with
     * the identifier it replaces.
     */
    public const REFUSED_INPUT_ATTRIBUTES = [
        'Account' => ['branchesIds', 'predecessorsIds'],
        'Contact' => ['predecessorsIds'],
    ];

    /** Links where a bulk link (mass relate) is refused. */
    public const BULK_REFUSED_LINKS = [
        'Account' => ['branches', 'parent', 'contacts', 'contactsPrimary', 'opportunities',
            'successor', 'predecessors'],
        'Contact' => ['accounts', 'account', 'successor', 'predecessors'],
        'Opportunity' => ['account'],
    ];

    /** The audit record's own scope; nothing else may write it. */
    public const AUDIT_ENTITY = 'IdentityAudit';

    /** Save option only server code sets, so no API caller can create an audit record. */
    public const AUDIT_WRITE_OPTION = 'identityAuditWrite';

    public static function isEmpty(mixed $value): bool
    {
        return $value === null || $value === '';
    }

    /** A contact's primary firm must be one of its linked firms. True means broken. */
    public static function primaryFirmBroken(?string $primaryId, array $linkedIds): bool
    {
        if (self::isEmpty($primaryId)) {
            return false;
        }

        return !in_array($primaryId, $linkedIds, true);
    }

    /** Unlinking the primary firm is refused. True means refused. */
    public static function unlinkRemovesPrimary(?string $primaryId, string $unlinkedFirmId): bool
    {
        return !self::isEmpty($primaryId) && $primaryId === $unlinkedFirmId;
    }

    /**
     * The problem with a status and successor pair, or null when it is valid.
     * $successorExists tells whether the named successor is an existing record of
     * the same kind.
     */
    public static function statusProblem(?string $status, ?string $successorId, bool $successorExists): ?string
    {
        $status = self::isEmpty($status) ? self::STATUS_ACTIVE : $status;

        if (!in_array($status, self::STATUSES, true)) {
            return 'The identity status must be active, retired or superseded.';
        }

        if ($status === self::STATUS_SUPERSEDED) {
            if (self::isEmpty($successorId)) {
                return 'A superseded record needs a successor.';
            }

            if (!$successorExists) {
                return 'The successor must be an existing record of the same kind.';
            }

            return null;
        }

        if (!self::isEmpty($successorId)) {
            return 'Only a superseded record has a successor.';
        }

        return null;
    }

    /**
     * Whether following the successor chain from $startId reaches $selfId (or loops
     * on itself). $next maps an identifier to its successor identifier or null.
     */
    public static function successorLoop(string $selfId, ?string $startId, callable $next): bool
    {
        $seen = [];
        $current = $startId;
        $steps = 0;

        while (!self::isEmpty($current)) {
            if ($current === $selfId || isset($seen[$current]) || ++$steps > self::MAX_CHAIN) {
                return true;
            }

            $seen[$current] = true;
            $current = $next($current);
        }

        return false;
    }

    /** The end of a successor chain (what an identifier resolves to), or null if it loops. */
    public static function resolve(string $id, callable $next): ?string
    {
        $seen = [$id => true];
        $current = $id;

        for ($steps = 0; $steps <= self::MAX_CHAIN; $steps++) {
            $following = $next($current);

            if (self::isEmpty($following)) {
                return $current;
            }

            if (isset($seen[$following])) {
                return null;
            }

            $seen[$following] = true;
            $current = $following;
        }

        return null;
    }
}
