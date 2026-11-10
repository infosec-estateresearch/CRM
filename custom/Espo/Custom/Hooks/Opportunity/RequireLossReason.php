<?php

namespace Espo\Custom\Hooks\Opportunity;

use Espo\Core\Exceptions\BadRequest;
use Espo\Core\Hook\Hook\BeforeSave;
use Espo\Entities\User;
use Espo\ORM\Entity;
use Espo\ORM\Repository\Option\SaveOptions;

/**
 * CRM-004 (R7, D3): an enquiry (Opportunity) cannot be saved as Lost without a
 * loss reason. Two exemptions, both only for records flagged
 * lossReasonLegacyMissing (a Salesforce record closed as lost without a reason):
 * - the ER Import API user (type api, userName 'er-import', as in
 *   config/access/api_users.json) may write such a record; no other API user may;
 * - anyone may save such a record while neither the stage nor the loss reason
 *   is being changed.
 * People cannot set the flag: role fieldData makes it read-only for them.
 * The rule table is mirrored in tests/unit/enquiry_policy.py (loss_reason_allowed).
 *
 * @implements BeforeSave<Entity>
 */
class RequireLossReason implements BeforeSave
{
    public function __construct(private User $user)
    {}

    public function beforeSave(Entity $entity, SaveOptions $options): void
    {
        if ($entity->get('stage') !== 'Lost') {
            return;
        }

        if ((string) $entity->get('lossReason') !== '') {
            return;
        }

        $legacyMissing = $entity->get('lossReasonLegacyMissing') === true;

        $isImportUser = $this->user->getType() === User::TYPE_API &&
            $this->user->getUserName() === 'er-import';

        if ($legacyMissing && $isImportUser) {
            return;
        }

        $unchanged = !$entity->isAttributeChanged('stage') &&
            !$entity->isAttributeChanged('lossReason');

        if ($legacyMissing && $unchanged) {
            return;
        }

        throw new BadRequest('A lost enquiry needs a loss reason.');
    }
}
