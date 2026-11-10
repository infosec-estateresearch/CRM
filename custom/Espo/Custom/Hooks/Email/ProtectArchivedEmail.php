<?php

namespace Espo\Custom\Hooks\Email;

use Espo\Core\Exceptions\Forbidden;
use Espo\Core\Hook\Hook\BeforeSave;
use Espo\Entities\User;
use Espo\ORM\Entity;
use Espo\ORM\Repository\Option\SaveOptions;

/**
 * CRM-005 (R11): an archived email is read-only history. Once an Email has been
 * saved with status Archived, its subject, body, addresses, dates, message id and
 * status cannot be changed, except by an admin or by the ER Import API user
 * (type api, userName 'er-import', as in config/access/api_users.json).
 * Re-linking the parent (enquiry, firm, contact) and every other attribute stay
 * editable. New records are not guarded: the importer creates them.
 * The rule table is mirrored in tests/unit/activity_policy.py (archived_save_allowed).
 *
 * @implements BeforeSave<Entity>
 */
class ProtectArchivedEmail implements BeforeSave
{
    private const PROTECTED_ATTRIBUTES = [
        'name',
        'body',
        'bodyPlain',
        'isHtml',
        'from',
        'to',
        'cc',
        'bcc',
        'fromString',
        'dateSent',
        'messageId',
        'status',
    ];

    public function __construct(private User $user)
    {}

    public function beforeSave(Entity $entity, SaveOptions $options): void
    {
        if ($entity->isNew()) {
            return;
        }

        if ($entity->getFetched('status') !== 'Archived') {
            return;
        }

        if ($this->user->isAdmin()) {
            return;
        }

        $isImportUser = $this->user->getType() === User::TYPE_API &&
            $this->user->getUserName() === 'er-import';

        if ($isImportUser) {
            return;
        }

        foreach (self::PROTECTED_ATTRIBUTES as $attribute) {
            if ($entity->isAttributeChanged($attribute)) {
                throw new Forbidden('An archived email is read-only history.');
            }
        }
    }
}
